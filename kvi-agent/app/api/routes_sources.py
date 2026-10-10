"""Source registry (WhatsApp groups), imports, Facebook connector endpoints."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import GROUP_CATEGORIES, CLASS_LEVELS, get_settings
from ..connectors.facebook_graph import FacebookGraphClient
from ..connectors.facebook_ingest import manual_import, sync_from_api
from ..connectors.whatsapp_ingest import find_group_for_filename, import_export_text, scan_watch_folder
from ..db import get_db
from ..models import FacebookPage, User, WhatsAppGroup
from ..security import audit, require_role
from ..services import source_health

router = APIRouter(prefix="/api", tags=["sources"])
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB per export file
ALLOWED_METHODS = {"export_upload", "watch_folder", "manual"}


class GroupIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    category: str = "Other"
    class_level: str = ""
    academic_year: str = Field(default="", max_length=20)
    group_admin: str = Field(default="", max_length=120)
    collection_method: str = "export_upload"
    include_in_reporting: bool = True
    authorization_noted: bool = False


class GroupPatch(BaseModel):
    name: str | None = None
    category: str | None = None
    class_level: str | None = None
    academic_year: str | None = None
    group_admin: str | None = None
    collection_method: str | None = None
    include_in_reporting: bool | None = None
    is_active: bool | None = None
    archived: bool | None = None
    authorization_noted: bool | None = None


def _validate_group(data: dict) -> None:
    if "category" in data and data["category"] not in GROUP_CATEGORIES:
        raise HTTPException(422, f"category must be one of: {', '.join(GROUP_CATEGORIES)}")
    if data.get("class_level") not in (None, "") and data["class_level"] not in CLASS_LEVELS:
        raise HTTPException(422, f"class_level must be one of: {', '.join(CLASS_LEVELS)}")
    if "collection_method" in data and data["collection_method"] not in ALLOWED_METHODS:
        raise HTTPException(422, f"collection_method must be one of: {', '.join(sorted(ALLOWED_METHODS))}")


def _group_out(g: WhatsAppGroup) -> dict:
    return {"id": g.id, "name": g.name, "category": g.category, "class_level": g.class_level,
            "academic_year": g.academic_year, "group_admin": g.group_admin,
            "collection_method": g.collection_method, "include_in_reporting": g.include_in_reporting,
            "is_active": g.is_active, "archived": g.archived,
            "authorization_noted": g.authorization_noted,
            "last_sync_at": g.last_sync_at.isoformat() if g.last_sync_at else None,
            "last_message_at": g.last_message_at.isoformat() if g.last_message_at else None}


@router.get("/sources")
def sources(db: Session = Depends(get_db), user: User = Depends(require_role("staff"))):
    """Honest per-source status including Facebook connection state."""
    health = source_health(db)
    fb = FacebookGraphClient().status(timeout=6)
    page = db.scalar(select(FacebookPage).where(FacebookPage.is_active == True))  # noqa: E712
    health["facebook"] = {
        "configured": fb.configured, "connected": fb.connected, "detail": fb.detail,
        "page_name": fb.page_name, "page_url": fb.page_url or get_settings().fb_page_url,
        "last_sync_at": page.last_sync_at.isoformat() if page and page.last_sync_at else None,
        "last_error": page.last_error if page else "",
        "page_url_verified": bool(fb.connected and fb.page_url),
    }
    health["whatsapp"] = {
        "live_api_connected": False,
        "mode": "Authorized chat exports (upload or watch folder). The WhatsApp Business Platform API "
                "does not provide access to existing class/teacher group histories, and this system "
                "does not use scraping or session-based access.",
    }
    return health


@router.get("/groups")
def list_groups(include_archived: bool = False, db: Session = Depends(get_db),
                user: User = Depends(require_role("staff"))):
    q = select(WhatsAppGroup).order_by(WhatsAppGroup.name)
    if not include_archived:
        q = q.where(WhatsAppGroup.archived == False)  # noqa: E712
    return [_group_out(g) for g in db.scalars(q)]


@router.post("/groups", status_code=201)
def create_group(body: GroupIn, db: Session = Depends(get_db), user: User = Depends(require_role("leadership"))):
    data = body.model_dump()
    _validate_group(data)
    if db.scalar(select(WhatsAppGroup).where(WhatsAppGroup.name == body.name)):
        raise HTTPException(409, "A group with this name already exists")
    g = WhatsAppGroup(**data)
    db.add(g)
    db.commit()
    audit(db, user.username, "group_created", f"{g.name} method={g.collection_method}")
    return _group_out(g)


@router.patch("/groups/{group_id}")
def update_group(group_id: int, body: GroupPatch, db: Session = Depends(get_db),
                 user: User = Depends(require_role("leadership"))):
    g = db.get(WhatsAppGroup, group_id)
    if not g:
        raise HTTPException(404, "Group not found")
    changes = body.model_dump(exclude_none=True)
    _validate_group(changes)
    for k, v in changes.items():
        setattr(g, k, v)
    if g.archived:
        g.is_active = False
        g.include_in_reporting = False
    db.commit()
    audit(db, user.username, "group_updated", f"id={g.id} changes={sorted(changes)}")
    return _group_out(g)


@router.post("/imports/whatsapp")
async def import_whatsapp(group_id: int = Form(...), file: UploadFile = File(...),
                          db: Session = Depends(get_db), user: User = Depends(require_role("staff"))):
    """Upload one authorized WhatsApp chat export (.txt) for a registered group."""
    g = db.get(WhatsAppGroup, group_id)
    if not g or g.archived:
        raise HTTPException(404, "Group not found or archived")
    if not (file.filename or "").lower().endswith(".txt"):
        raise HTTPException(422, "Only WhatsApp exported .txt files are accepted")
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File too large (max 5 MB)")
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        content = raw.decode("utf-8", errors="replace")
    stats = import_export_text(db, g, content, import_label="manual_upload")
    audit(db, user.username, "whatsapp_import", f"group={g.name} file={file.filename} new={stats['new']} dup={stats['duplicate']}")
    return {**stats, "file": file.filename, "source_method": "manual_upload"}


@router.post("/imports/whatsapp/suggest-group")
async def suggest_group(filename: str = Form(...), db: Session = Depends(get_db),
                        user: User = Depends(require_role("staff"))):
    g = find_group_for_filename(db, filename)
    return {"group_id": g.id if g else None, "group_name": g.name if g else None}


@router.post("/imports/watch-folder/scan")
def scan_watch(db: Session = Depends(get_db), user: User = Depends(require_role("admin"))):
    results = scan_watch_folder(db)
    audit(db, user.username, "watch_folder_scan", f"files={len(results)}")
    return {"results": results}


class FbManualIn(BaseModel):
    url: str = Field(default="", max_length=400)
    text: str = Field(min_length=3, max_length=8000)
    published_at: datetime | None = None
    reactions: int | None = Field(default=None, ge=0)
    comments_count: int | None = Field(default=None, ge=0)


@router.post("/facebook/manual-post")
def fb_manual(body: FbManualIn, db: Session = Depends(get_db), user: User = Depends(require_role("staff"))):
    res = manual_import(db, body.url, body.text, body.published_at, body.reactions,
                        body.comments_count, imported_by=user.username)
    if not res.get("ok"):
        raise HTTPException(422, res.get("error", "import failed"))
    audit(db, user.username, "facebook_manual_import", f"post_id={res['post_id']}")
    return res


@router.post("/facebook/sync")
def fb_sync(db: Session = Depends(get_db), user: User = Depends(require_role("admin"))):
    res = sync_from_api(db, days=1)
    audit(db, user.username, "facebook_sync", "ok" if res.get("ok") else f"error={res.get('error')}")
    return res
