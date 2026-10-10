"""ORM models for the KVI School Intelligence platform.

Design notes:
- Original message text is always preserved (text_original). Normalized and
  redacted copies are stored separately — evidence is never silently rewritten.
- Every ingestion event is recorded in SyncLog; every send attempt in EmailLog.
- DailyReport.report_date is UNIQUE — this is the duplicate-send prevention key.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (JSON, Boolean, DateTime, Float, ForeignKey, Integer,
                        String, Text, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """Stores timezone-aware datetimes as naive UTC and always returns aware UTC.
    SQLite drops tzinfo on read; this keeps comparisons correct on every backend."""
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc)


def new_uid() -> str:
    return uuid.uuid4().hex


# --------------------------------------------------------------------------
# Users, roles, audit
# --------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    # admin | leadership | staff | viewer
    role: Mapped[str] = mapped_column(String(20), default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    username: Mapped[str] = mapped_column(String(80), default="system")
    action: Mapped[str] = mapped_column(String(80), index=True)
    detail: Mapped[str] = mapped_column(Text, default="")


# --------------------------------------------------------------------------
# Sources: WhatsApp group registry + Facebook pages
# --------------------------------------------------------------------------
class WhatsAppGroup(Base):
    __tablename__ = "whatsapp_groups"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    category: Mapped[str] = mapped_column(String(80), default="Other")
    class_level: Mapped[str] = mapped_column(String(40), default="")   # e.g. "Class 5"
    academic_year: Mapped[str] = mapped_column(String(20), default="")
    group_admin: Mapped[str] = mapped_column(String(120), default="")
    # export_upload | watch_folder | manual | api (future approved integration)
    collection_method: Mapped[str] = mapped_column(String(30), default="export_upload")
    include_in_reporting: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    authorization_noted: Mapped[bool] = mapped_column(Boolean, default=False)
    last_sync_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    messages: Mapped[list["Message"]] = relationship(back_populates="group")


class FacebookPage(Base):
    __tablename__ = "facebook_pages"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), default="Kashyap Vidyapeeth Inaruwa")
    page_id: Mapped[str] = mapped_column(String(120), default="")
    page_url: Mapped[str] = mapped_column(String(300), default="")
    include_in_reporting: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    posts: Mapped[list["FacebookPost"]] = relationship(back_populates="page")


# --------------------------------------------------------------------------
# Ingested content
# --------------------------------------------------------------------------
class Message(Base):
    """A single WhatsApp message (from export/import). Timestamps stored UTC."""
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("group_id", "dedupe_key", name="uq_message_dedupe"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("whatsapp_groups.id"), index=True)
    dedupe_key: Mapped[str] = mapped_column(String(64), index=True)   # sha1(ts|sender|text)
    sender_label: Mapped[str] = mapped_column(String(160), default="")
    sender_kind: Mapped[str] = mapped_column(String(20), default="unknown")  # teacher|parent|student|unknown
    ts_original: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    text_original: Mapped[str] = mapped_column(Text, default="")
    text_normalized: Mapped[str] = mapped_column(Text, default="")
    text_redacted: Mapped[str] = mapped_column(Text, default="")
    media_kind: Mapped[str] = mapped_column(String(30), default="")   # image|video|document|audio|sticker|""
    language: Mapped[str] = mapped_column(String(20), default="")     # en|ne|ne-roman|mixed
    categories: Mapped[list] = mapped_column(JSON, default=list)
    priority: Mapped[str] = mapped_column(String(10), default="LOW", index=True)
    priority_reason: Mapped[str] = mapped_column(Text, default="")
    activity_status: Mapped[str] = mapped_column(String(20), default="")  # planned|announced|in_progress|completed|delayed|unverified
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    is_question: Mapped[bool] = mapped_column(Boolean, default=False)
    question_answered: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)
    analysis_version: Mapped[str] = mapped_column(String(20), default="")
    imported_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    group: Mapped[WhatsAppGroup] = relationship(back_populates="messages")


class FacebookPost(Base):
    __tablename__ = "facebook_posts"
    id: Mapped[int] = mapped_column(primary_key=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("facebook_pages.id"), index=True)
    fb_post_id: Mapped[str] = mapped_column(String(120), unique=True)
    message: Mapped[str] = mapped_column(Text, default="")
    permalink: Mapped[str] = mapped_column(String(400), default="")
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True, index=True)
    reactions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comments_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shares: Mapped[int | None] = mapped_column(Integer, nullable=True)
    media_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    source_kind: Mapped[str] = mapped_column(String(20), default="api")  # api|manual
    raw: Mapped[dict] = mapped_column(JSON, default=dict)
    categories: Mapped[list] = mapped_column(JSON, default=list)
    priority: Mapped[str] = mapped_column(String(10), default="LOW")
    imported_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    page: Mapped[FacebookPage] = relationship(back_populates="posts")
    comments: Mapped[list["FacebookComment"]] = relationship(back_populates="post", cascade="all, delete-orphan")


class FacebookComment(Base):
    __tablename__ = "facebook_comments"
    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("facebook_posts.id"), index=True)
    fb_comment_id: Mapped[str] = mapped_column(String(160), default="")
    from_name: Mapped[str] = mapped_column(String(160), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    is_question: Mapped[bool] = mapped_column(Boolean, default=False)
    post: Mapped[FacebookPost] = relationship(back_populates="comments")


# --------------------------------------------------------------------------
# Sync / import logs
# --------------------------------------------------------------------------
class SyncLog(Base):
    __tablename__ = "sync_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_kind: Mapped[str] = mapped_column(String(30), index=True)  # whatsapp|facebook|manual
    source_name: Mapped[str] = mapped_column(String(200), default="")
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running")  # success|partial|failed|running
    items_seen: Mapped[int] = mapped_column(Integer, default=0)
    items_new: Mapped[int] = mapped_column(Integer, default=0)
    items_duplicate: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")


# --------------------------------------------------------------------------
# Reports, actions, email delivery
# --------------------------------------------------------------------------
class DailyReport(Base):
    __tablename__ = "daily_reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    report_uid: Mapped[str] = mapped_column(String(40), unique=True, default=new_uid)
    report_date: Mapped[str] = mapped_column(String(10), unique=True, index=True)  # YYYY-MM-DD (NPT)
    nepali_date: Mapped[str] = mapped_column(String(80), default="")
    generated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    engine: Mapped[str] = mapped_column(String(20), default="rules")   # rules|llm|hybrid
    coverage: Mapped[dict] = mapped_column(JSON, default=dict)
    data: Mapped[dict] = mapped_column(JSON, default=dict)             # full structured report
    html: Mapped[str] = mapped_column(Text, default="")
    text: Mapped[str] = mapped_column(Text, default="")
    pdf_path: Mapped[str] = mapped_column(String(400), default="")
    pdf_engine: Mapped[str] = mapped_column(String(20), default="")    # weasyprint|fpdf2|""
    status: Mapped[str] = mapped_column(String(20), default="generated")  # generated|sending|sent|failed|no_email_config
    is_regeneration: Mapped[bool] = mapped_column(Boolean, default=False)


class ActionItem(Base):
    __tablename__ = "action_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    action_id: Mapped[str] = mapped_column(String(20), unique=True, default=lambda: "ACT-" + new_uid()[:8].upper())
    report_date: Mapped[str] = mapped_column(String(10), index=True)
    title: Mapped[str] = mapped_column(String(300))
    detail: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    priority: Mapped[str] = mapped_column(String(10), default="MEDIUM", index=True)
    suggested_role: Mapped[str] = mapped_column(String(60), default="")
    deadline: Mapped[str] = mapped_column(String(10), default="")
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)  # open|in_progress|resolved|dismissed
    resolution_notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class EmailLog(Base):
    __tablename__ = "email_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int | None] = mapped_column(ForeignKey("daily_reports.id"), nullable=True)
    report_uid: Mapped[str] = mapped_column(String(40), default="", index=True)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    kind: Mapped[str] = mapped_column(String(20), default="daily")   # daily|test|resend|failure_notice
    to_addr: Mapped[str] = mapped_column(String(300), default="")
    subject: Mapped[str] = mapped_column(String(400), default="")
    status: Mapped[str] = mapped_column(String(30), default="queued")  # queued|accepted|failed|skipped_duplicate|not_configured
    provider_response: Mapped[str] = mapped_column(Text, default="")
    has_pdf: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class AppSetting(Base):
    """Runtime-editable settings (scheduler, privacy) — DB overrides .env defaults."""
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)
