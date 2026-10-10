# Backup and restore

## What must be backed up
1. The database (`KVI_DATABASE_URL`): users, groups, messages, reports, actions, email and audit logs.
2. Generated PDFs (`data/reports/`), which are also reproducible from the database.
3. The `.env` file, stored separately and encrypted (it contains secrets).
4. Pending watch-folder files, if any.

## Backup (SQLite)
```
python scripts\kvi.py backup --out D:\KVI-Backups
```
Uses SQLite's online backup API, so it is consistent while the server runs. The result folder holds
`kvi.db` and `reports\`. Verify with `sqlite3 kvi.db "pragma integrity_check;"` (should print `ok`).

## Backup (PostgreSQL, if used)
`pg_dump --format=custom --file=kvi.dump "postgresql://USER@HOST/kvi_intel"` (password via `PGPASSWORD`
or a `.pgpass` file, never on the command line in shared logs).

## Restore (SQLite)
1. Stop the server.
2. Copy the backup `kvi.db` over `data\kvi.db`. Keep the old file until the restore is verified.
3. Restore `reports\` into `data\reports\`.
4. Start the server, then run `python scripts\kvi.py check-config`.
5. Open the report archive and confirm the latest dates are present.

## Restore (PostgreSQL)
`pg_restore --clean --if-exists -d kvi_intel kvi.dump`, then `alembic upgrade head`.

## Schedule
Daily backup at 18:30 (before the report) using Task Scheduler: run `scripts\kvi.py backup`. Keep at least
30 days of daily backups, and copy at least one a week off-site, encrypted.

## Retention
Dashboard → Privacy & retention, or `python scripts\kvi.py purge --days 365`. Purge removes raw WhatsApp
message text and Facebook comments older than the retention period. It keeps daily reports, action items
and delivery logs. Backups are subject to the same retention policy, so set a backup retention limit too.
