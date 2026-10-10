"""Application configuration.

All secrets come from environment variables / .env file — never hardcoded.
School profile defaults follow the KVI specification but can be overridden.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

# Classes reported on, from Playgroup through Class 12 (spec section 6.1)
CLASS_LEVELS = [
    "Playgroup", "Nursery", "LKG", "UKG",
    "Class 1", "Class 2", "Class 3", "Class 4", "Class 5", "Class 6",
    "Class 7", "Class 8", "Class 9", "Class 10", "Class 11", "Class 12",
]

GROUP_CATEGORIES = [
    "Playgroup & Kindergarten",
    "Class Group",
    "Parent-Teacher Group",
    "Subject Teachers",
    "Academic Coordination",
    "Administration & Management",
    "Examination & Assessment",
    "Events & Extracurricular",
    "Transport / Hostel / Welfare",
    "Other",
]

SUGGESTED_ROLES = [
    "Principal", "Vice Principal", "Coordinator", "Class Teacher",
    "Subject Teacher", "Administrative Staff",
]

PRIORITY_LEVELS = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "POSITIVE"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="KVI_",
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- core ---
    secret_key: str = Field(default="dev-insecure-key-change-me")
    env: str = "development"
    database_url: str = f"sqlite:///{BASE_DIR / 'data' / 'kvi.db'}"

    # --- school profile ---
    school_name: str = "Kashyap Vidyapeeth Inaruwa"
    school_address: str = "Inaruwa-4, Sunsari, Koshi Province, Nepal"
    school_website: str = "https://www.kvnepal.edu.np"
    levels: str = "Playgroup through Class 12"
    primary_administrator: str = "School Principal"
    report_recipient: str = "kptcc@gmail.com"
    backup_recipient: str = ""
    public_dashboard_url: str = ""

    # --- scheduler ---
    report_hour: int = 19
    report_minute: int = 0
    timezone: str = "Asia/Kathmandu"
    scheduler_enabled: bool = True
    import_watch_interval_min: int = 15
    import_watch_dir: str = "./data/imports"

    # --- email ---
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_starttls: bool = True
    smtp_ssl: bool = False
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "KVI School Intelligence <no-reply@example.org>"
    email_max_retries: int = 4
    email_backoff_base_seconds: float = 2.0
    email_backoff_max_seconds: float = 60.0
    email_attach_pdf: bool = True
    pdf_font_path: str = ""

    # --- facebook ---
    fb_page_id: str = ""
    fb_page_url: str = ""
    fb_access_token: str = ""
    fb_api_version: str = "v21.0"

    # --- AI provider (optional) ---
    ai_api_base: str = ""
    ai_api_key: str = ""
    ai_model: str = ""
    ai_enabled: bool = True

    # --- privacy ---
    retention_days: int = 365
    redact_in_summaries: bool = True

    # --- bootstrap admin ---
    admin_username: str = "admin"
    admin_password: str = ""

    # --- security ---
    login_max_failures: int = 5
    login_lock_minutes: int = 15

    @field_validator("timezone")
    @classmethod
    def _valid_tz(cls, v: str) -> str:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try:
            ZoneInfo(v)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Invalid IANA timezone: {v}") from exc
        return v

    # --- derived helpers -------------------------------------------------
    @property
    def secret_key_is_strong(self) -> bool:
        """Rejects the dev default and any placeholder copied from .env.example."""
        k = self.secret_key or ""
        return len(k) >= 32 and k != "dev-insecure-key-change-me" and not k.upper().startswith("CHANGE_ME")

    @property
    def email_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_from)

    @property
    def facebook_configured(self) -> bool:
        return bool(self.fb_page_id and self.fb_access_token)

    @property
    def ai_configured(self) -> bool:
        return bool(self.ai_enabled and self.ai_api_base and self.ai_api_key and self.ai_model)

    @property
    def watch_dir(self) -> Path:
        p = Path(self.import_watch_dir)
        if not p.is_absolute():
            p = BASE_DIR / p
        return p

    def validation_report(self) -> list[dict]:
        """Structured configuration validation used by /api/health/system."""
        checks = [
            {"item": "SECRET_KEY", "ok": self.secret_key_is_strong,
             "detail": "Set KVI_SECRET_KEY to a random value."},
            {"item": "Database URL", "ok": bool(self.database_url),
             "detail": self.database_url.split("://")[0] + " driver"},
            {"item": "Timezone", "ok": True,
             "detail": f"Reports scheduled in {self.timezone}"},
            {"item": "SMTP email", "ok": self.email_configured,
             "detail": "Configured" if self.email_configured else
                       "NOT configured — reports will be generated but not delivered."},
            {"item": "Meta/Facebook", "ok": self.facebook_configured,
             "detail": "Configured" if self.facebook_configured else
                       "NOT configured — Facebook connector reports 'unavailable'; manual import still works."},
            {"item": "AI provider", "ok": self.ai_configured,
             "detail": ("Hosted LLM configured" if self.ai_configured else
                        "Not configured — deterministic rules engine will be used (labelled in report).")},
            {"item": "Watch folder", "ok": self.watch_dir.is_dir(),
             "detail": str(self.watch_dir)},
            {"item": "Backup recipient", "ok": bool(self.backup_recipient),
             "detail": "Enabled" if self.backup_recipient else "Disabled until configured (by design)."},
        ]
        return checks


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.watch_dir.mkdir(parents=True, exist_ok=True)
    if s.database_url.startswith("sqlite"):
        Path(s.database_url.replace("sqlite:///", "")).parent.mkdir(parents=True, exist_ok=True)
    return s
