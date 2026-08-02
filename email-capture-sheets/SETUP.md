# Email capture via Google Sheets — one-time setup

Simpler path than the Cloudflare/GitHub version: no tokens, no CLI, no
third-party account. Just Google, which you already use. Estimated time:
10 minutes.

## 1. Create the Sheet

1. Go to sheets.google.com -> **Blank spreadsheet**.
2. Name it something like **Case Analytica — Email List**.
3. Rename the first tab (bottom-left) to **Subscribers**.

## 2. Add the script

1. In the Sheet: **Extensions -> Apps Script**. This opens a script editor
   bound to this specific Sheet.
2. Delete whatever boilerplate code is in `Code.gs`.
3. Paste in the full contents of `Code.gs` from this folder.
4. Click the save icon (or Ctrl/Cmd+S). Name the project if it asks, e.g.
   "Email Capture."

## 3. Deploy it as a Web App

1. Top right: **Deploy -> New deployment**.
2. Click the gear icon next to "Select type" -> choose **Web app**.
3. Settings:
   - **Execute as:** Me (your Google account)
   - **Who has access:** Anyone
4. Click **Deploy**.
5. The first time, Google will show an "authorize access" prompt, then an
   "unverified app" warning screen. That's expected, it's your own script:
   click **Advanced** -> **Go to Email Capture (unsafe)** -> **Allow**.
   (Google shows this for any Apps Script project not published to their
   marketplace. It's normal and only ever asks once.)
6. Copy the **Web app URL** shown after deploying. It ends in `/exec`.

## 4. Point the site at it

Open `Website/guide.html`, find this line near the bottom (search for
`SHEETS_ENDPOINT_URL`):

```js
var SHEETS_ENDPOINT_URL = "REPLACE_WITH_YOUR_APPS_SCRIPT_URL";
```

Paste in the real `/exec` URL from step 3, save, commit, and push.

## 5. Test it

1. Visit the live guide page and submit a real email.
2. You should see a confirmation and the PDF should open in-browser
   immediately (this happens regardless of email delivery).
3. Check the Sheet — a new row should appear within a couple seconds, no
   refresh needed if you leave it open (Sheets auto-updates).
4. Check that inbox — an email from your Google account with subject
   "Your guide: What New York Doesn't Tell You After an Arrest" should
   arrive within a minute or two. Check spam if it doesn't show up in the
   first couple minutes; mail sent via MailApp from a personal Gmail
   sometimes lands there the first time.
5. Whenever you want a local copy of the list: **File -> Download ->
   Comma Separated Values (.csv)** from inside the Sheet.

## 6. Turn on the daily article digest (optional)

The same script can also email everyone in Subscribers whenever a new
article goes up on the site — no separate list or CMS needed, it reads
straight from `assets/data.js`.

1. Paste the current `Code.gs` in (it already includes the digest
   functions below the email-capture code) and save.
2. **Run `markAllCurrentArticlesAsSent` once, first.** Use the function
   dropdown next to Run/Debug at the top of the editor, pick
   `markAllCurrentArticlesAsSent`, click **Run**. This marks every article
   currently on the site as "already sent" in a new `SentArticles` tab, so
   the very first daily run doesn't blast the entire back catalog at
   subscribers. Skipping this step means everyone gets ~20 emails at once
   the first time the trigger fires.
3. The first run will likely prompt another authorization screen, same
   pattern as before (Advanced -> Go to [project] (unsafe) -> Allow) —
   this one grants permission to fetch external URLs
   (`UrlFetchApp`, used to read `data.js` off the live site).
4. **Run `createDailyArticleTrigger` once, second.** Same dropdown, pick
   it, click Run. This sets up a time-based trigger that runs
   `sendDailyArticleDigest` once a day around 9am. You can also see/edit
   it later under the **Triggers** icon (clock) in the left sidebar.
5. From then on, it runs unattended: each day it checks `data.js` for any
   slug not yet in `SentArticles`, and if there's at least one, emails a
   digest (one article or several, whatever's new) to everyone in
   Subscribers, then logs those slugs as sent.
6. If a day has no new articles, nothing gets sent — silent no-op, check
   **Executions** in the sidebar if you want to confirm it ran.

**Notes specific to the digest:**

- **Publishing an article is the only step needed** for it to show up in
  the next day's digest — no separate "add to list" action. It reads
  `ARTICLES` from `data.js` directly, so anything added there per the
  existing "HOW TO ADD A NEW ARTICLE" instructions at the top of that file
  is automatically picked up.
- **Unsubscribe is built in (2026-08-02).** Every digest email now carries
  a personal unsubscribe link back to the same `/exec` URL. Clicking it
  removes that row from `Subscribers` and logs it (email + timestamp) in a
  new `Unsubscribed` tab, created automatically the first time anyone
  unsubscribes. The link includes a short signature so a stranger can't
  unsubscribe an address just by guessing it, but this is anti-abuse
  obfuscation, not real security (see `UNSUB_SALT` in `Code.gs`) — fine for
  a small personal list, not something to rely on for a large one.
- **Digest links now carry UTM tags** (`utm_source=newsletter&utm_medium=
  email&utm_campaign=daily_digest`) so traffic from these emails shows up
  distinctly in the site's existing Google Analytics, instead of being
  indistinguishable from any other referrer.
- **This means Code.gs changed.** Per the note below on editing `Code.gs`:
  paste the updated file into the Apps Script editor and deploy a **new
  version** (Deploy -> Manage deployments -> edit -> New version -> Deploy).
  Saving alone does not push this to the live `/exec` URL, and the old
  version will keep sending digest emails with no unsubscribe link until
  that redeploy happens.
- **Email quota is shared** with the guide-signup confirmation emails —
  all `MailApp.sendEmail` calls count against the same 100/day (personal
  Gmail) or higher (Workspace) ceiling. At current subscriber counts this
  isn't close to a concern.
- **To pause it:** open **Triggers** (clock icon) in the Apps Script
  sidebar, find the `sendDailyArticleDigest` trigger, and delete it. The
  guide signup flow is unaffected either way.

## Notes

- **Two things happen on submit, independently:** the PDF opens directly
  in the visitor's browser tab (via `guide.html`'s own JS, instant, never
  fails), and a copy is emailed to them via `MailApp.sendEmail` from
  `Code.gs` (goes out from your Google account, can occasionally fail or
  land in spam). If the email fails, the visitor still gets the PDF right
  away and the lead is still captured in the Sheet — email delivery is a
  bonus layer, not the only way the guide reaches them.
- **MailApp quota:** a personal Gmail account gets 100 emails/day sent via
  Apps Script; Google Workspace accounts get more. Fine for a lead-capture
  form at normal volume. If you ever hit the ceiling, sends past the quota
  are silently dropped (the script catches the error so the form still
  reports success) — check Apps Script's execution log if subscribers
  report not receiving anything and the count seems high.
- **Duplicates are skipped in the Sheet** — resubmitting the same email
  won't add a second row, but it will resend the guide email (useful if
  someone lost the original).
- **Spam:** there's a honeypot field built in already (see `guide.html`);
  bots that fill every field get silently dropped. If real spam shows up
  later, the next upgrade is adding a CAPTCHA (Cloudflare Turnstile is
  free) to the form — flag it and it can be added.
- **If you ever edit `Code.gs`:** go to **Deploy -> Manage deployments ->
  edit (pencil icon) -> Version: New version -> Deploy**. Just saving the
  script does not push changes to the live `/exec` URL on its own.
- **Revoking access:** Deploy -> Manage deployments -> Archive (or delete)
  the deployment. The form will show a connection error, but the direct
  PDF download link keeps working — nothing else breaks.
- **Why `text/plain` in the fetch call in guide.html:** Google Apps Script
  web apps don't handle CORS preflight requests cleanly. Sending the
  request body as `text/plain` instead of `application/json` avoids
  triggering a preflight in the first place — Apps Script still parses it
  fine as JSON on its end. Leave that as-is; it's not a typo.
