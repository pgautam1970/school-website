# KVI AI School Intelligence & Daily Reporting Agent

Kashyap Vidyapeeth Inaruwa, Inaruwa-4, Sunsari, Koshi Province, Nepal.

Collects **authorized** school communications (WhatsApp chat exports, Facebook Page data, manual imports),
analyses them with a transparent rules engine (optional hosted LLM), builds a bilingual-ready daily
report, and emails it to **kptcc@gmail.com at 19:00 Asia/Kathmandu** with a PDF attachment. A secure
dashboard holds the evidence, the archive, the action tracker and the delivery logs.

> Principles: no unauthorized access, no scraping, no automated replies, no automated disciplinary or
> grading decisions, sensitive details redacted, every finding linked to its evidence, and every gap in
> coverage stated in the report.

## Quick start (Windows)
```
cd kvi-agent
scripts\windows\setup.bat        # venv, dependencies, .env template, migrations
notepad .env                     # set KVI_SECRET_KEY, KVI_ADMIN_PASSWORD; SMTP and Meta when available
scripts\windows\run_server.bat   # dashboard at http://localhost:8000
```
Full instructions: [docs/INSTALL_WINDOWS.md](docs/INSTALL_WINDOWS.md). Remaining manual steps:
[docs/HANDOVER.md](docs/HANDOVER.md).

## Layout
```
kvi-agent/
├─ app/
│  ├─ main.py            FastAPI app, security headers, CSRF header check, scheduler lifecycle
│  ├─ config.py          settings (env only), school profile, categories, validation checks
│  ├─ db.py / models.py  SQLAlchemy models (UTC-aware datetimes everywhere)
│  ├─ security.py        PBKDF2 passwords, signed sessions, RBAC, audit helper
│  ├─ services.py        generate+send, purge, source health, bootstrap admin
│  ├─ scheduler.py       APScheduler: 19:00 Asia/Kathmandu report, watch-folder polling
│  ├─ connectors/        whatsapp_export (parser), whatsapp_ingest (dedupe/store/watch folder),
│  │                     facebook_graph (Meta client), facebook_ingest (sync + manual import)
│  ├─ analysis/          normalize, nepali_calendar, classify (17 categories), priority (5 levels),
│  │                     dedupe (cross-source), redact, summarizer (rules | LLM), pipeline
│  ├─ reports/           Jinja templates (HTML email + text), renderer, pdf (fpdf2 / WeasyPrint)
│  ├─ delivery/          email_sender: claim, retry/backoff, logs, failure notice, backup, test
│  ├─ api/               routes_auth, routes_sources, routes_reports, routes_admin
│  └─ static/            dashboard (index.html, css/dashboard.css, js/dashboard.js)
├─ migrations/           Alembic (initial schema) — `alembic upgrade head`
├─ scripts/
│  ├─ kvi.py             CLI: init, run-daily, generate, test-email, watch-scan, purge, backup, seed-demo, check-config
│  └─ windows/           setup.bat, run_server.bat, run_daily.bat, register_daily_task.ps1
├─ tests/                86 automated tests + synthetic fixtures (tests/fixtures)
├─ docs/                 install, integrations, email, scheduler, security, backup, troubleshooting, test results, samples
├─ requirements.txt · .env.example · .gitignore
```

## Daily report (sections A–K)
A Principal's briefing · B critical & high alerts with evidence · C class-wise table (all 16 classes,
Playgroup → Class 12, with explicit "no data" states) · D educator coordination · E parent communication ·
F Facebook · G dated deadlines · H action plan (priority, action, role, deadline, evidence) · I positives ·
J coverage & limitations · K tomorrow's focus. A Nepali executive summary is included when available.

See a synthetic example: [docs/sample/SAMPLE_DAILY_REPORT_SYNTHETIC.html](docs/sample/SAMPLE_DAILY_REPORT_SYNTHETIC.html)
and [docs/sample/SAMPLE_DAILY_REPORT_SYNTHETIC.txt](docs/sample/SAMPLE_DAILY_REPORT_SYNTHETIC.txt).

## Status of integrations (honest)
| Source | Status in this build |
|---|---|
| WhatsApp groups | Authorized exports via upload and watch folder: **implemented and tested with synthetic exports**. Live API: **not available** (by design). |
| Facebook Page | Meta Graph client **implemented and tested with mocked responses**. Live connection: **not verified** (no credentials). Manual import: implemented. |
| Email (SMTP) | Delivery, retries, duplicate prevention and logs: **tested with an injected transport**. Live send: **not verified** (no credentials). |
| AI provider | Optional, **failure path tested with a mock**. Live: not verified. Rules engine is the default. |
| PDF | fpdf2 generation **executed and checked**. Devanagari needs a font. |
| Dashboard | **Executed in headless Chromium** at phone (390 px) and desktop (1366 px) widths. |
| Scheduler | Next-run computation **tested**; a real 19:00 firing is **not yet observed** (see SCHEDULER.md). |

## Development
```
.venv\Scripts\activate
python -m pytest -q
python scripts\kvi.py seed-demo --i-understand-synthetic   # SYNTHETIC demo only; needs KVI_DEMO_PASSWORD
```
