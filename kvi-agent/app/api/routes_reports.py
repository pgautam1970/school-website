"""Daily reports, archive search, action tracker, email delivery endpoints.

Access model
- staff: source registry, imports, redacted archive search.
- leadership: reports, PDF/HTML export (audited), action tracker updates,
  email logs, original-text reveal in the archive (audited).
- admin: resend, test email, Facebook API sync, users, settings, audit log, retention.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import String, func, or_, select
from sqlalchemy.orm import Session

from ..analysis.pipeline import day_window_utc
from ..config import CLASS_LEVELS, GROUP_CATEGORIES, PRIORITY_LEVELS, get_settings
from ..db import get_db
from ..delivery.email_sender import send_daily_report, send_test_email
from ..models import ActionItem, DailyReport, EmailLog, Message, User, WhatsAppGroup
from ..security import audit, require_role
from ..services import generate_and_send

router = APIRouter(prefix="/api", tags=["reports"])


class ConfirmIn(BaseModel):
    confirm: bool = False
    report_date: str | None = None
    send: bool = True


def _need_confirm(body: ConfirmIn | None) -> None:
    if not body or not body.confirm:
        raise HTTPException(409, "Confirmation required: resend {'confirm': true} to proceed.")


def _report_summary(r: DailyReport) -> dict:
    return {"id": r.id, "report_uid": r.report_uid, "report_date": r.report_date,
            "nepali_date": r.nepali_date, "generated_at": r.generated_at.isoformat() if r.generated_at else None,
            "engine": r.engine, "status": r.status, "pdf_available": bool(r.pdf_path and Path(r.pdf_path).is_file()),
            "pdf_engine": r.pdf_engine, "is_regeneration": r.is_regeneration,
            "counts": (r.data or {}).get("counts", {}), "coverage": {
                "groups_with_data": (r.coverage or {}).get("groups_with_data"),
                "groups_total": (r.coverage or {}).get("groups_total")},
            "pdf_error": (r.data or {}).get("pdf_error", "")}


@router.post("/reports/generate")
def generate(body: ConfirmIn | None = None, db: Session = Depends(get_db),
             user: User = Depends(require_role("leadership"))):
    """Generate Today's Report (Asia/Kathmandu). Sends only when body.send is true."""
    _need_confirm(body)
    npt_today = datetime.now(ZoneInfo(get_settings().timezone)).date().isoformat()
    day = (body.report_date or npt_today)
    try:
        date.fromisoformat(day)
    except ValueError:
        raise HTTPException(422, "report_date must be YYYY-MM-DD")
    result = generate_and_send(db, day, send=body.send, kind="regenerate", actor=user.username)
    return result


@router.get("/reports")
def list_reports(limit: int = Query(60, le=365), db: Session = Depends(get_db),
                 user: User = Depends(require_role("leadership"))):
    rows = list(db.scalars(select(DailyReport).order_by(DailyReport.report_date.desc()).limit(limit)))
    return [_report_summary(r) for r in rows]


@router.get("/reports/by-date/{day}")
def report_by_date(day: str, db: Session = Depends(get_db), user: User = Depends(require_role("leadership"))):
    r = db.scalar(select(DailyReport).where(DailyReport.report_date == day))
    if not r:
        raise HTTPException(404, "No report generated for this date yet")
    audit(db, user.username, "report_view", f"{day} uid={r.report_uid}")
    return {**_report_summary(r), "data": r.data}


@router.get("/reports/{report_id}/html", response_class=HTMLResponse)
def report_html(report_id: int, db: Session = Depends(get_db), user: User = Depends(require_role("leadership"))):
    r = db.get(DailyReport, report_id)
    if not r:
        raise HTTPException(404)
    audit(db, user.username, "report_export_html", f"uid={r.report_uid}")
    return HTMLResponse(r.html or "<p>Not rendered</p>")


@router.get("/reports/{report_id}/pdf")
def report_pdf(report_id: int, db: Session = Depends(get_db), user: User = Depends(require_role("leadership"))):
    r = db.get(DailyReport, report_id)
    if not r or not r.pdf_path or not Path(r.pdf_path).is_file():
        raise HTTPException(404, "PDF not available for this report")
    audit(db, user.username, "report_export_pdf", f"uid={r.report_uid}")
    return FileResponse(r.pdf_path, media_type="application/pdf", filename=Path(r.pdf_path).name)


@router.post("/reports/{report_id}/resend")
def resend(report_id: int, body: ConfirmIn, db: Session = Depends(get_db),
           user: User = Depends(require_role("admin"))):
    _need_confirm(body)
    r = db.get(DailyReport, report_id)
    if not r:
        raise HTTPException(404)
    outcome = send_daily_report(db, r, kind="resend", force=True)
    audit(db, user.username, "report_resend", f"uid={r.report_uid} outcome={outcome.status}")
    return {"status": outcome.status, "attempts": outcome.attempts, "detail": outcome.message}


@router.post("/email/test")
def email_test(body: ConfirmIn, db: Session = Depends(get_db), user: User = Depends(require_role("admin"))):
    _need_confirm(body)
    outcome = send_test_email(db)
    audit(db, user.username, "email_test", f"outcome={outcome.status}")
    return {"status": outcome.status, "attempts": outcome.attempts, "detail": outcome.message,
            "to": get_settings().report_recipient}


@router.get("/email/logs")
def email_logs(limit: int = Query(200, le=1000), db: Session = Depends(get_db),
               user: User = Depends(require_role("leadership"))):
    rows = db.scalars(select(EmailLog).order_by(EmailLog.created_at.desc()).limit(limit))
    return [{"id": e.id, "report_uid": e.report_uid, "attempt": e.attempt, "kind": e.kind,
             "to": e.to_addr, "subject": e.subject, "status": e.status,
             "provider_response": e.provider_response, "has_pdf": e.has_pdf,
             "created_at": e.created_at.isoformat()} for e in rows]


# ----------------------------------------------------------------- archive
@router.get("/archive")
def archive(q: str = "", date_from: str | None = None, date_to: str | None = None,
            class_level: str | None = None, group_id: int | None = None,
            priority: str | None = None, category: str | None = None,
            reveal: bool = False, limit: int = Query(50, le=200), offset: int = 0,
            db: Session = Depends(get_db), user: User = Depends(require_role("staff"))):
    """Searchable communication archive. Staff see redacted text; leadership may
    reveal original text (audited). Original text is never shown to staff."""
    if reveal and user.role not in ("leadership", "admin"):
        raise HTTPException(403, "Revealing original text requires leadership role")
    tz = ZoneInfo(get_settings().timezone)
    stmt = select(Message, WhatsAppGroup).join(WhatsAppGroup, Message.group_id == WhatsAppGroup.id)
    if date_from:
        start, _ = day_window_utc(date_from)
        stmt = stmt.where(Message.ts_original >= start)
    if date_to:
        _, end = day_window_utc(date_to)
        stmt = stmt.where(Message.ts_original < end)
    if group_id:
        stmt = stmt.where(Message.group_id == group_id)
    if priority:
        if priority not in PRIORITY_LEVELS:
            raise HTTPException(422, "invalid priority")
        stmt = stmt.where(Message.priority == priority)
    if class_level:
        if class_level not in CLASS_LEVELS:
            raise HTTPException(422, "invalid class level")
        stmt = stmt.where(WhatsAppGroup.class_level == class_level)
    if category:
        stmt = stmt.where(Message.categories.cast(String).like(f'%"{category}"%'))
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(Message.text_normalized).like(like),
                              func.lower(Message.sender_label).like(like)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(stmt.order_by(Message.ts_original.desc()).limit(limit).offset(offset)).all()
    items = []
    for m, g in rows:
        item = {"id": m.id, "group": g.name, "class_level": g.class_level, "category_group": g.category,
                "ts_original": m.ts_original.astimezone(tz).strftime("%Y-%m-%d %H:%M NPT"),
                "sender": m.sender_label if (user.role in ("leadership", "admin")) else _mask_sender(m.sender_label),
                "sender_kind": m.sender_kind, "categories": m.categories, "priority": m.priority,
                "priority_reason": m.priority_reason, "activity_status": m.activity_status,
                "language": m.language, "confidence": m.confidence, "is_question": m.is_question,
                "question_answered": m.question_answered, "media_kind": m.media_kind,
                "text": m.text_redacted, "text_is_original": False}
        if reveal:
            item["text"] = m.text_original
            item["text_is_original"] = True
        items.append(item)
    if reveal:
        audit(db, user.username, "archive_reveal_original", f"q={q[:80]} count={len(items)}")
    return {"total": total, "items": items, "limit": limit, "offset": offset,
            "filters": {"q": q, "date_from": date_from, "date_to": date_to, "class_level": class_level,
                        "group_id": group_id, "priority": priority, "category": category},
            "redacted_view": not reveal}


def _mask_sender(label: str) -> str:
    """Staff view: keep the role-relevant first word, mask the rest."""
    if not label:
        return ""
    first = label.split()[0]
    return (first[:1] + "•••") if len(first) > 1 else "•••"


# --------------------------------------------------------------- actions
class ActionPatch(BaseModel):
    status: str | None = None
    resolution_notes: str | None = Field(default=None, max_length=2000)
    suggested_role: str | None = None


@router.get("/actions")
def list_actions(status: str | None = None, priority: str | None = None, date_: str | None = Query(None, alias="date"),
                 db: Session = Depends(get_db), user: User = Depends(require_role("leadership"))):
    stmt = select(ActionItem).order_by(ActionItem.report_date.desc(), ActionItem.priority)
    if status:
        stmt = stmt.where(ActionItem.status == status)
    if priority:
        stmt = stmt.where(ActionItem.priority == priority)
    if date_:
        stmt = stmt.where(ActionItem.report_date == date_)
    return [{"id": a.id, "action_id": a.action_id, "report_date": a.report_date, "title": a.title,
             "detail": a.detail, "evidence": a.evidence, "priority": a.priority,
             "suggested_role": a.suggested_role, "deadline": a.deadline, "status": a.status,
             "resolution_notes": a.resolution_notes,
             "updated_at": a.updated_at.isoformat() if a.updated_at else None}
            for a in db.scalars(stmt.limit(500))]


@router.patch("/actions/{action_id}")
def update_action(action_id: int, body: ActionPatch, db: Session = Depends(get_db),
                  user: User = Depends(require_role("leadership"))):
    a = db.get(ActionItem, action_id)
    if not a:
        raise HTTPException(404)
    if body.status is not None:
        if body.status not in ("open", "in_progress", "resolved", "dismissed"):
            raise HTTPException(422, "invalid status")
        a.status = body.status
    if body.resolution_notes is not None:
        a.resolution_notes = body.resolution_notes
    if body.suggested_role is not None:
        a.suggested_role = body.suggested_role
    db.commit()
    audit(db, user.username, "action_updated", f"{a.action_id} status={a.status}")
    return {"ok": True, "action_id": a.action_id, "status": a.status}


@router.get("/meta")
def meta(user: User = Depends(require_role("staff"))):
    s = get_settings()
    return {"school": s.school_name, "address": s.school_address, "website": s.school_website,
            "classes": CLASS_LEVELS, "categories": GROUP_CATEGORIES, "priorities": PRIORITY_LEVELS,
            "timezone": s.timezone, "role": user.role, "username": user.username}
