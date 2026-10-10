"""Test 4 — Facebook posts and comments; Test 10 (failed connection reported accurately).

Graph API responses are MOCKED here (labelled as mock tests). No live Meta call is made."""
import json
from datetime import datetime, timezone

from sqlalchemy import select

from app.connectors import facebook_ingest
from app.connectors.facebook_graph import FacebookGraphClient
from app.models import FacebookComment, FacebookPage, FacebookPost, SyncLog
from conftest import FIXTURES


def test_status_is_not_configured_and_never_claims_connection():
    st = FacebookGraphClient().status()
    assert st.configured is False and st.connected is False
    assert "not configured" in st.detail.lower()


def test_manual_import_stores_text_and_marks_source(db):
    res = facebook_ingest.manual_import(
        db, "https://www.facebook.com/example/posts/900000000000001",
        "Terminal examination routine for Class 5 to 8 will be published on 2026-10-20.",
        published_at=datetime(2026, 10, 10, 4, 30, tzinfo=timezone.utc), reactions=None, comments_count=None)
    assert res["ok"]
    post = db.get(FacebookPost, res["post_id"])
    assert post.source_kind == "manual"
    assert post.reactions is None                      # not provided -> stays unknown, not zero
    assert "Examinations & assessments" in post.categories


def test_manual_import_rejects_non_http_url_and_duplicates(db):
    bad = facebook_ingest.manual_import(db, "javascript:alert(1)", "Some text here")
    assert bad["ok"] is False and "http" in bad["error"].lower()
    url = "https://www.facebook.com/example/posts/900000000000777"
    assert facebook_ingest.manual_import(db, url, "Annual day notice text")["ok"]
    dup = facebook_ingest.manual_import(db, url, "Annual day notice text")
    assert dup["ok"] is False and dup.get("duplicate") is True


def test_api_sync_mocked_success_stores_posts_and_comments(db, monkeypatch):
    feed = json.loads((FIXTURES / "facebook" / "page_feed_sample.json").read_text())["data"]
    comments = json.loads((FIXTURES / "facebook" / "comments_sample.json").read_text())["data"]

    def fake_posts(self, since, until, timeout=20.0):   # MOCK
        return feed, ""

    def fake_comments(self, post_id, timeout=15.0):      # MOCK
        return comments if post_id.endswith("900000000000001") else []

    monkeypatch.setattr(FacebookGraphClient, "fetch_posts", fake_posts)
    monkeypatch.setattr(FacebookGraphClient, "fetch_comments", fake_comments)
    monkeypatch.setattr(FacebookGraphClient, "fetch_reaction_count", lambda self, pid, timeout=15.0: None)
    res = facebook_ingest.sync_from_api(db, days=1)
    assert res["ok"] and res["posts_fetched"] == 2
    p = db.scalar(select(FacebookPost).where(FacebookPost.fb_post_id == "100000000000001_900000000000001"))
    assert p.published_at is not None and p.comments_count == 2
    assert db.scalar(select(FacebookComment).where(FacebookComment.post_id == p.id, FacebookComment.is_question == True)) is not None  # noqa: E712
    assert p.reactions is None


def test_api_failure_is_reported_accurately_not_hidden(db, monkeypatch):
    """Test 10 (mock): an expired token must surface as a failed sync with the Graph error."""
    def expired(self, since, until, timeout=20.0):      # MOCK Graph error
        return [], "Graph API error 190: Error validating access token (token expired)"
    monkeypatch.setattr(FacebookGraphClient, "fetch_posts", expired)
    res = facebook_ingest.sync_from_api(db, days=1)
    assert res["ok"] is False and "190" in res["error"]
    page = db.scalar(select(FacebookPage))
    assert "190" in page.last_error
    log = db.scalar(select(SyncLog).where(SyncLog.source_kind == "facebook", SyncLog.status == "failed").order_by(SyncLog.id.desc()))
    assert log is not None and "190" in log.error
