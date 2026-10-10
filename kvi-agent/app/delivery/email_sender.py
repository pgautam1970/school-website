"""Email delivery: SMTP transport with retry, exponential backoff, duplicate-send
prevention, per-attempt delivery logs, failure notices and a backup recipient.

Guarantees
- 'accepted' is recorded ONLY when the SMTP server returns a success response
  for the message. Generation alone never marks a report as sent.
- Duplicate prevention: the daily send first atomically CLAIMS the report
  (UPDATE ... WHERE status NOT IN ('sending','sent')). A second scheduler run,
  a restarted process or a double click sees the claim and skips.
- Retries: only transient failures (connection errors, SMTP 4xx, timeouts) are
  retried, with exponential backoff capped at KVI_EMAIL_BACKOFF_MAX_SECONDS.
  Authentication/permanent (5xx) failures are not retried.
- Manual resend is an explicit admin action that is audited and recorded as
  kind='resend'; it still refuses to send a second copy unless forced.
"""
from __future__ import annotations

import logging
import smtplib
import socket
import ssl
import time
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..models import DailyReport, EmailLog, utcnow

log = logging.getLogger("kvi.email")

TRANSIENT_EXC = (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError,
                 smtplib.SMTPHeloError, socket.timeout, ConnectionError, TimeoutError)


@dataclass
class SendOutcome:
    status: str                 # accepted | failed | skipped_duplicate | not_configured
    attempts: int = 0
    message: str = ""
    log_ids: list[int] | None = None


def subject_for(report_date: str, settings: Settings, kind: str = "daily") -> str:
    base = f"{settings.school_name} | Daily School Intelligence Report | {report_date}"
    if kind == "test":
        return f"[TEST] {settings.school_name} | Email delivery test | {report_date}"
    if kind == "resend":
        return base + " (resent)"
    return base


def build_message(*, to: str, subject: str, text: str, html: str, settings: Settings,
                  attachment: Path | None = None, report_uid: str = "") -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Date"] = formatdate(localtime=False)
    msg["Message-ID"] = make_msgid(domain=(settings.smtp_from.split("@")[-1].strip(">") or "kvi.local"))
    if report_uid:
        msg["X-KVI-Report-ID"] = report_uid
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    if attachment and attachment.is_file():
        msg.add_attachment(attachment.read_bytes(), maintype="application",
                           subtype="pdf", filename=attachment.name)
    return msg


def _smtp_send(msg: EmailMessage, settings: Settings, timeout: float = 30.0) -> str:
    """Send one message. Returns provider response text. Raises on failure."""
    if settings.smtp_ssl:
        server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=timeout,
                                  context=ssl.create_default_context())
    else:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=timeout)
    try:
        server.ehlo()
        if settings.smtp_starttls and not settings.smtp_ssl:
            server.starttls(context=ssl.create_default_context())
            server.ehlo()
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password)
        # Post-DATA responses are NOT retried: once the server accepted the message,
        # any later error would otherwise cause a duplicate send.
        refused = server.send_message(msg)  # {} means accepted for all recipients
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)
        return "SMTP server accepted the message (250 after DATA)"
    finally:
        try:
            server.quit()
        except Exception:
            server.close()


def send_with_retries(msg: EmailMessage, settings: Settings, *, sender=_smtp_send,
                      sleep=time.sleep) -> tuple[str, int, str]:
    """Return (status, attempts, detail). status in accepted|failed."""
    max_attempts = max(1, settings.email_max_retries + 1)
    last_err = ""
    for attempt in range(1, max_attempts + 1):
        try:
            resp = sender(msg, settings)
            return "accepted", attempt, resp
        except smtplib.SMTPResponseException as exc:
            last_err = f"SMTP {exc.smtp_code}: {exc.smtp_error[:200] if isinstance(exc.smtp_error, bytes) else exc.smtp_error}"
            transient = 400 <= exc.smtp_code < 500
        except smtplib.SMTPRecipientsRefused as exc:
            last_err = f"Recipient refused: {exc.recipients}"
            transient = False
        except smtplib.SMTPAuthenticationError as exc:
            last_err = f"SMTP authentication failed ({exc.smtp_code}) — check KVI_SMTP_USERNAME/PASSWORD"
            transient = False
        except TRANSIENT_EXC as exc:
            last_err = f"Transient network error: {type(exc).__name__}: {exc}"
            transient = True
        except (smtplib.SMTPException, ssl.SSLError, OSError) as exc:
            last_err = f"{type(exc).__name__}: {exc}"
            transient = isinstance(exc, (OSError, ssl.SSLError)) and not isinstance(exc, smtplib.SMTPException)
        log.warning("email attempt %d/%d failed: %s", attempt, max_attempts, last_err)
        if not transient or attempt == max_attempts:
            return "failed", attempt, last_err
        delay = min(settings.email_backoff_base_seconds * (2 ** (attempt - 1)),
                    settings.email_backoff_max_seconds)
        sleep(delay)
    return "failed", max_attempts, last_err


def _log(db: Session, *, report: DailyReport | None, uid: str, attempt: int, kind: str,
         to: str, subject: str, status: str, detail: str, has_pdf: bool) -> EmailLog:
    row = EmailLog(report_id=report.id if report else None, report_uid=uid, attempt=attempt,
                   kind=kind, to_addr=to[:300], subject=subject[:400], status=status,
                   provider_response=detail[:2000], has_pdf=has_pdf)
    db.add(row)
    db.commit()
    return row


def claim_report_for_send(db: Session, report_id: int, *, force: bool = False) -> bool:
    """Atomically move report to 'sending'. False if another run owns/completed it."""
    blocked = ["sending"] if force else ["sending", "sent"]
    res = db.execute(update(DailyReport)
                     .where(DailyReport.id == report_id, DailyReport.status.not_in(blocked))
                     .values(status="sending"))
    db.commit()
    return res.rowcount == 1


def send_daily_report(db: Session, report: DailyReport, *, kind: str = "daily",
                      force: bool = False, settings: Settings | None = None,
                      sender=_smtp_send, sleep=time.sleep) -> SendOutcome:
    s = settings or get_settings()
    subject = subject_for(report.report_date, s, kind)
    attachment = Path(report.pdf_path) if (report.pdf_path and s.email_attach_pdf) else None
    if not s.email_configured:
        _log(db, report=report, uid=report.report_uid, attempt=0, kind=kind, to=s.report_recipient,
             subject=subject, status="not_configured",
             detail="SMTP not configured (KVI_SMTP_HOST empty). Report archived, NOT delivered.",
             has_pdf=False)
        report.status = "no_email_config"
        db.commit()
        return SendOutcome("not_configured", 0, "SMTP not configured")

    if kind == "daily" and not force:
        already = db.scalar(select(EmailLog.id).where(
            EmailLog.report_uid == report.report_uid, EmailLog.status == "accepted",
            EmailLog.kind.in_(["daily", "resend"])))
        if already:
            _log(db, report=report, uid=report.report_uid, attempt=0, kind=kind,
                 to=s.report_recipient, subject=subject, status="skipped_duplicate",
                 detail=f"Already accepted by provider (log #{already}); duplicate send prevented.",
                 has_pdf=False)
            return SendOutcome("skipped_duplicate", 0, "already accepted")

    if not claim_report_for_send(db, report.id, force=force):
        _log(db, report=report, uid=report.report_uid, attempt=0, kind=kind, to=s.report_recipient,
             subject=subject, status="skipped_duplicate",
             detail="Another send for this report is in progress or completed.", has_pdf=False)
        return SendOutcome("skipped_duplicate", 0, "claim not acquired")

    recipients = [s.report_recipient]
    results: list[int] = []
    overall_status, total_attempts, detail = "accepted", 0, ""
    for to in recipients:
        msg = build_message(to=to, subject=subject, text=report.text, html=report.html,
                            settings=s, attachment=attachment, report_uid=report.report_uid)
        status, attempts, resp = send_with_retries(msg, s, sender=sender, sleep=sleep)
        total_attempts += attempts
        row = _log(db, report=report, uid=report.report_uid, attempt=attempts, kind=kind, to=to,
                   subject=subject, status=status if status == "failed" else "accepted",
                   detail=resp, has_pdf=bool(attachment))
        results.append(row.id)
        if status != "accepted":
            overall_status, detail = "failed", resp

    if overall_status == "accepted":
        report.status = "sent"
        report.data = {**report.data, "delivered_at": utcnow().isoformat()}
        detail = "accepted by provider"
    else:
        report.status = "failed"
        _notify_failure(db, report, s, detail, sender=sender, sleep=sleep)
    db.commit()
    # backup copy is independent and only when configured
    if overall_status == "accepted" and s.backup_recipient:
        send_backup_copy(db, report, s, subject, attachment, sender=sender, sleep=sleep)
    return SendOutcome(overall_status, total_attempts, detail, results)


def send_backup_copy(db: Session, report: DailyReport, s: Settings, subject: str,
                     attachment: Path | None, *, sender=_smtp_send, sleep=time.sleep) -> None:
    msg = build_message(to=s.backup_recipient, subject=subject + " [backup copy]",
                        text=report.text, html=report.html, settings=s,
                        attachment=attachment, report_uid=report.report_uid)
    status, attempts, resp = send_with_retries(msg, s, sender=sender, sleep=sleep)
    _log(db, report=report, uid=report.report_uid, attempt=attempts, kind="backup",
         to=s.backup_recipient, subject=subject, status="accepted" if status == "accepted" else "failed",
         detail=resp, has_pdf=bool(attachment))


def _notify_failure(db: Session, report: DailyReport, s: Settings, detail: str, *,
                    sender=_smtp_send, sleep=time.sleep) -> None:
    """Failure notice goes to the backup recipient when configured. The primary
    recipient is intentionally not used for failure notices — its delivery already failed.
    The failure is always visible on the dashboard (System health / Email logs)."""
    if not s.backup_recipient:
        log.error("Report %s delivery failed and no backup recipient is configured: %s",
                  report.report_date, detail)
        return
    msg = build_message(
        to=s.backup_recipient,
        subject=f"[ACTION NEEDED] KVI daily report delivery failed | {report.report_date}",
        text=f"Delivery of the daily report for {report.report_date} (ID {report.report_uid}) failed.\n"
             f"Last error: {detail}\nThe report is archived in the dashboard and can be resent manually.",
        html=f"<p>Delivery of the daily report for <b>{report.report_date}</b> failed.</p>"
             f"<p>Last error: <code>{detail}</code></p><p>Use the dashboard to resend.</p>",
        settings=s, report_uid=report.report_uid)
    status, attempts, resp = send_with_retries(msg, s, sender=sender, sleep=sleep)
    _log(db, report=report, uid=report.report_uid, attempt=attempts, kind="failure_notice",
         to=s.backup_recipient, subject=msg["Subject"], status="accepted" if status == "accepted" else "failed",
         detail=resp, has_pdf=False)


def send_test_email(db: Session, *, to: str | None = None, settings: Settings | None = None,
                    sender=_smtp_send, sleep=time.sleep) -> SendOutcome:
    """Connectivity/configuration test. Contains no school data."""
    s = settings or get_settings()
    recipient = to or s.report_recipient
    subject = subject_for(utcnow().date().isoformat(), s, "test")
    if not s.email_configured:
        _log(db, report=None, uid="", attempt=0, kind="test", to=recipient, subject=subject,
             status="not_configured", detail="SMTP not configured", has_pdf=False)
        return SendOutcome("not_configured", 0, "SMTP not configured")
    text = (f"This is a delivery test from {s.school_name}'s Daily School Intelligence Agent.\n"
            "It contains no school data. If you received this message, SMTP delivery works.")
    html = (f"<p>This is a delivery test from <b>{s.school_name}</b>'s Daily School Intelligence Agent.</p>"
            "<p>It contains no school data. If you received this message, SMTP delivery works.</p>")
    msg = build_message(to=recipient, subject=subject, text=text, html=html, settings=s)
    status, attempts, resp = send_with_retries(msg, s, sender=sender, sleep=sleep)
    _log(db, report=None, uid="", attempt=attempts, kind="test", to=recipient, subject=subject,
         status="accepted" if status == "accepted" else "failed", detail=resp, has_pdf=False)
    return SendOutcome("accepted" if status == "accepted" else "failed", attempts, resp)
