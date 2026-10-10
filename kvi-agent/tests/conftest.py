"""Shared test fixtures.

All tests use a temporary SQLite database, a temporary watch folder, no SMTP and
no Meta credentials. Nothing here contacts the internet. Fixture data in
tests/fixtures is SYNTHETIC (invented names, example.com addresses, test numbers).
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="kvi-tests-"))
os.environ.update({
    "KVI_DATABASE_URL": f"sqlite:///{_TMP / 'test.db'}",
    "KVI_SECRET_KEY": "test-secret-key-for-pytest-only-0123456789abcdef",
    "KVI_ADMIN_PASSWORD": "admin-test-password-123",
    "KVI_SCHEDULER_ENABLED": "false",
    "KVI_IMPORT_WATCH_DIR": str(_TMP / "watch"),
    "KVI_EMAIL_BACKOFF_BASE_SECONDS": "0",
    "KVI_SMTP_HOST": "",
    "KVI_BACKUP_RECIPIENT": "",
    "KVI_FB_PAGE_ID": "",
    "KVI_FB_ACCESS_TOKEN": "",
    "KVI_AI_API_BASE": "",
    "KVI_AI_API_KEY": "",
    "KVI_AI_MODEL": "",
})

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"

from fixture_map import FILE_FOR_GROUP, GROUPS, TEST_DAY  # noqa: E402


@pytest.fixture(scope="session")
def app_module():
    import app.main as main
    return main


@pytest.fixture(scope="session")
def client(app_module):
    """Session-wide app with lifespan (creates tables and the bootstrap admin)."""
    with TestClient(app_module.app) as c:
        c.headers.update({"X-Requested-With": "kvi-dashboard"})
        yield c


def login_client(app_module, username: str, password: str) -> TestClient:
    c = TestClient(app_module.app)
    c.headers.update({"X-Requested-With": "kvi-dashboard"})
    r = c.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return c


@pytest.fixture(scope="session")
def seeded(app_module, client):
    """Create users, registry groups and import the synthetic fixtures once."""
    from app.db import SessionLocal
    from app.models import User, WhatsAppGroup
    from app.security import hash_password
    from app.connectors.whatsapp_ingest import import_export_text

    with SessionLocal() as db:
        for role in ("leadership", "staff", "viewer"):
            db.add(User(username=f"{role}_user", full_name=role, role=role,
                        password_hash=hash_password(f"{role}-test-password-1")))
        db.commit()
        groups = {}
        for name, cat, level, method in GROUPS:
            g = WhatsAppGroup(name=name, category=cat, class_level=level,
                              collection_method=method, include_in_reporting=True,
                              authorization_noted=True, academic_year="2083")
            db.add(g)
            db.flush()
            groups[name] = g.id
        db.commit()
        import_stats = {}
        for name, fname in FILE_FOR_GROUP.items():
            g = db.get(WhatsAppGroup, groups[name])
            content = (FIXTURES / "whatsapp" / fname).read_text(encoding="utf-8")
            import_stats[name] = import_export_text(db, g, content, import_label="test_fixture")
    return {"groups": groups, "imports": import_stats}


@pytest.fixture()
def admin(app_module, seeded):
    return login_client(app_module, "admin", "admin-test-password-123")


@pytest.fixture()
def leadership(app_module, seeded):
    return login_client(app_module, "leadership_user", "leadership-test-password-1")


@pytest.fixture()
def staff(app_module, seeded):
    return login_client(app_module, "staff_user", "staff-test-password-1")


@pytest.fixture()
def viewer(app_module, seeded):
    return login_client(app_module, "viewer_user", "viewer-test-password-1")


@pytest.fixture()
def db():
    from app.db import SessionLocal
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()
