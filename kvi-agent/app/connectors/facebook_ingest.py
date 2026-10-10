"""Facebook ingestion: store API-fetched or manually-imported page posts.

Manual import is the sanctioned fallback for anything the connected API cannot
retrieve (or when the API is not configured). Manually imported posts are
labelled source_kind='manual' and the report states that engagement figures
for them were provided by staff, not measured by Meta.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..analysis.classify import classify
from ..analysis.normalize import detect_language, normalize_text
from ..analysis.priority import assess_priority
from ..models import FacebookComment, FacebookPage, FacebookPost, SyncLog
from .facebook_graph import FacebookGraphClient

URL_RE = re.compile(r"^https?://[^\s<>\"']+$")


def _ensure_page(db: Session) -> FacebookPage:
    page = db.scalar(select(FacebookPage).where(FacebookPage.is_active == True))  # noqa: E712
    if not page:
        page = FacebookPage(name="Kashyap Vidyapeeth Inaruwa")
        db.add(page)
        db.commit()
    return page


def _analyze_post(post: FacebookPost, message: str) -> None:
    norm = normalize_text(message)
    cls = classify(norm, sender_kind="teacher", group_category="Administration & Management")
    pr = assess_priority(norm, cls.categories)
    post.categories = cls.categories
    post.priority = pr.priority


def sync_from_api(db: Session, days: int = 1) -> dict:
    """Fetch recent posts via the Graph API. Honest error propagation."""
    page = _ensure_page(db)
    client = FacebookGraphClient()
    log = SyncLog(source_kind="facebook", source_name=page.name or "Facebook Page")
    db.add(log)
    until = datetime.now(timezone.utc)
    since = until - timedelta(days=days)
    posts, error = client.fetch_posts(since, until)
    if error:
        log.status = "failed"
        log.error = error
        log.finished_at = datetime.now(timezone.utc)
        page.last_error = error
        db.commit()
        return {"ok": False, "error": error}

    existing = set(db.scalars(select(FacebookPost.fb_post_id)))
    new = comments_total = 0
    for p in posts:
        pid = p.get("id", "")
        if not pid or pid in existing:
            continue
        shares = (p.get("shares") or {}).get("count")
        pub = p.get("created_time")
        post = FacebookPost(
            page_id=page.id, fb_post_id=pid,
            message=p.get("message", "") or "",
            permalink=p.get("permalink_url", "") or f"https://facebook.com/{pid.replace('_', '/posts/')}",
            published_at=datetime.fromisoformat(pub.replace("Z", "+00:00")) if pub else None,
            shares=shares,
            media_metadata={"status_type": p.get("status_type"), "has_picture": bool(p.get("full_picture"))},
            source_kind="api", raw={k: v for k, v in p.items() if k != "attachment"},
        )
        _analyze_post(post, post.message)
        db.add(post)
        db.flush()
        new += 1
        post_comments = 0
        for c in client.fetch_comments(pid):
            db.add(FacebookComment(
                post_id=post.id, fb_comment_id=c.get("id", ""),
                from_name=(c.get("from") or {}).get("name", ""),
                message=c.get("message", ""),
                created_at=datetime.fromisoformat(c["created_time"].replace("Z", "+00:00")) if c.get("created_time") else None,
                is_question="?" in c.get("message", ""),
            ))
            comments_total += 1
            post_comments += 1
        post.comments_count = post_comments
        post.reactions = client.fetch_reaction_count(pid)
    page.last_sync_at = datetime.now(timezone.utc)
    page.last_error = ""
    log.status = "success"
    log.items_seen = len(posts)
    log.items_new = new
    log.finished_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True, "posts_fetched": len(posts), "posts_new": new, "comments_fetched": comments_total}


def manual_import(db: Session, url: str, text: str, published_at: datetime | None = None,
                  reactions: int | None = None, comments_count: int | None = None,
                  imported_by: str = "staff") -> dict:
    """Staff-provided fallback import. URL must be a plain http(s) link
    (validated; never fetched server-side automatically, never executed)."""
    url = (url or "").strip()
    text = (text or "").strip()
    if not text:
        return {"ok": False, "error": "Post text is required for manual import."}
    if url and not URL_RE.match(url):
        return {"ok": False, "error": "Invalid URL (only http/https allowed)."}
    page = _ensure_page(db)
    ref = url or f"manual:{hashlib.sha1((text + str(published_at)).encode()).hexdigest()[:12]}"
    dup = db.scalar(select(FacebookPost).where(FacebookPost.fb_post_id == ref))
    if dup:
        return {"ok": False, "error": "This post URL/reference was already imported.", "duplicate": True}
    post = FacebookPost(
        page_id=page.id, fb_post_id=ref, message=text, permalink=url,
        published_at=published_at or datetime.now(timezone.utc),
        reactions=reactions, comments_count=comments_count,
        source_kind="manual", raw={"imported_by": imported_by},
    )
    _analyze_post(post, text)
    db.add(post)
    db.add(SyncLog(source_kind="facebook", source_name=f"{page.name} (manual)",
                   status="success", items_seen=1, items_new=1,
                   finished_at=datetime.now(timezone.utc)))
    db.commit()
    return {"ok": True, "post_id": post.id}
