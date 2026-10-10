# Test results

Environment: Linux sandbox, Python 3.11, Node 22, headless Chromium (executed via `@sparticuz/chromium`).
All WhatsApp, Facebook, report and email data is **synthetic** (`tests/fixtures`). No real student
conversations were used. Test runs did not contact Meta, an SMTP server or an AI provider.

Legend — **EXECUTED**: real code path run end to end. **MOCK**: an external dependency was replaced
with a controlled fake (labelled in the test file). **NOT RUN**: needs school credentials or hardware.

## A. Automated suite (`python -m pytest -q`)
**86 passed, 0 failed** (11 s). Breakdown:

| File | Tests | Covers | Mode |
|---|---|---|---|
| test_whatsapp_import.py | 7 | Multi-group import, timestamps (NPT → UTC), duplicate-safe re-import, watch folder, unmatched files, upload validation | EXECUTED |
| test_language_and_classification.py | 10 | English, Devanagari, Romanized Nepali, code-switching, classification, status (planned vs completed) | EXECUTED |
| test_facebook.py | 5 | Honest "not configured" status, manual import validation and duplicates, API sync, expired-token error | Sync tests: **MOCK** Graph responses |
| test_dedupe_and_priority.py | 7 | Cross-source merge with all references kept; unrelated look-alikes not merged; CRITICAL with evidence; no escalation from caps or punctuation | EXECUTED |
| test_report_pipeline.py | 12 | All 16 classes, no-data vs not-configured states, coverage, alerts with evidence, unanswered questions, redaction, injection, escaping, verified / inferred / recommendation labels, one report per date | EXECUTED |
| test_email_and_pdf.py | 11 | HTML sections A–K, PDF validity, MIME alternatives and attachment, retry with backoff, permanent failure, duplicate prevention, claim lock, not-configured, backup and failure notice, test email | EXECUTED; SMTP transport **MOCK** |
| test_scheduler.py | 6 | 19:00 Asia/Kathmandu trigger, weekend roll-over, 13:15 UTC equivalence, disabled scheduler | EXECUTED (fire-time computation; no real wait) |
| test_security_and_access.py | 14 | RBAC per role, redacted archive, audited reveal, CSRF header, confirmation required, validation, untrusted upload cannot change config/users/scheduler, lockout, cookie tampering, security headers, self-disable prevention, group registry rules | EXECUTED |
| test_api_and_dashboard.py | 8 | Public health, viewport and CSS breakpoints, JS parses (`node --check`), escaping in renderers, role endpoints, honest source status | EXECUTED |
| test_retention_and_privacy.py | 2 | Purge removes only old raw content, audited; retention minimum | EXECUTED |
| test_migrations_and_ai_fallback.py | 4 | Alembic upgrade creates all tables and `alembic check` matches models; AI failure falls back to rules and says so; prompt delimits untrusted data; scheduled retry does not regenerate or resend a sent report | EXECUTED; AI provider **MOCK** |

## B. Acceptance tests (spec section 13)
| # | Test | Result | Mode / note |
|---|---|---|---|
| 1 | Import sample WhatsApp conversations from multiple class groups | Passed | EXECUTED (8 synthetic groups, 33 messages) |
| 2 | Educator messages: lesson plans, homework, meetings, deadlines | Passed | EXECUTED |
| 3 | Nepali, English and Romanized Nepali messages | Passed | EXECUTED |
| 4 | Facebook posts and comments | Passed | Sync **MOCK**; manual import EXECUTED |
| 5 | Repeated announcements detected, source references kept | Passed | EXECUTED |
| 6 | Urgent issue identified with explained priority and evidence | Passed | EXECUTED |
| 7 | Report contains every configured class and explicit coverage indicators | Passed | EXECUTED |
| 8 | Visually correct HTML email and PDF attachment | Passed (HTML rendered and inspected at 900 px and 390 px; PDF text extracted and checked) | EXECUTED; **not sent** to a real inbox |
| 9 | Scheduling at 19:00 Asia/Kathmandu | Passed (computation) | A real 19:00 firing **NOT RUN** — see SCHEDULER.md |
| 10 | Failed source connection reported accurately | Passed | Graph error **MOCK**; Facebook status and source health EXECUTED |
| 11 | Retry behaviour and duplicate-send prevention | Passed | Transport **MOCK**; logic EXECUTED |
| 12 | Role-based access and sensitive-data redaction | Passed | EXECUTED |
| 13 | Untrusted text cannot change config or execute commands | Passed | EXECUTED |
| 14 | Dashboard usable on mobile and desktop | Passed | EXECUTED in headless Chromium (see C) |
| 15 | Report distinguishes verified facts, inferences, recommendations | Passed | EXECUTED (labels and per-alert status) |

## C. Browser verification (headless Chromium, synthetic demo database)
Run against the live server (`uvicorn app.main:app`, port 8000) with the demo login.

| Check | Result |
|---|---|
| Login page renders at 1366 px | Passed |
| Overview, reports, classes, alerts, archive, sources, groups, email logs, scheduler, privacy, system pages render at 1366 px with no page errors | Passed (12 pages) |
| Overview at 390 px: no horizontal overflow | Passed (0 px after fix; was 99 px before) |
| Mobile navigation menu opens | Passed |
| Archive at 390 px: no horizontal overflow | Passed (0 px) |
| "Generate Today's Report" opens a confirmation dialog | Passed |
| HTML report at 900 px renders all sections | Passed (visual inspection) |
| HTML report at 390 px: no horizontal overflow | Passed (0 px after fix; was 235 px before) |

Limitation: the sandbox has no Devanagari font, so Nepali text appears as boxes in these screenshots.
Systems with standard Nepali fonts display it correctly; this was not verified on Windows.
Browser: Chromium only. Firefox, Edge and Safari were not tested.

## D. Not yet verified (requires school credentials or the target PC)
| Item | Why not run |
|---|---|
| Real SMTP delivery to kptcc@gmail.com | No SMTP credentials supplied |
| Live Meta Graph API sync and permissions | No Page ID / token supplied; Page URL not yet confirmed |
| Live AI provider | No provider credentials supplied |
| 19:00 NPT firing observed on the target PC | Needs the target machine running across the time |
| Windows setup.bat, run_server.bat, Task Scheduler registration | Written for Windows; the sandbox is Linux. Run on the target PC |
| PostgreSQL deployment | Not tested in this sandbox (SQLite only) |
| Real WhatsApp exports from school groups | Not used, by design, without authorization |

## E. How to reproduce
```
cd kvi-agent
python -m pytest -q
alembic upgrade head   # against a fresh database
```
