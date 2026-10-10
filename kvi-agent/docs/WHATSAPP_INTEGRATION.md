# WhatsApp integration — what is supported and how to use it

## What the system can and cannot do
| Capability | Status |
|---|---|
| Live reading of existing class / teacher groups via a Meta API | **Not available.** The Business Platform API does not provide this access. The system never claims it. |
| Authorized chat-export import (upload) | **Implemented.** |
| Authorized chat-export import (watch folder, every `KVI_IMPORT_WATCH_INTERVAL_MIN` minutes) | **Implemented.** |
| Duplicate detection and preservation of original timestamps | **Implemented.** Dedupe key = timestamp + sender + text. Timestamps are stored as UTC and shown in NPT. |
| Coverage: which groups supplied data today | **Implemented** (registry, report section C and J). |
| Scraping, QR/session reuse, browser automation | **Prohibited — not implemented.** |

## Step-by-step: getting an export from a group
1. A group administrator (with the school's written authorization and an informed membership notice)
   opens the group → **⋮ / group info → More → Export chat → Without media**.
2. The export is a `.txt` file. Save it in a folder named by group, e.g. `Class 5 Science - 2026-10-10.txt`.
3. Upload it in the dashboard: **Source connections → Upload an authorized chat export**, choosing the
   registered group. Or copy it into the watch folder (`data\imports`). File names must contain the
   registered group name, e.g. `Class 5 Science`. Unmatched files are left in place and reported.
4. After a successful import the file is renamed `*.txt.imported`. Re-importing the same file is safe.

## Registering groups (no code changes needed)
Dashboard → **WhatsApp group registry → Add group**. Fields: name, category, class, academic year,
group administrator (a role, not a personal number), collection method, reporting inclusion and an
"authorization on file" checkbox. Deactivate or archive groups from the same page. Archived groups keep
their history but are excluded from reports.

## Limits you should communicate to staff
- An export contains only what the exporter could see. Messages deleted before export are absent.
- Exports do not contain media, so images, PDFs and voice notes are not analysed. Their presence is
  recorded as a media placeholder only.
- Sender labels are the names shown in WhatsApp. Teachers are inferred from name patterns and the group
  category. Treat this as an inference, which the report labels as such.
