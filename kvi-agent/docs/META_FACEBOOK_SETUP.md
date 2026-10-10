# Meta (Facebook Page) setup

The Graph API is used only for the school's own Page. Verify each step against Meta's current
developer documentation, because permission names and review rules change.

1. **Confirm the official Page.** The school website currently links to a generic `facebook.com` URL.
   Find the official Kashyap Vidyapeeth Inaruwa Page (check the website footer and the school's
   verified contact details), and record its URL and Page ID. Do not guess the URL.
2. **Create a Meta developer app** at developers.facebook.com (type: Business). Add the Facebook Login
   product only if you need it for the token flow.
3. **Request Page permissions** for the app: `pages_show_list`, `pages_read_engagement`, `read_insights`,
   and the permission that allows reading comments on Page posts. Standard access works for admins of
   the Page. Advanced access may require App Review.
4. **Create a Page access token** from a user who is an admin of the Page, using the Graph API Explorer,
   then exchange it for a long-lived token. Store it only in `.env` as `KVI_FB_ACCESS_TOKEN`.
5. Set `KVI_FB_PAGE_ID` and `KVI_FB_PAGE_URL` in `.env`. Restart the server.
6. Dashboard → **Facebook Page → Sync from Meta API now**. The status must read *Connected* with the
   Page name. If it does not, the error text from Meta is shown in full.

## Token safety
- Never paste the token into chat, tickets or the dashboard. It lives in `.env` only.
- Tokens expire or are revoked when a Page admin changes. The sync then fails and the dashboard says so.
- Rotate tokens if they are exposed.

## What is collected
Posts in the reporting window, with text, timestamps, permalinks and media type. Comments and reaction
counts only where Meta returns them. No private profiles, Messenger threads or closed groups.
