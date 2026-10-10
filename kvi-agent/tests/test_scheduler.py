"""Test 9 — scheduling at 19:00 Asia/Kathmandu (not the server time zone)."""
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler

from app.scheduler import build_report_trigger, JOB_REPORT
from app import scheduler as sched

NPT = ZoneInfo("Asia/Kathmandu")


def test_trigger_uses_explicit_kathmandu_zone():
    trig = build_report_trigger()
    assert str(trig.timezone) == "Asia/Kathmandu"


def test_next_fire_is_19_00_npt_same_day_before_the_time():
    trig = build_report_trigger(19, 0)
    nxt = trig.get_next_fire_time(None, datetime(2026, 10, 10, 18, 0, tzinfo=NPT))
    assert nxt.astimezone(NPT).strftime("%Y-%m-%d %H:%M") == "2026-10-10 19:00"


def test_after_the_time_it_rolls_to_next_day_including_weekend():
    trig = build_report_trigger(19, 0)
    # 2026-10-10 is a Saturday; the report still runs (schedule covers weekends)
    nxt = trig.get_next_fire_time(None, datetime(2026, 10, 10, 19, 30, tzinfo=NPT))
    assert nxt.astimezone(NPT).strftime("%Y-%m-%d %H:%M") == "2026-10-11 19:00"


def test_19_00_npt_equals_13_15_utc():
    trig = build_report_trigger(19, 0)
    nxt = trig.get_next_fire_time(None, datetime(2026, 10, 10, 0, 0, tzinfo=NPT))
    assert nxt.astimezone(ZoneInfo("UTC")).strftime("%H:%M") == "13:15"


def test_registered_job_fires_at_configured_time(monkeypatch):
    s = BackgroundScheduler(timezone=NPT)
    s.add_job(lambda: None, build_report_trigger(), id=JOB_REPORT)
    job = s.get_job(JOB_REPORT)
    assert job is not None
    nxt = job.trigger.get_next_fire_time(None, datetime(2026, 10, 10, 12, 0, tzinfo=NPT))
    assert nxt.astimezone(NPT).hour == 19 and nxt.astimezone(NPT).minute == 0


def test_scheduler_disabled_by_configuration_does_not_start(monkeypatch):
    class S:  # minimal settings stand-in
        scheduler_enabled = False
    monkeypatch.setattr(sched, "get_settings", lambda: S())
    assert sched.start_scheduler() is None
