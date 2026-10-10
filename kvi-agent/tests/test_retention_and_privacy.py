"""Privacy controls: retention purge is audited and scoped to raw content."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.models import AuditLog, Message
from app.services import purge_expired


def test_purge_removes_only_old_raw_messages_and_is_audited(seeded, db):
    old = Message(group_id=seeded["groups"]["Class 1 Maths"], dedupe_key="old-" + "x" * 30,
                  sender_label="Old", sender_kind="teacher",
                  ts_original=datetime.now(timezone.utc) - timedelta(days=4000),
                  text_original="ancient", text_normalized="ancient", text_redacted="ancient")
    db.add(old)
    db.commit()
    res = purge_expired(db, retention_days=365, actor="pytest")
    assert res["messages_deleted"] >= 1
    assert db.scalar(select(func.count()).select_from(Message).where(Message.text_original == "ancient")) == 0
    assert db.scalar(select(func.count()).select_from(Message)) > 0          # recent data kept
    assert db.scalar(select(AuditLog.id).where(AuditLog.action == "retention_purge")) is not None


def test_retention_cannot_be_set_below_30_days(admin):
    r = admin.put("/api/settings", json={"retention_days": 5})
    assert r.status_code == 422
