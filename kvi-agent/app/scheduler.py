"""Scheduler: daily 19:00 Asia/Kathmandu report + watch-folder import polling.

- Uses an explicit ZoneInfo('Asia/Kathmandu') for the cron trigger, never the server's local zone.
- Runs every day including weekends (unless KVI_REPORT_* is changed).
- Duplicate-run safe: the report row is claimed before sending (see email_sender).
- misfire_grace_time covers a restart shortly after 19:00; coalesce merges missed runs.
- The scheduler runs inside the API process when KVI_SCHEDULER_ENABLED=true. For
  production, run ONE scheduler instance (single worker), or disable it in the API
  and use the CLI (`python -m scripts.run_daily`) from Windows Task Scheduler / cron / n8n.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import get_settings

log = logging.getLogger("kvi.scheduler")
_scheduler: BackgroundScheduler | None = None
JOB_REPORT = "daily-report"
JOB_WATCH = "watch-folder-import"


def npt_now() -> datetime:
    return datetime.now(ZoneInfo(get_settings().timezone))


def build_report_trigger(hour: int | None = None, minute: int | None = None) -> CronTrigger:
    s = get_settings()
    return CronTrigger(hour=s.report_hour if hour is None else hour,
                       minute=s.report_minute if minute is None else minute,
                       timezone=ZoneInfo(s.timezone))


def next_report_time() -> datetime | None:
    if _scheduler is None:
        trig = build_report_trigger()
        return trig.get_next_fire_time(None, npt_now())
    job = _scheduler.get_job(JOB_REPORT)
    return job.next_run_time if job else None


def run_daily_job(report_date: str | None = None, *, force: bool = False) -> dict:
    """Generate today's report and send it. Safe to call multiple times."""
    from sqlalchemy import select
    from .db import session_scope
    from .models import DailyReport
    from .services import generate_and_send
    day = report_date or npt_now().date().isoformat()
    with session_scope() as db:
        if not force:
            done = db.scalar(select(DailyReport).where(DailyReport.report_date == day,
                                                       DailyReport.status == "sent"))
            if done is not None:
                # retries (e.g. Task Scheduler every 15 min after 19:00) stop here: nothing is regenerated
                return {"report_date": day, "report_uid": done.report_uid, "generated": False,
                        "send_status": "skipped_duplicate",
                        "send_detail": "Report already accepted by the provider; not regenerated or resent."}
        return generate_and_send(db, day, send=True, kind="daily", force=force, actor="scheduler")


def run_watch_import() -> list[dict]:
    from .connectors.whatsapp_ingest import scan_watch_folder
    from .db import session_scope
    with session_scope() as db:
        return scan_watch_folder(db)


def start_scheduler() -> BackgroundScheduler | None:
    global _scheduler
    s = get_settings()
    if not s.scheduler_enabled:
        log.info("Scheduler disabled by configuration")
        return None
    if _scheduler and _scheduler.running:
        return _scheduler
    _scheduler = BackgroundScheduler(
        timezone=ZoneInfo(s.timezone),
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 6 * 3600},
    )
    _scheduler.add_job(run_daily_job, build_report_trigger(), id=JOB_REPORT,
                       replace_existing=True, name="Daily 19:00 NPT report")
    _scheduler.add_job(run_watch_import, "interval", minutes=s.import_watch_interval_min,
                       id=JOB_WATCH, replace_existing=True, name="Watch-folder import")
    _scheduler.start()
    log.info("Scheduler started; next report at %s", next_report_time())
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None


def scheduler_status() -> dict:
    s = get_settings()
    nxt = next_report_time()
    return {
        "enabled": s.scheduler_enabled,
        "running": bool(_scheduler and _scheduler.running),
        "timezone": s.timezone,
        "report_time": f"{s.report_hour:02d}:{s.report_minute:02d}",
        "next_report_at_npt": nxt.astimezone(ZoneInfo(s.timezone)).strftime("%Y-%m-%d %H:%M %Z") if nxt else None,
        "watch_interval_min": s.import_watch_interval_min,
    }
