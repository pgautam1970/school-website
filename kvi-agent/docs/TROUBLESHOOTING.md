# Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Dashboard says **Email delivery is not configured** | SMTP variables are empty. The report is archived only. Fill `KVI_SMTP_*` and run Send Test Email. |
| Report status **failed**, log says `SMTP authentication failed (535)` | Wrong `KVI_SMTP_USERNAME`/`KVI_SMTP_PASSWORD`, or the provider requires an app-specific password. |
| Log says `Transient network error` repeatedly | Firewall or wrong port. Test with `python scripts\kvi.py test-email`. 587 needs STARTTLS. |
| A group shows **no data today** | No export was imported for it. Upload it, or put the file in the watch folder with the group name in the file name. |
| Watch-folder file skipped: *No registered group matches* | Rename it to include the registered group name, or register the group. |
| Import reports *malformed line(s)* | The export has unusual lines. Imported lines are kept; malformed ones are counted, and the group's status is `partial`. |
| Facebook: *Not connected* / Graph error 190 | Token expired or revoked. Create a new Page token (see `META_FACEBOOK_SETUP.md`). |
| Facebook: *Graph API error 200* | Missing permission on the app. Check the permissions list. |
| Nepali text shows as boxes or `?` in the PDF | No Devanagari font configured. Set `KVI_PDF_FONT_PATH` to a Devanagari-capable TTF (for example Noto Sans Devanagari). The HTML email shows Nepali on systems with standard fonts. |
| Login says *Too many failed attempts* | Lockout after 5 failures for 15 minutes (`KVI_LOGIN_MAX_FAILURES`, `KVI_LOGIN_LOCK_MINUTES`). Wait, or restart the server to clear it (the counter is in memory). |
| *Role changed; please log in again* | An administrator changed your role. Sign in again. |
| Browser shows 403 *Missing X-Requested-With* | You are calling the API from a script without the header. Add `X-Requested-With: kvi-dashboard`. |
| Two servers both run the scheduler | Run one server process. Stop the other one. Duplicate sends are blocked anyway, but avoid it. |
| `alembic` fails with *table already exists* | The database was created by an earlier start. Run `python scripts\kvi.py init`, which stamps it. |
| `check-config` shows `SECRET_KEY` not set | Set `KVI_SECRET_KEY`. The server refuses to start in production without it. |

## Collecting information for support
`python scripts\kvi.py check-config`, the **System health** page, and the server log. Never send `.env`
or database files to anyone outside the school.
