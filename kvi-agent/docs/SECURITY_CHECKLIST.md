# Security and privacy checklist

Legend: ✅ implemented and tested · 🟡 implemented, needs your operational action · ⛔ not implemented (by design or not yet)

## Access and authentication
- ✅ Role-based access: viewer < staff < leadership < admin, enforced on every API route (tests in `test_security_and_access.py`).
- ✅ Passwords hashed with PBKDF2-SHA256, 240 000 iterations, random salt. Minimum 12 characters for new users.
- ✅ Signed session cookie (HMAC-SHA256), HttpOnly, SameSite=Lax, 12-hour expiry, `Secure` in production.
- ✅ Tampered cookie rejected. Role change forces re-login.
- ✅ Login lockout after 5 failures for 15 minutes (in-memory, per username).
- ✅ State-changing API calls require `X-Requested-With: kvi-dashboard`, which blocks cross-site form posts.
- ✅ Admins cannot disable or demote their own account.
- 🟡 Change the bootstrap admin password after first login. Enable HTTPS (see below).
- ⛔ Multi-factor authentication. Recommended if the server is internet-facing. Add at the reverse proxy or via an identity provider.

## Sensitive data
- ✅ Phone numbers, e-mail addresses and long ID numbers are redacted before classification, report text and archive view (`analysis/redact.py`).
- ✅ Staff see redacted text and masked sender names. Original text is shown only to leadership and admins who choose to reveal it, and every reveal is audited.
- ✅ Reports store redacted excerpts only. The PDF and email use the same redacted data.
- ✅ Routine reports do not extract health, counselling or family details. Sensitive keywords are not used for summaries.
- ✅ No automated disciplinary, admission, grading or employment decision is produced. Priorities are explained with evidence and reviewed by humans.
- ✅ Sentiment is not used as evidence against anyone. Teachers are not ranked. Message volume is labelled as not a quality measure.
- ✅ Parent concerns are grouped and described neutrally; parents are not labelled.
- 🟡 Sender identity is taken from WhatsApp display names. Confirm group membership and authorization locally.
- 🟡 Written authorization and member notice for each group: tick "authorization on file" only after you have it.

## Untrusted input
- ✅ Imported chat text, file names and Facebook content are treated as data. There is no `eval`, no shell call and no template execution on message content. Jinja autoescaping is on; the dashboard escapes all message-derived values.
- ✅ Injection test: messages containing "ignore previous instructions", shell commands and `<script>` do not change configuration, users, scheduler state, or SMTP settings, and do not execute (`test_untrusted_upload_cannot_alter_config_users_or_scheduler`, `test_injected_instructions_do_not_change_configuration_or_run_commands`).
- ✅ Upload limits: `.txt` only, 5 MB max. Manual post URLs must be `http(s)`; `javascript:` is rejected.
- ✅ LLM prompt: message content is wrapped in `<<<DATA>>>` markers with an instruction to ignore instructions inside it. The model has no tools and its output is used only as prose.
- ✅ No automatic replies to parents, teachers or students. The system only reads, analyses and reports.

## Transport, secrets and headers
- ✅ Secrets only in environment variables (`.env`, gitignored). Nothing hardcoded. `.env.example` contains placeholders only.
- ✅ Production refuses to start with a default or `CHANGE_ME` secret key (`lifespan` check, `check-config`).
- ✅ Security headers: CSP (`default-src 'self'`, `frame-ancestors 'none'`), `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`, `Permissions-Policy`. API responses are `no-store`.
- 🟡 HTTPS: run behind a reverse proxy with a valid certificate (for example Caddy or IIS with ARR). Set `KVI_ENV=production`. Bind the app to `127.0.0.1` behind the proxy in that case.
- 🟡 Firewall: expose only the proxy's port to the school network or internet.

## Audit and retention
- ✅ Audit log for logins (success and failure), report generation, sends, resends, test emails, exports (PDF and HTML), archive reveals, group and user changes, settings changes, imports, purges. Visible to admins.
- ✅ Configurable retention with a purge action. Purge is itself audited. Minimum retention 30 days.
- 🟡 Backups are subject to the same retention. Set a backup retention limit (see `BACKUP_RESTORE.md`).

## Reliability and integrity
- ✅ Duplicate report sends are prevented by a database claim and an accepted-log check.
- ✅ Retry with exponential backoff only for transient failures.
- ✅ Failed deliveries are recorded and never shown as sent.
- ✅ Structured JSON logs (no message content in logs beyond counts and error types).

## Known limitations (be explicit with leadership)
- ⛔ Incident linking: two separate CRITICAL signals about the same incident are not automatically merged. The Principal must connect them.
- ⛔ Login lockout and sessions are per process. Run one server process.
- ⛔ The rules engine reads keywords. It can miss messages in unusual wording, and it can flag unrelated messages. Verify the evidence before acting.
- ⛔ No live WhatsApp API (see `WHATSAPP_INTEGRATION.md`).
