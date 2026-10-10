# Scheduler

| Setting | Default | Meaning |
|---|---|---|
| `KVI_TIMEZONE` | `Asia/Kathmandu` | Explicit IANA zone, never the server default. |
| `KVI_REPORT_HOUR` / `KVI_REPORT_MINUTE` | `19` / `0` | Daily report time (requires restart). |
| `KVI_SCHEDULER_ENABLED` | `true` | Runs the in-process job. Run only one server process. |
| `KVI_IMPORT_WATCH_INTERVAL_MIN` | `15` | Watch-folder scan interval. |

- Runs every day, including weekends.
- `misfire_grace_time` is 6 hours, so a restart shortly after 19:00 still runs the job.
- `coalesce` and `max_instances=1` stop duplicate concurrent runs.
- Duplicate safety: a sent report is never regenerated or resent by the scheduler, and a claim in the
  database blocks a second concurrent sender.

## Alternatives
- **Windows Task Scheduler**: `scripts\windows\register_daily_task.ps1` (19:00 with 15-minute retries
  for 5 hours, using the PC clock).
- **Cron / n8n / any orchestrator**: call `python scripts/kvi.py run-daily` at the desired time, or
  call the API (`POST /api/reports/generate` with `{"confirm": true, "send": true}`, leadership login).

## Verification performed
- `tests/test_scheduler.py` computes the next fire time in Asia/Kathmandu: 18:00 → 19:00 the same day,
  19:30 → 19:00 the next day (Saturday included), and 19:00 NPT = 13:15 UTC.
- **Not done:** waiting for a real 19:00 firing in the sandbox. Run the server across one real 19:00
  boundary on the target PC and confirm the `Scheduler started; next report at …` log line.
