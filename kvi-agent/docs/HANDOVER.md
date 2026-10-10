# Handover — remaining manual steps (owner: school administration / IT)

The system is built and tested. The items below need school information, accounts or decisions that
only the school can provide. None of them requires editing code.

## A. Must do before live use
1. **Change the bootstrap admin password** after the first login, and create named accounts for the
   Principal, leadership, staff and any viewers. Remove the demo account (`demo_leadership`) if it exists.
2. **Set `KVI_SECRET_KEY`** (random, 32+ characters) and `KVI_ENV=production` in the real `.env`.
3. **Configure SMTP** (`EMAIL_SETUP.md`), then run *Send Test Email* and confirm the message reaches
   kptcc@gmail.com. The first daily report will be sent at 19:00 Asia/Kathmandu.
4. **Confirm the official Facebook Page** and its URL, then configure Meta access (`META_FACEBOOK_SETUP.md`).
   Until then the Facebook section says "not connected".
5. **Register the WhatsApp groups** in the registry: class-wise groups, class parent-teacher groups,
   educator and department groups, administration. Enter each group's category, class and administrator role.
6. **Record written authorization** for each group and the member notice required by school policy and
   Nepali law, then tick "authorization on file". Do not start collecting from a group before this.
7. **Set the scheduler mode**: in-app (`KVI_SCHEDULER_ENABLED=true`, recommended) or Task Scheduler.
8. **Set up HTTPS** through a reverse proxy if the dashboard will be reachable beyond the school LAN.
9. **Schedule backups** (`BACKUP_RESTORE.md`) and run one restore test.

## B. Should do
10. Provide a **Devanagari-capable TTF** and set `KVI_PDF_FONT_PATH` so Nepali text appears in the PDF.
11. Confirm the **retention period** (default 365 days) and the **redaction** setting with the Principal.
12. Decide whether an **AI provider** is wanted. If yes, set `KVI_AI_API_BASE`, `KVI_AI_API_KEY`,
    `KVI_AI_MODEL`. Review a sample of its output before relying on it. The rules engine works without it.
13. Decide the **backup recipient** (`KVI_BACKUP_RECIPIENT`), or leave it disabled.
14. Agree the **weekly routine** for exports: who exports which groups, by what time, into which folder.

## C. Known limits that need a human decision
- Live WhatsApp group reading is not possible through approved APIs. The export routine is the working method.
- Facebook reach and follower data are available only where Meta provides them through the connected Page.
- Two CRITICAL signals about the same incident are listed separately until a person connects them.
- The sandbox could not reach real SMTP, Meta or an AI provider. Those integrations were tested with mocks.
  Run section A3 and A4 on the target machine and check the Email logs and Facebook status.

## D. What was verified and how
See `TEST_RESULTS.md`. Mock tests and executed tests are listed separately.
