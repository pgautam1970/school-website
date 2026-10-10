"""Test 14 — dashboard usable on mobile and desktop (static checks + JS syntax), and API smoke tests."""
import shutil
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"


def test_health_is_public_and_leaks_nothing(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert set(body) <= {"status", "database", "time_npt"}


def test_dashboard_shell_served_with_viewport_and_csp(client):
    r = client.get("/")
    assert r.status_code == 200
    assert 'name="viewport" content="width=device-width, initial-scale=1.0"' in r.text
    assert "/static/js/dashboard.js" in r.text and "<script>" not in r.text.replace('<script src', '')  # no inline scripts


def test_css_has_mobile_breakpoints_and_touch_targets():
    css = (STATIC / "css" / "dashboard.css").read_text(encoding="utf-8")
    assert "@media (max-width: 800px)" in css
    assert "min-height: 44px" in css
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in css
    assert "prefers-reduced-motion" in css
    assert ":focus-visible" in css


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_dashboard_js_parses():
    r = subprocess.run(["node", "--check", str(STATIC / "js" / "dashboard.js")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_dashboard_escapes_untrusted_text_everywhere_it_renders_data():
    js = (STATIC / "js" / "dashboard.js").read_text(encoding="utf-8")
    assert "function esc(" in js
    # every message-derived field is wrapped; spot-check the high-risk renderers
    assert "${esc(m.text)}" in js and "${esc(q.question)}" in js and "${esc(a.issue)}" in js


def test_meta_and_dashboard_endpoints_for_roles(admin, staff, leadership):
    assert staff.get("/api/dashboard").status_code == 200
    d = staff.get("/api/dashboard").json()
    for key in ("configured_sources", "messages_today", "high_priority_today", "open_actions",
                "failed_connections_recent", "next_report_at", "email_configured", "today_npt"):
        assert key in d
    assert d["email_configured"] is False          # SMTP not configured in tests -> honest
    assert admin.get("/api/system").status_code == 200
    sysinfo = leadership.get("/api/system").json()
    assert sysinfo["email"]["configured"] is False
    assert sysinfo["scheduler"]["timezone"] == "Asia/Kathmandu"
    assert any(c["item"] == "Watch folder" for c in sysinfo["config_checks"])


def test_sources_report_facebook_and_whatsapp_honestly(staff):
    s = staff.get("/api/sources").json()
    assert s["facebook"]["connected"] is False
    assert s["whatsapp"]["live_api_connected"] is False
    assert s["groups_configured"] >= 8
    never = [g for g in s["groups"] if g["name"] == "Class 4 Parents"][0]
    assert never["import_status"] == "never_imported"


def test_source_status_marks_groups_with_data_today(staff, seeded, db):
    """Clock-independent: insert a message stamped 'now' so it counts as today in NPT."""
    from datetime import datetime, timezone
    from app.models import Message
    gid = seeded["groups"]["Class 1 Maths"]
    now = datetime.now(timezone.utc)
    db.add(Message(group_id=gid, dedupe_key="today-" + now.isoformat(), sender_label="T",
                   sender_kind="teacher", ts_original=now, text_original="today's note",
                   text_normalized="today's note", text_redacted="today's note"))
    db.commit()
    s = staff.get("/api/sources").json()
    row = [g for g in s["groups"] if g["id"] == gid][0]
    assert row["import_status"] == "data_received_today"
    assert row["messages_today"] >= 1
