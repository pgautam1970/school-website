"""Users, settings, audit, retention, scheduler, health and dashboard summary."""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ..analysis.pipeline import day_window_utc
from ..config import PRIORITY_LEVELS, SUGGESTED_ROLES, get_settings
from ..db import get_db
from ..models import ActionItem, AppSetting, AuditLog, DailyReport, EmailLog, Message, SyncLog, User, WhatsAppGroup
from ..reports.pdf import _find_font
from ..scheduler import scheduler_status
from ..security import ROLE_LEVELS, audit, hash_password, require_role
from ..services import purge_expired, source_health
from .routes_reports import ConfirmIn, _need_confirm

router = APIRouter(prefix="/api", tags=["admin"])
ROLES = list(ROLE_LEVELS.keys())


# ----------------------------------------------------------------- users
class UserIn(BaseModel):
    username: str = Field(min_length=3, max_length=80, pattern=r"^[a-zA-Z0-9_.-]+$")
    full_name: str = Field(default="", max_length=160)
    role: str
    password: str = Field(min_length=12, max_length=256)


class UserPatch(BaseModel):
    full_name: str | None = None
    role: str | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=12, max_length=256)


@router.get("/users")
def list_users(db: Session = Depends(get_db), user: User = Depends(require_role("admin"))):
    return [{"id": u.id, "username": u.username, "full_name": u.full_name, "role": u.role,
             "is_active": u.is_active} for u in db.scalars(select(User).order_by(User.username))]


@router.post("/users", status_code=201)
def create_user(body: UserIn, db: Session = Depends(get_db), user: User = Depends(require_role("admin"))):
    if body.role not in ROLES:
        raise HTTPException(422, f"role must be one of {ROLES}")
    if db.scalar(select(User).where(User.username == body.username)):
        raise HTTPException(409, "username exists")
    u = User(username=body.username, full_name=body.full_name, role=body.role,
             password_hash=hash_password(body.password))
    db.add(u)
    db.commit()
    audit(db, user.username, "user_created", f"{u.username} role={u.role}")
    return {"id": u.id, "username": u.username, "role": u.role}


@router.patch("/users/{user_id}")
def update_user(user_id: int, body: UserPatch, db: Session = Depends(get_db),
                user: User = Depends(require_role("admin"))):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404)
    if body.role is not None and body.role not in ROLES:
        raise HTTPException(422, "invalid role")
    if u.id == user.id and (body.is_active is False or (body.role and body.role != "admin")):
        raise HTTPException(422, "You cannot disable or demote your own admin account")
    if body.full_name is not None:
        u.full_name = body.full_name
    if body.role is not None:
        u.role = body.role
    if body.is_active is not None:
        u.is_active = body.is_active
    if body.password:
        u.password_hash = hash_password(body.password)
    db.commit()
    audit(db, user.username, "user_updated", f"{u.username} role={u.role} active={u.is_active}")
    return {"ok": True}


# ------------------------------------------------------- runtime settings
class SettingsIn(BaseModel):
    retention_days: int | None = Field(default=None, ge=30, le=3650)
    redact_in_summaries: bool | None = None


@router.get("/settings")
def get_app_settings(db: Session = Depends(get_db), user: User = Depends(require_role("admin"))):
    s = get_settings()
    stored = {r.key: r.value for r in db.scalars(select(AppSetting))}
    return {
        "scheduler": scheduler_status(),
        "scheduler_note": "Schedule values come from .env (KVI_REPORT_HOUR/MINUTE, KVI_TIMEZONE). "
                          "Change them there and restart the service.",
        "retention_days": stored.get("retention_days", {}).get("v", s.retention_days),
        "redact_in_summaries": stored.get("redact_in_summaries", {}).get("v", s.redact_in_summaries),
        "report_recipient": s.report_recipient,
        "backup_recipient": s.backup_recipient or "(disabled — not configured)",
        "email_configured": s.email_configured,
        "priorities": PRIORITY_LEVELS,
        "suggested_roles": SUGGESTED_ROLES,
    }


@router.put("/settings")
def put_app_settings(body: SettingsIn, db: Session = Depends(get_db), user: User = Depends(require_role("admin"))):
    changes = body.model_dump(exclude_none=True)
    for k, v in changes.items():
        row = db.get(AppSetting, k) or AppSetting(key=k)
        row.value = {"v": v}
        db.add(row)
    db.commit()
    audit(db, user.username, "settings_updated", str(changes))
    return {"ok": True, "changed": sorted(changes)}


class RetentionIn(ConfirmIn):
    retention_days: int | None = None


@router.post("/retention/purge")
def retention_purge(body: RetentionIn, db: Session = Depends(get_db), user: User = Depends(require_role("admin"))):
    _need_confirm(body)
    stored = db.get(AppSetting, "retention_days")
    days = body.retention_days or (stored.value.get("v") if stored else None)
    return purge_expired(db, retention_days=days, actor=user.username)


# ------------------------------------------------------------- audit
@router.get("/audit")
def audit_log(limit: int = Query(200, le=1000), action: str | None = None,
              db: Session = Depends(get_db), user: User = Depends(require_role("admin"))):
    q = select(AuditLog).order_by(AuditLog.ts.desc()).limit(limit)
    if action:
        q = q.where(AuditLog.action == action)
    return [{"ts": a.ts.isoformat(), "user": a.username, "action": a.action, "detail": a.detail}
            for a in db.scalars(q)]


# ------------------------------------------------------- scheduler + health
@router.get("/scheduler")
def scheduler(user: User = Depends(require_role("staff"))):
    return scheduler_status()


@router.post("/scheduler/watch-now")
def watch_now(body: ConfirmIn, db: Session = Depends(get_db), user: User = Depends(require_role("admin"))):
    _need_confirm(body)
    from ..connectors.whatsapp_ingest import scan_watch_folder
    res = scan_watch_folder(db)
    audit(db, user.username, "watch_scan_manual", f"files={len(res)}")
    return {"results": res}


@router.get("/health")
def health(db: Session = Depends(get_db)):
    """Public liveness/readiness probe: no secrets, no school data."""
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return {"status": "ok" if db_ok else "degraded", "database": "ok" if db_ok else "unreachable",
            "time_npt": datetime.now(ZoneInfo(get_settings().timezone)).strftime("%Y-%m-%d %H:%M:%S %Z")}


@router.get("/system")
def system(db: Session = Depends(get_db), user: User = Depends(require_role("leadership"))):
    s = get_settings()
    font, dev = _find_font()
    last_report = db.scalar(select(DailyReport).order_by(DailyReport.report_date.desc()).limit(1))
    recent_failures = list(db.scalars(select(SyncLog).where(SyncLog.status == "failed")
                                      .order_by(SyncLog.started_at.desc()).limit(10)))
    email_fail = db.scalar(select(func.count()).select_from(EmailLog).where(EmailLog.status == "failed"))
    return {
        "config_checks": s.validation_report(),
        "scheduler": scheduler_status(),
        "database": s.database_url.split("://")[0],
        "pdf": {"fallback_font": font or "none", "devanagari_font": dev,
                "engine": "fpdf2"},
        "ai": {"configured": s.ai_configured, "engine_when_unconfigured": "rules"},
        "email": {"configured": s.email_configured, "failed_attempts_total": email_fail or 0,
                  "backup_enabled": bool(s.backup_recipient)},
        "facebook": {"configured": s.facebook_configured},
        "last_report": {"date": last_report.report_date, "status": last_report.status,
                        "uid": last_report.report_uid} if last_report else None,
        "recent_failures": [{"source": f.source_name, "kind": f.source_kind, "error": f.error,
                             "at": f.started_at.isoformat()} for f in recent_failures],
    }


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(require_role("staff"))):
    """Overview indicators. Every number is computed from stored data, never estimated."""
    s = get_settings()
    health_ = source_health(db)
    npt = ZoneInfo(s.timezone)
    today = datetime.now(npt).date().isoformat()
    start, end = day_window_utc(today)
    msgs_today = db.scalar(select(func.count()).select_from(Message).where(
        Message.ts_original >= start, Message.ts_original < end)) or 0
    high = db.scalar(select(func.count()).select_from(Message).where(
        Message.ts_original >= start, Message.ts_original < end,
        Message.priority.in_(["CRITICAL", "HIGH"]))) or 0
    open_actions = db.scalar(select(func.count()).select_from(ActionItem).where(ActionItem.status.in_(["open", "in_progress"]))) or 0
    last_report = db.scalar(select(DailyReport).order_by(DailyReport.report_date.desc()).limit(1))
    demo = db.get(AppSetting, "demo_data")
    return {
        "demo_data": bool(demo and demo.value.get("v")),
        "today_npt": today,
        "configured_sources": health_["groups_configured"] + 1,
        "whatsapp_groups_configured": health_["groups_configured"],
        "whatsapp_groups_synced_today": health_["groups_synced_today"],
        "facebook_configured": s.facebook_configured,
        "messages_today": msgs_today,
        "high_priority_today": high,
        "open_actions": open_actions,
        "failed_connections_recent": len(health_["failed_recent"]),
        "last_successful_collection": health_["last_successful_collection"],
        "latest_report": {"date": last_report.report_date, "status": last_report.status,
                          "engine": last_report.engine} if last_report else None,
        "next_report_at": scheduler_status()["next_report_at_npt"],
        "email_configured": s.email_configured,
        "priorities": PRIORITY_LEVELS,
    }
