"""Test 8 (HTML email and PDF), Test 11 (retry, backoff, duplicate-send prevention)."""
import smtplib
from pathlib import Path

from sqlalchemy import select

from app.analysis.pipeline import run_pipeline
from app.config import get_settings
from app.delivery.email_sender import build_message, send_daily_report, send_test_email, send_with_retries
from app.models import DailyReport, EmailLog
from conftest import TEST_DAY

SECTIONS = ["A. Principal", "B. Critical", "C. Class-wise", "D. Educator", "E. Parent",
            "F. Facebook", "G. Upcoming", "H. Principal", "I. Positive", "J. Source", "K. Tomorrow"]


def _smtp_settings(**extra):
    return get_settings().model_copy(update={"smtp_host": "smtp.test.invalid", "smtp_from": "KVI <noreply@test.invalid>",
                                             "email_backoff_base_seconds": 2.0, "email_max_retries": 4, **extra})


def _fresh_report(db):
    return run_pipeline(db, TEST_DAY)


def test_html_and_plain_text_contain_all_report_sections(seeded, db):
    rep = _fresh_report(db)
    for s in SECTIONS:
        assert s in rep.html, s
        assert s.split(".")[0] + "." in rep.text
    assert 'name="viewport"' in rep.html and "max-width:860px" in rep.html   # responsive container
    assert "नेपाली सारांश" in rep.html                                         # Nepali executive summary
    assert "Report ID" in rep.html


def test_pdf_attachment_is_generated_and_valid(seeded, db):
    rep = _fresh_report(db)
    assert rep.pdf_path and Path(rep.pdf_path).is_file()
    head = Path(rep.pdf_path).read_bytes()[:8]
    assert head.startswith(b"%PDF-")
    assert Path(rep.pdf_path).stat().st_size > 3000
    assert rep.pdf_engine == "fpdf2"


def test_email_message_has_alternatives_and_pdf_attachment(seeded, db):
    rep = _fresh_report(db)
    s = _smtp_settings()
    msg = build_message(to="kptcc@gmail.com", subject="Kashyap Vidyapeeth | Daily School Intelligence Report | " + TEST_DAY,
                        text=rep.text, html=rep.html, settings=s, attachment=Path(rep.pdf_path), report_uid=rep.report_uid)
    assert msg["To"] == "kptcc@gmail.com"
    assert msg["X-KVI-Report-ID"] == rep.report_uid
    types = [p.get_content_type() for p in msg.walk()]
    assert "text/plain" in types and "text/html" in types and "application/pdf" in types


class FlakySender:
    """MOCK SMTP: fails transiently twice, then the server accepts."""
    def __init__(self):
        self.calls = 0
    def __call__(self, msg, settings):
        self.calls += 1
        if self.calls <= 2:
            raise smtplib.SMTPServerDisconnected("connection unexpectedly closed (mock)")
        return "SMTP server accepted the message (mock)"


def test_retry_with_exponential_backoff_then_success(seeded, db):
    rep = _fresh_report(db)
    sleeps = []
    sender = FlakySender()
    outcome = send_daily_report(db, rep, settings=_smtp_settings(), sender=sender, sleep=sleeps.append)
    assert outcome.status == "accepted"
    assert sender.calls == 3
    assert sleeps == [2.0, 4.0]                       # exponential: base * 2^(n-1)
    logs = list(db.scalars(select(EmailLog).where(EmailLog.report_uid == rep.report_uid, EmailLog.kind == "daily")))
    assert logs[-1].status == "accepted" and logs[-1].attempt == 3
    db.refresh(rep)
    assert rep.status == "sent"                       # accepted by provider -> sent


def test_permanent_auth_failure_is_not_retried_and_is_reported(seeded, db):
    class AuthFail:
        calls = 0
        def __call__(self, msg, settings):
            AuthFail.calls += 1
            raise smtplib.SMTPAuthenticationError(535, b"5.7.8 bad credentials (mock)")
    rep = _fresh_report(db)
    outcome = send_daily_report(db, rep, settings=_smtp_settings(), sender=AuthFail(), sleep=lambda s: None, force=True)
    assert outcome.status == "failed"
    assert AuthFail.calls == 1
    db.refresh(rep)
    assert rep.status == "failed"                     # never claimed as sent


def test_second_send_for_same_report_is_skipped_duplicate(seeded, db):
    # dedicated date so earlier tests' sends for TEST_DAY do not interfere (one row per date)
    rep = run_pipeline(db, "2026-10-12")
    ok = lambda msg, settings: "accepted (mock)"
    s = _smtp_settings()
    first = send_daily_report(db, rep, settings=s, sender=ok, sleep=lambda x: None)
    assert first.status == "accepted"
    calls = []
    second = send_daily_report(db, rep, settings=s, sender=lambda m, st: calls.append(1) or "x", sleep=lambda x: None)
    assert second.status == "skipped_duplicate"
    assert calls == []                                # no second message ever reached the provider


def test_claim_blocks_concurrent_scheduler_run(seeded, db):
    rep = _fresh_report(db)
    rep.status = "sending"
    db.commit()
    calls = []
    out = send_daily_report(db, rep, settings=_smtp_settings(), sender=lambda m, st: calls.append(1) or "x", sleep=lambda x: None)
    assert out.status == "skipped_duplicate" and calls == []


def test_not_configured_is_recorded_honestly_not_as_sent(seeded, db):
    rep = _fresh_report(db)
    out = send_daily_report(db, rep, settings=get_settings().model_copy(update={"smtp_host": ""}), sleep=lambda x: None)
    assert out.status == "not_configured"
    db.refresh(rep)
    assert rep.status == "no_email_config"


def test_failure_notice_goes_to_backup_only_when_configured(seeded, db):
    rep = _fresh_report(db)
    sent_to = []
    def always_fail(msg, settings):
        sent_to.append(msg["To"])
        raise smtplib.SMTPServerDisconnected("down (mock)")
    s_no_backup = _smtp_settings(email_max_retries=0, backup_recipient="")
    send_daily_report(db, rep, settings=s_no_backup, sender=always_fail, sleep=lambda x: None, force=True)
    assert sent_to == ["kptcc@gmail.com"]
    sent_to.clear()
    s_backup = _smtp_settings(email_max_retries=0, backup_recipient="backup-admin@test.invalid")
    rep2 = _fresh_report(db)
    send_daily_report(db, rep2, settings=s_backup, sender=always_fail, sleep=lambda x: None, force=True)
    assert "backup-admin@test.invalid" in sent_to


def test_test_email_contains_no_school_data(seeded, db):
    captured = {}
    def capture(msg, settings):
        captured["text"] = msg.get_body(preferencelist=("plain",)).get_content()
        return "ok (mock)"
    out = send_test_email(db, settings=_smtp_settings(), sender=capture, sleep=lambda x: None)
    assert out.status == "accepted"
    assert "contains no school data" in captured["text"]


def test_send_with_retries_gives_up_after_max_attempts(seeded):
    calls = []
    def boom(msg, settings):
        calls.append(1)
        raise TimeoutError("mock timeout")
    msg = build_message(to="a@test.invalid", subject="s", text="t", html="<p>t</p>", settings=_smtp_settings())
    status, attempts, _ = send_with_retries(msg, _smtp_settings(email_max_retries=2), sender=boom, sleep=lambda x: None)
    assert status == "failed" and attempts == 3 and len(calls) == 3
