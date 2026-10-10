# Email setup (SMTP or transactional provider)

Set these in `.env`. None of them is a secret except `KVI_SMTP_PASSWORD`.

| Variable | Example | Notes |
|---|---|---|
| `KVI_SMTP_HOST` | `smtp.provider.example` | Empty = delivery disabled (reports are still archived). |
| `KVI_SMTP_PORT` | `587` | 587 + STARTTLS (default) or 465 + `KVI_SMTP_SSL=true`. |
| `KVI_SMTP_USERNAME` / `KVI_SMTP_PASSWORD` | | Provider-issued credentials. |
| `KVI_SMTP_FROM` | `KVI School <no-reply@yourdomain>` | Must be an address your provider allows. |
| `KVI_REPORT_RECIPIENT` | `kptcc@gmail.com` | Daily report recipient. |
| `KVI_BACKUP_RECIPIENT` | *(empty)* | Leave empty to keep backup delivery disabled. |

## Verify
1. Dashboard → **Send Test Email** (admin, confirmation required) or `python scripts\kvi.py test-email`.
2. The result shows the provider's reply. "accepted" means the server accepted the message. It does not
   guarantee inbox placement. Check spam folders the first time.
3. Check **Email delivery logs** for every attempt.

## Behaviour
- Retries: transient network and 4xx errors, with exponential backoff (2 s, 4 s, 8 s ... capped at 60 s),
  up to `KVI_EMAIL_MAX_RETRIES` retries. Authentication and 5xx errors are not retried.
- Duplicate prevention: a report accepted once is never sent automatically again. A manual resend is
  an admin action with confirmation, and it is audited.
- Failure notices go to the backup recipient, if configured. Otherwise the failure is shown on the
  dashboard and logged.
- A report that was generated but not accepted is shown as `failed` or `no_email_config`, never `sent`.

## Provider notes
Gmail-style recipients (kptcc@gmail.com) receive mail from any SMTP provider that authenticates correctly.
Set SPF, DKIM and DMARC on the sender domain to improve delivery. Those are DNS settings for the domain owner.
