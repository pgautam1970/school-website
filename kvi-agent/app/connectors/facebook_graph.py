"""Authorized Meta (Facebook Page) connector.

Uses the official Meta Graph API only. Requires a Page access token from a Meta
developer app with permissions: pages_show_list, pages_read_engagement,
read_insights (see docs/META_FACEBOOK_SETUP.md). The token lives ONLY in the
environment (KVI_FB_ACCESS_TOKEN) — never in the database or code.

Honesty rules implemented here:
- If no token is configured, status is 'not_configured' — the system never
  pretends to be connected.
- Only fields the API actually returns are stored; missing engagement numbers
  stay NULL and are reported as "not available", never estimated.
- No access to private profiles, Messenger conversations or closed groups.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import httpx

from ..config import Settings, get_settings

GRAPH_BASE = "https://graph.facebook.com"


@dataclass
class FbStatus:
    configured: bool = False
    connected: bool = False
    page_name: str = ""
    page_id: str = ""
    page_url: str = ""
    detail: str = ""
    checked_at: str = ""


@dataclass
class FbSyncResult:
    ok: bool = False
    posts_fetched: int = 0
    posts_new: int = 0
    comments_fetched: int = 0
    error: str = ""
    detail: dict = field(default_factory=dict)


class FacebookGraphClient:
    def __init__(self, settings: Settings | None = None):
        self.s = settings or get_settings()
        self.base = f"{GRAPH_BASE}/{self.s.fb_api_version}"

    # ------------------------------------------------------------ status
    def status(self, timeout: float = 10.0) -> FbStatus:
        st = FbStatus(configured=self.s.facebook_configured,
                      page_id=self.s.fb_page_id, page_url=self.s.fb_page_url,
                      checked_at=datetime.now(timezone.utc).isoformat())
        if not self.s.facebook_configured:
            st.detail = ("Meta integration not configured. Set KVI_FB_PAGE_ID and "
                         "KVI_FB_ACCESS_TOKEN (see docs/META_FACEBOOK_SETUP.md). "
                         "Manual post import remains available.")
            return st
        try:
            r = httpx.get(f"{self.base}/{self.s.fb_page_id}",
                          params={"fields": "name,link,fan_count",
                                  "access_token": self.s.fb_access_token},
                          timeout=timeout)
            data = r.json()
            if r.status_code == 200 and "name" in data:
                st.connected = True
                st.page_name = data.get("name", "")
                st.page_url = data.get("link", self.s.fb_page_url)
                fans = data.get("fan_count")
                st.detail = f"Page verified: {st.page_name}" + (f" ({fans} followers)" if fans is not None else "")
            else:
                err = data.get("error", {})
                st.detail = f"API error {err.get('code', r.status_code)}: {err.get('message', 'unknown')}"
        except httpx.HTTPError as exc:
            st.detail = f"Network error contacting Graph API: {exc}"
        return st

    # ------------------------------------------------------------- fetch
    def fetch_posts(self, since: datetime, until: datetime,
                    timeout: float = 20.0) -> tuple[list[dict], str]:
        """Fetch page feed for the window. Returns (posts, error)."""
        if not self.s.facebook_configured:
            return [], "not_configured"
        params = {
            "fields": "id,message,created_time,permalink_url,shares,"
                      "status_type,full_picture,attachment{media,description,target}",
            "since": int(since.timestamp()),
            "until": int(until.timestamp()),
            "limit": 100,
            "access_token": self.s.fb_access_token,
        }
        try:
            r = httpx.get(f"{self.base}/{self.s.fb_page_id}/feed", params=params, timeout=timeout)
            data = r.json()
            if r.status_code != 200 or "data" not in data:
                err = data.get("error", {})
                return [], f"Graph API error {err.get('code', r.status_code)}: {err.get('message', '')}"
            return data["data"], ""
        except httpx.HTTPError as exc:
            return [], f"Network error: {exc}"

    def fetch_comments(self, post_id: str, timeout: float = 15.0) -> list[dict]:
        if not self.s.facebook_configured:
            return []
        params = {"fields": "id,from{name},message,created_time",
                  "limit": 100, "access_token": self.s.fb_access_token}
        try:
            r = httpx.get(f"{self.base}/{post_id}/comments", params=params, timeout=timeout)
            data = r.json()
            return data.get("data", []) if r.status_code == 200 else []
        except httpx.HTTPError:
            return []

    def fetch_reaction_count(self, post_id: str, timeout: float = 15.0) -> int | None:
        """Reactions summary — returns None (not 0) when unavailable."""
        if not self.s.facebook_configured:
            return None
        params = {"summary": "true", "limit": 0, "access_token": self.s.fb_access_token}
        try:
            r = httpx.get(f"{self.base}/{post_id}/reactions", params=params, timeout=timeout)
            data = r.json()
            if r.status_code == 200:
                return data.get("summary", {}).get("total_count")
            return None
        except httpx.HTTPError:
            return None

    def fetch_insights(self, metric: str = "page_impressions", period: str = "day",
                       since: datetime | None = None, timeout: float = 15.0) -> dict | None:
        """Page insights (requires read_insights). None when unavailable."""
        if not self.s.facebook_configured:
            return None
        since = since or datetime.now(timezone.utc) - timedelta(days=7)
        params = {"metric": metric, "period": period, "since": int(since.timestamp()),
                  "access_token": self.s.fb_access_token}
        try:
            r = httpx.get(f"{self.base}/{self.s.fb_page_id}/insights", params=params, timeout=timeout)
            return r.json().get("data") if r.status_code == 200 else None
        except httpx.HTTPError:
            return None
