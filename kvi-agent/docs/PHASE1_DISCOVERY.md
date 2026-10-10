# Phase 1 — Discovery, constraints and architecture decisions

## 1. Environment inspected
- Repository `pgautam1970/school-website` contained a static school website (`index.html`, `app.js`,
  `styles.css`) and a to-do app. Both were left untouched. The agent lives in `kvi-agent/`.
- Tooling available: Python 3.11, Node 22, npm, Git. Docker and `psql` are **not** installed in the
  sandbox. WeasyPrint's system libraries (Pango) are **not** installed.
- Outbound internet is limited to GitHub, npm, PyPI. Google/Playwright browser CDNs are **blocked**.

## 2. Integration constraints (researched; re-verify before go-live)

### WhatsApp
- The **WhatsApp Business Platform Cloud API** is built for business-customer messaging. It does **not**
  give read access to ordinary existing class or teacher groups, their histories, or arbitrary groups.
  The system therefore does **not** claim a live WhatsApp connection.
- Unauthorized scraping, QR/session reuse and browser automation are prohibited and are not implemented.
- **Supported acquisition method implemented:** administrator-authorized chat exports
  (WhatsApp: group → More → Export chat → *Without media*). Delivered via:
  1. dashboard upload (one or many `.txt` files per group, max 5 MB each);
  2. a watch folder (`KVI_IMPORT_WATCH_DIR`) scanned on a timer; files are matched to registered groups by name;
  3. the CLI (`scripts/kvi.py watch-scan`).
- Export format parsing covers Android/iOS bracketed and plain formats, 2- and 4-digit years,
  AM/PM, multi-line messages, system lines and media placeholders.

### Facebook (Meta Graph API)
- Official Page access only: Page feed, comments, reactions, insights, via a Page access token
  stored in the environment. Requested permissions (verify current names in Meta's documentation):
  `pages_show_list`, `pages_read_engagement`, `read_insights`, and the permission for reading user
  comments on Page posts.
- Advanced-access requirements may apply to Pages managed by other people; see `META_FACEBOOK_SETUP.md`.
- Private profiles, Messenger, closed groups: **not** accessed.
- Fallback: manual post import (text, URL, optional date and staff-entered counts), labelled `manual`.
- Reach, impressions and follower growth are **not** estimated. Unknown counts stay `n/a`.

### AI analysis
- Default: a deterministic, auditable **rules engine** (keywords in English, Devanagari and Romanized
  Nepali; priority rules; deduplication). It works offline and is labelled `rules` in every report.
- Optional: any OpenAI-compatible chat endpoint (`KVI_AI_*`). It is used only for summary prose.
  Message content is passed as delimited, untrusted data; the model has no tools. On any failure the
  rules output is used and the report states `rules(llm-failed)`.
- **Not verified live:** no AI provider credentials were available. The failure path is tested with a mock.

### Email
- SMTP (any transactional provider's SMTP relay, or a school mailbox). STARTTLS or implicit SSL.
- **Not verified live:** no SMTP credentials were available. All SMTP behaviour is tested with an
  injected fake sender (retry, backoff, duplicate prevention, permanent failure, backup, failure notice).

### PDF
- Layered: WeasyPrint (if installed with system libraries) → **fpdf2** (pure Python, used here).
  If generation fails, the email still goes out without the attachment and the failure is recorded.
- Devanagari text in the PDF requires a Devanagari-capable TTF (`KVI_PDF_FONT_PATH`). Without it, Nepali
  sections are omitted from the PDF and the omission is stated on the page. The HTML email is unaffected.

### Scheduling
- Primary: in-process APScheduler with an explicit `ZoneInfo("Asia/Kathmandu")` cron trigger at 19:00.
- Fallback: Windows Task Scheduler (`register_daily_task.ps1`), which retries every 15 minutes for 5 hours.
  Retries are harmless because a report already accepted by the provider is never regenerated or resent.
- **n8n was not adopted.** The CLI and the authenticated API give n8n or any other orchestrator a
  clean trigger. Running n8n would add a second system to operate without a need in this deployment.

### Database and frontend
- SQLite for development and the demo; PostgreSQL is supported through `KVI_DATABASE_URL` but **not tested
  in this sandbox**. Schema is managed by Alembic (`migrations/`), verified with `alembic check`.
- Frontend: a dependency-free single-page dashboard (HTML/CSS/vanilla JS) served by FastAPI.
  Chosen over React/Next.js to keep the Windows install free of Node tooling. Every message-derived
  value is HTML-escaped in the client and autoescaped in server templates.

## 3. Architecture

```
  WhatsApp exports ─┐                       ┌─> Analysis pipeline ─> Daily report (HTML/text/PDF)
  (upload / folder) ├─> Ingest & dedupe ─> Messages DB ─┤                           │
  Meta Graph API ───┤   (preserve NPT ts)                │  classify · priority ·     ▼
  Manual FB import ─┘                                    │  dedupe · evidence         Email delivery
                                                         └──> Action register        (claim · retry ·
  Scheduler (19:00 NPT) ─────────────────────────────────────────> CLI / API ───────────  log · backup)
  Dashboard + API (roles, audit) ────────────────────────────────────────────────────────────┘
```

Modules (`kvi-agent/app/`): `connectors/` (WhatsApp, Facebook), `analysis/` (normalize, classify,
priority, dedupe, redact, summarizer, pipeline), `reports/` (templates, renderer, pdf), `delivery/`
(email sender), `scheduler.py`, `services.py`, `security.py`, `api/` (routes), `static/` (dashboard).
