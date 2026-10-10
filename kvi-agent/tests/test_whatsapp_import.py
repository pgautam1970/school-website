"""Test 1 — WhatsApp multi-group import, duplicates, timestamps, source status."""
from datetime import datetime, timezone
from pathlib import Path
import shutil

from sqlalchemy import select

from app.connectors.whatsapp_export import parse_export
from app.connectors.whatsapp_ingest import find_group_for_filename, scan_watch_folder
from app.models import Message, WhatsAppGroup
from app.config import get_settings
from conftest import FIXTURES
from fixture_map import FILE_FOR_GROUP, GROUPS, TEST_DAY


def test_parser_reads_all_fixture_groups_and_skips_system_lines():
    total = 0
    for fname in FILE_FOR_GROUP.values():
        res = parse_export((FIXTURES / "whatsapp" / fname).read_text(encoding="utf-8"))
        assert res.messages, fname
        total += len(res.messages)
    assert total >= 30   # synthetic fixtures contain 33 messages across 8 files
    res = parse_export((FIXTURES / "whatsapp" / "Class_5_Science.txt").read_text(encoding="utf-8"))
    assert res.skipped_system == 1          # end-to-end encryption notice
    media = [m for m in res.messages if m.media_kind]
    assert media and media[0].media_kind == "image"  # media placeholder is not text evidence


def test_original_timestamps_preserved_as_utc(seeded, db):
    first = db.scalar(select(Message).where(Message.group_id == seeded["groups"]["Class 5 Science"],
                                            Message.text_original.like("Good morning parents%")))
    assert first is not None
    # 10/10/26 08:10:02 Asia/Kathmandu (UTC+05:45) == 02:25:02 UTC
    assert first.ts_original.replace(tzinfo=timezone.utc) == datetime(2026, 10, 10, 2, 25, 2, tzinfo=timezone.utc)


def test_every_group_with_data_is_recorded_and_sync_timestamps_set(seeded, db):
    for name, gid in seeded["groups"].items():
        g = db.get(WhatsAppGroup, gid)
        if name == "Class 4 Parents":
            assert g.last_sync_at is None          # never imported -> must not look synced
        else:
            assert g.last_sync_at is not None, name
            assert g.last_message_at is not None, name


def test_reimport_is_duplicate_safe(seeded, db):
    g = db.get(WhatsAppGroup, seeded["groups"]["Class 8 Parents"])
    content = (FIXTURES / "whatsapp" / "Class_8_Parents.txt").read_text(encoding="utf-8")
    from app.connectors.whatsapp_ingest import import_export_text
    before = db.scalar(select(Message.id).where(Message.group_id == g.id).order_by(Message.id.desc()).limit(1))
    stats = import_export_text(db, g, content, import_label="re-import")
    assert stats["new"] == 0
    assert stats["duplicate"] == stats["seen"]
    after = db.scalar(select(Message.id).where(Message.group_id == g.id).order_by(Message.id.desc()).limit(1))
    assert before == after


def test_watch_folder_matches_filename_and_marks_file_imported(seeded, db):
    watch = get_settings().watch_dir
    watch.mkdir(parents=True, exist_ok=True)
    src = FIXTURES / "whatsapp" / "Class_1_Maths.txt"
    dst = watch / "Class 1 Maths - export.txt"
    shutil.copy(src, dst)
    g = find_group_for_filename(db, dst.name)
    assert g is not None and g.name == "Class 1 Maths"
    results = scan_watch_folder(db)
    match = [r for r in results if r["file"] == dst.name]
    assert match and match[0]["status"] == "success"
    assert not dst.exists() and dst.with_suffix(".txt.imported").exists()
    assert match[0]["duplicate"] >= 1   # same content already imported -> dedupe, no double count


def test_unmatched_watch_file_is_skipped_not_guessed(seeded, db):
    watch = get_settings().watch_dir
    f = watch / "Unknown Staff Chat.txt"
    f.write_text("[10/10/26, 9:00:00 AM] A: hi there everyone\n", encoding="utf-8")
    results = scan_watch_folder(db)
    r = [x for x in results if x["file"] == f.name][0]
    assert r["status"] == "skipped"
    assert f.exists()   # left in place for manual handling
    f.unlink()


def test_upload_endpoint_rejects_non_txt_and_accepts_export(staff, seeded):
    gid = seeded["groups"]["Class 9 Parents"]
    bad = staff.post("/api/imports/whatsapp", data={"group_id": gid},
                     files={"file": ("export.exe", b"MZ....", "application/octet-stream")})
    assert bad.status_code == 422
    body = (FIXTURES / "whatsapp" / "Class_9_Parents.txt").read_bytes()
    ok = staff.post("/api/imports/whatsapp", data={"group_id": gid},
                    files={"file": ("Class 9 Parents.txt", body, "text/plain")})
    assert ok.status_code == 200, ok.text
    assert ok.json()["source_method"] == "manual_upload"
    assert ok.json()["duplicate"] >= 1
