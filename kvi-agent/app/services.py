"""Application services used by both the API and the scheduler/CLI.

Keeping this logic out of the route handlers makes every step testable and lets
the same code run from the dashboard, the scheduler, n8n (via the API) or the CLI.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import (AuditLog, DailyReport, EmailLog, FacebookComment, FacebookPage,
                     FacebookPost, Message, SyncLog, User, WhatsAppGroup, utcnow)
from .security import audit, hash_password

log = logging.getLogger("kvi.services")


def ensure_bootstrap(db: Session) -> None:
    """Create the first admin on an empty database. Requires KVI_ADMIN_PASSWORD;
    never creates a user with a default or empty password."""
    s = get_settings()
    if db.scalar(select(User.id).limit(1)) is not None:
        return
    if not s.admin_password or s.admin_password.startswith("CHANGE_ME"):
        log.warning("No users exist and KVI_ADMIN_PASSWORD is not set; no admin created. "
                    "Set KVI_ADMIN_PASSWORD in .env and restart.")
        return
    db.add(User(username=s.admin_username, full_name="System Administrator",
                password_hash=hash_password(s.admin_password), role="admin"))
    db.commit()
    audit(db, "system", "bootstrap_admin_created", s.admin_username)


def generate_and_send(db: Session, report_date: str, *, send: bool, kind: str = "daily",
                      force: bool = False, actor: str = "system") -> dict:
    """Run pipeline -> PDF -> (optional) email. Returns a status summary."""
    from .analysis.pipeline import run_pipeline
    from .delivery.email_sender import send_daily_report
    report = run_pipeline(db, report_date, regenerate=kind == "regenerate")
    audit(db, actor, "report_generated", f"{report_date} uid={report.report_uid} engine={report.engine}")
    outcome = None
    if send:
        outcome = send_daily_report(db, report, kind=("resend" if kind == "resend" else "daily"),
                                    force=force)
        audit(db, actor, "report_send", f"{report_date} outcome={outcome.status}")
    return {
        "report_date": report_date,
        "report_uid": report.report_uid,
        "report_id": report.id,
        "engine": report.engine,
        "generated": True,
        "pdf": bool(report.pdf_path),
        "pdf_error": report.data.get("pdf_error", ""),
        "send_status": outcome.status if outcome else "not_requested",
        "send_detail": outcome.message if outcome else "",
        "report_status": report.status,
    }


def purge_expired(db: Session, *, retention_days: int | None = None, actor: str = "system") -> dict:
    """Delete raw WhatsApp message content and Facebook comments older than the retention
    window. Aggregated daily reports, action items and email logs are kept (they are the
    school's record) — the retention setting is documented accordingly."""
    days = retention_days if retention_days is not None else get_settings().retention_days
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    m = db.execute(delete(Message).where(Message.ts_original < cutoff)).rowcount or 0
    c = db.execute(delete(FacebookComment).where(FacebookComment.created_at < cutoff)).rowcount or 0
    p = db.execute(delete(FacebookPost).where(FacebookPost.published_at < cutoff,
                                              FacebookPost.source_kind == "api")).rowcount or 0
    db.commit()
    audit(db, actor, "retention_purge", f"days={days} messages={m} comments={c} fb_posts={p}")
    return {"retention_days": days, "messages_deleted": m, "fb_comments_deleted": c,
            "fb_posts_deleted": p}


def source_health(db: Session) -> dict:
    """Honest per-source status for the dashboard. Nothing is assumed connected."""
    s = get_settings()
    groups = list(db.scalars(select(WhatsAppGroup).order_by(WhatsAppGroup.name)))
    npt = ZoneInfo(s.timezone)
    today = datetime.now(npt).date()
    start_local = datetime(today.year, today.month, today.day, tzinfo=npt)
    start_utc = start_local.astimezone(timezone.utc)
    per_group_today = {}
    for gid, cnt in db.execute(select(Message.group_id, func.count())
                               .where(Message.ts_original >= start_utc)
                               .group_by(Message.group_id)).all():
        per_group_today[gid] = cnt
    last_sync_failures = list(db.scalars(select(SyncLog).where(SyncLog.status == "failed")
                                         .order_by(SyncLog.started_at.desc()).limit(10)))
    return {
        "groups": [{
            "id": g.id, "name": g.name, "category": g.category, "class_level": g.class_level,
            "academic_year": g.academic_year, "group_admin": g.group_admin,
            "collection_method": g.collection_method,
            "active": g.is_active, "archived": g.archived,
            "include_in_reporting": g.include_in_reporting,
            "authorization_noted": g.authorization_noted,
            "last_sync_at": _iso(g.last_sync_at), "last_message_at": _iso(g.last_message_at),
            "messages_today": per_group_today.get(g.id, 0),
            "import_status": ("archived" if g.archived else "inactive" if not g.is_active else
                              ("data_received_today" if per_group_today.get(g.id) else
                               ("never_imported" if g.last_sync_at is None else "no_data_today"))),
        } for g in groups],
        "groups_configured": len([g for g in groups if g.is_active and not g.archived]),
        "groups_synced_today": len([g for g in groups if per_group_today.get(g.id)]),
        "failed_recent": [{"source": x.source_name, "kind": x.source_kind, "error": x.error,
                           "at": _iso(x.started_at)} for x in last_sync_failures],
        "last_successful_collection": _iso(db.scalar(
            select(SyncLog.finished_at).where(SyncLog.status == "success",
                                              SyncLog.source_kind.in_(["whatsapp", "facebook"]))
            .order_by(SyncLog.finished_at.desc()).limit(1))),
        "today_npt": today.isoformat(),
    }


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ZoneInfo(get_settings().timezone)).strftime("%Y-%m-%d %H:%M NPT")
