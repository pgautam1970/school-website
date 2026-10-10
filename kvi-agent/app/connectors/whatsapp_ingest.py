"""WhatsApp import pipeline: authorized exports -> normalized, classified,
deduplicated Message rows + SyncLog bookkeeping.

Duplicate handling: dedupe_key = sha1(original_ts | sender | text). Re-importing
the same export adds nothing; overlapping exports are safe. Original timestamps
are always preserved (converted NPT -> UTC for storage).
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..analysis.classify import classify
from ..analysis.normalize import detect_language, normalize_text
from ..analysis.priority import assess_priority
from ..analysis.redact import redact_text
from ..models import Message, SyncLog, WhatsAppGroup
from .whatsapp_export import ParseResult, parse_export

TEACHER_MARKERS = re.compile(
    r"(sir|ma'?am|miss|teacher|guru|principal|coordinator|admin|hod|vice)", re.I)
PARENT_CATEGORIES = {"Class Group", "Parent-Teacher Group", "Playgroup & Kindergarten",
                     "Events & Extracurricular", "Transport / Hostel / Welfare"}


def guess_sender_kind(sender: str, group_category: str) -> str:
    if TEACHER_MARKERS.search(sender or ""):
        return "teacher"
    if group_category in ("Subject Teachers", "Academic Coordination",
                          "Administration & Management", "Examination & Assessment"):
        return "teacher"
    if group_category in PARENT_CATEGORIES:
        return "parent"
    return "unknown"


def dedupe_key(ts: datetime, sender: str, text: str) -> str:
    raw = f"{ts.astimezone(timezone.utc).isoformat()}|{sender.strip().lower()}|{text.strip()}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def analyze_and_store(db: Session, group: WhatsAppGroup, parsed: ParseResult,
                      import_label: str = "upload") -> dict:
    """Store parsed messages for a group; returns import statistics."""
    existing = set(db.scalars(
        select(Message.dedupe_key).where(Message.group_id == group.id)))
    log = SyncLog(source_kind="whatsapp", source_name=group.name,
                  status="running", items_seen=len(parsed.messages))
    db.add(log)

    new_count = dup_count = 0
    last_ts = group.last_message_at
    for pm in parsed.messages:
        key = dedupe_key(pm.ts, pm.sender, pm.text)
        if key in existing:
            dup_count += 1
            continue
        existing.add(key)
        ts_utc = pm.ts.astimezone(timezone.utc)
        sender_kind = guess_sender_kind(pm.sender, group.category)
        # analysis copy is redacted first: contact details never drive categories or evidence
        norm = normalize_text(redact_text(pm.text))
        cls = classify(norm, sender_kind=sender_kind, group_category=group.category)
        pr = assess_priority(norm, cls.categories, is_question=cls.is_question,
                             sender_kind=sender_kind)
        msg = Message(
            group_id=group.id,
            dedupe_key=key,
            sender_label=pm.sender[:160],
            sender_kind=sender_kind,
            ts_original=ts_utc,
            text_original=pm.text,
            text_normalized=norm,
            text_redacted=redact_text(pm.text),
            media_kind=pm.media_kind,
            language=detect_language(pm.text),
            categories=cls.categories,
            priority=pr.priority,
            priority_reason=pr.reason,
            activity_status=cls.activity_status,
            confidence=cls.confidence,
            is_question=cls.is_question,
            analysis_version="rules-v1",
        )
        db.add(msg)
        new_count += 1
        if last_ts is None or ts_utc > last_ts:
            last_ts = ts_utc

    group.last_message_at = last_ts
    group.last_sync_at = datetime.now(timezone.utc)
    log.finished_at = datetime.now(timezone.utc)
    log.items_new = new_count
    log.items_duplicate = dup_count
    log.status = "success" if parsed.malformed_lines == 0 else "partial"
    if parsed.malformed_lines:
        log.error = f"{parsed.malformed_lines} malformed line(s) skipped"
    db.commit()
    return {"seen": len(parsed.messages), "new": new_count, "duplicate": dup_count,
            "malformed": parsed.malformed_lines, "status": log.status,
            "import_label": import_label, "group": group.name}


def import_export_text(db: Session, group: WhatsAppGroup, content: str,
                       import_label: str = "upload") -> dict:
    parsed = parse_export(content)
    return analyze_and_store(db, group, parsed, import_label)


def find_group_for_filename(db: Session, filename: str) -> WhatsAppGroup | None:
    """Match an upload/watch-folder file to a registered group by name similarity.
    e.g. 'Class 5 - Science group.txt' -> group named 'Class 5 Science'."""
    stem = Path(filename).stem.lower()
    stem_clean = re.sub(r"[^a-z0-9\u0900-\u097F]+", " ", stem).strip()
    stem_tokens = set(stem_clean.split())
    best, best_score = None, 0.0
    for g in db.scalars(select(WhatsAppGroup).where(WhatsAppGroup.is_active == True)):  # noqa: E712
        name_clean = re.sub(r"[^a-z0-9\u0900-\u097F]+", " ", g.name.lower()).strip()
        name_tokens = set(name_clean.split())
        if not name_tokens:
            continue
        inter = len(stem_tokens & name_tokens)
        score = inter / max(len(name_tokens), 1)
        if score > best_score:
            best, best_score = g, score
    return best if best_score >= 0.6 else None


def scan_watch_folder(db: Session) -> list[dict]:
    """Automation path: import any new *.txt exports in the configured watch dir.
    Files are renamed to *.imported after processing to avoid double imports
    (dedupe_key also protects against duplicates)."""
    from ..config import get_settings
    settings = get_settings()
    results = []
    wdir = settings.watch_dir
    wdir.mkdir(parents=True, exist_ok=True)
    for path in sorted(wdir.glob("*.txt")):
        group = find_group_for_filename(db, path.name)
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            if group is None:
                results.append({"file": path.name, "status": "skipped",
                                "reason": "No registered group matches this filename. "
                                          "Register the group or name the file after it."})
                continue
            stats = import_export_text(db, group, content, import_label="watch_folder")
            stats["file"] = path.name
            results.append(stats)
            path.rename(path.with_suffix(".txt.imported"))
        except Exception as exc:  # record failure, keep processing other files
            db.add(SyncLog(source_kind="whatsapp", source_name=path.name,
                           status="failed", error=str(exc)[:500],
                           finished_at=datetime.now(timezone.utc)))
            db.commit()
            results.append({"file": path.name, "status": "failed", "reason": str(exc)[:200]})
    return results
