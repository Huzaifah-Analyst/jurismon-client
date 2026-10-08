# Rigorous Testing Prompt, JurisMon

> Paste this whole document as the instruction to a testing agent (or follow it
> by hand). It covers the live site at `https://jurismon.com` and the admin
> panel at `/admin`. Reference: `docs/ai/frontend-standard.md` (what "good"
> means) and `docs/ai/frontend-audit.md` (what was already found before this
> run).

---

## Rules for the tester

1. Test the real, running site. Do not assume; open it and watch it happen.
2. Every finding needs: the exact page/URL, the exact steps to reproduce,
   what happened, what should have happened, and a screenshot or network
   trace if the finding is visual or timing-related.
3. Never invent a number, a percentage, or a "likely cause" that wasn't
   directly observed. If the cause is unclear, say so and say what would
   confirm it.
4. Do not create real subscriptions, do not trigger live PayPal charges, do
   not send real emails to addresses you do not own. Use throwaway test
   accounts for signup/login flows.
5. Report in a table: `# | Page | Finding | Severity | Repro steps`. Group by
   page. Severity is High (breaks the product or the business claim), Medium
   (wrong/confusing but not broken), Low (polish).

---

## 1. Performance and loading

- Open DevTools Network tab. Hard-refresh `/`, `/about`, `/account`,
  `/admin`. For each: record total load time, time to first result/content,
  and whether any resource returns uncompressed (`content-encoding` header
  absent on a JSON or HTML response over 1KB).
- Check `Cache-Control` on the HTML response for every page. Note whether
  it's present and what it says.
- Load the homepage, close the tab, reopen it after 30 seconds, and watch
  carefully for a moment where old or placeholder content is visible before
  fresh content replaces it. Record what you saw frame by frame (use
  DevTools' Network throttling set to "Slow 3G" to exaggerate the window if
  needed).
- Search for a common term (e.g. "zoning"). Time how long results take to
  appear from keystroke to render. Repeat 3 times, note variance.
- Check the size in KB of the `/api/search` response for an anonymous
  (signed-out) request vs. a signed-in trial request, same query. Note
  whether the signed-out response contains more data than the 2-item teaser
  it displays.

## 2. Signup, login, verification

- Register a new account with a throwaway email. Confirm the code-entry
  screen appears and the email address shown matches what was typed.
- Submit a deliberately wrong confirmation code. Confirm a clear, specific
  error is shown (not silence, not a generic "error").
- Attempt login with a non-existent email and with a correct email but wrong
  password. Confirm a clear error is shown both times, and the modal does
  not just silently close.
- Attempt to register with an email already in use. Confirm the error names
  the actual problem.
- Password reset: request a reset, check the flow reaches a code-entry
  screen with a sensible message.
- Try submitting every form (register, login, reset) with empty fields.
  Confirm client-side or server-side validation catches it before a network
  call, or with a clear error after.

## 3. Search and results

- Search for a term with zero matches. Confirm the empty state is a
  specific sentence, not a blank area.
- Search, then clear the search box. Confirm it returns to the default
  "latest results" list, not an error or stuck skeleton.
- Click each filter tab (All / Added clauses / Removed clauses / Full
  snapshots). Confirm the count badge on each tab matches the number of
  results actually shown when that tab is active.
- Open at least 5 different results and read their preview text. For each,
  judge: does this read like actual legal/statutory text, or does it read
  like scraped page furniture (navigation labels, menu items, "Download",
  "Share", site breadcrumbs)? List every result where the preview looks like
  garbage, with the source name and section/document title.
- For a locked (gated) result, click "Show full page"/"Show full section".
  Confirm the paywall message is logically consistent with what was already
  visible in the preview, that is, the unlock should plausibly reveal
  something more than what's already shown. If the preview text looks
  identical in kind to what the paywall is "protecting," flag it.
- Click "Copy link" on a result. Confirm the copied URL actually opens that
  specific result (deep link), not just the homepage.
- Click "Open source document" on several results across different
  jurisdictions. Confirm the link goes to a real, live page (not a 404, not
  example.com, not a dead government link) for at least 10 different
  sources.

## 4. Public claims and copy, cross-check against the code

- Record every place on the public site that states a number of
  jurisdictions, sources, or portals: homepage header, homepage status
  line, homepage "Free Preview Mode" banner, About page, meta description,
  JSON-LD. Confirm every single instance uses the current live/tracked
  wording and the current numbers (cross-check against `GET /api/sources`
  at the time of testing), not a stale hardcoded figure.
- Read every claim on the About page against what the codebase actually
  does (crawler adapters, OCR, diffing, search). Flag anything that reads
  as aspirational rather than built.
- Check the pricing shown on the homepage against `GET /api/plans`. They
  must match exactly, including currency and interval.

## 5. Account page, every state

Using real or seeded test accounts, reach and screenshot each of:

- Signed out
- Trial active, no subscription
- Active paid subscription (monthly and annual)
- Paused
- Cancelled, still inside paid period
- Cancelled, past the paid period (expired)
- An API/network error (simulate by blocking `/api/account/subscription` in
  DevTools)

For each state: confirm the copy is grammatically correct and specific
(dates, amounts), confirm no raw internal ID (PayPal subscription ID,
internal UUID) is shown without explanation, confirm the action buttons
available match what should be possible in that state (e.g. no "Pause"
button on an already-paused subscription).

Then exercise the actions for real on a disposable test account:

- Pause a subscription. Confirm PayPal state and local state agree
  afterward (check both, not just the UI).
- Resume it. Same check.
- Cancel it, with a reason. Same check.
- Confirm a transactional email actually arrives in the inbox for each
  action, with the correct plan name, amount, and date, nothing templated
  or wrong.

## 6. Admin panel

- Log in as admin. Confirm every tab loads real data: Sources, Subscribers,
  Plans, Webhook log, Crawl control.
- Edit a plan's name only. Confirm the change appears immediately without a
  server restart, and appears in the price-change history table with the
  correct old and new value.
- Attempt a price edit that does not match PayPal's live price for that
  plan. Confirm it's refused with a clear message showing both numbers.
- Attempt to deactivate the only active plan. Confirm it's refused.
- Trigger a manual crawl. Confirm the UI shows real progress/status, not a
  static "running" that never changes.
- Check the webhook log for entries that look fabricated or suspiciously
  uniform versus ones that look like real PayPal payloads.

## 7. Responsive and visual

- Test every public page (`/`, `/about`, `/account`, `/admin`, `/terms`,
  `/privacy`) at these widths: 375px (small phone), 768px (tablet), 1280px
  (laptop), 1920px (desktop). At each width, confirm: no horizontal page
  scroll, no overlapping text, no element cut off, tap targets at least
  44px on mobile.
- Toggle the OS/browser dark mode setting and reload each page. Confirm
  what happens (the site may not support dark mode yet, note current
  behavior precisely rather than just saying "broken").
- Zoom the browser to 200%. Confirm text reflows rather than overlapping or
  clipping.
- Check the logo at actual rendered size on a high-DPI display (or
  DevTools device emulation with a 3x pixel ratio). Note if it looks soft
  or blurry.

## 8. Accessibility

- Navigate the entire homepage using only the Tab key: search box, filter
  tabs, sort dropdown, each result's expand/copy/open-source buttons,
  header nav, login/register. Confirm every interactive element is
  reachable and shows a visible focus outline.
- Run the browser's built-in accessibility audit (Lighthouse or equivalent)
  on `/`, `/account`, `/about`. Record the score and list every "Serious"
  or "Critical" issue by name.
- Confirm images have `alt` text and icon-only buttons have `aria-label`
  (inspect the DOM, don't just look at the screen).
- Confirm the page announces loading and error states to screen readers
  (`aria-live` regions) rather than silently changing content.

## 9. Error handling and edge cases

- Turn off network (DevTools offline mode) and reload the homepage. Confirm
  a sensible message appears rather than an infinite skeleton or a blank
  page.
- Block the `/api/search` endpoint specifically and reload. Confirm the
  rest of the page (header, nav) still works and the results area shows a
  real error state.
- Submit a search query containing HTML/script-looking text
  (`<script>alert(1)</script>`, `"><img src=x>`) and confirm it is not
  rendered as live HTML anywhere on the page (view source / inspect the
  DOM, don't just eyeball it).
- Try an expired or tampered JWT in `localStorage` on `/account`. Confirm it
  is rejected cleanly (signed-out state or clear re-login prompt), not a
  broken half-rendered page.

## 10. Cross-browser

Repeat section 3 (search) and section 5 (one account state) in at least:
Chrome, Firefox, Safari (or WebKit), and one mobile browser (iOS Safari or
Android Chrome). Note any rendering or functional difference between them.

---

## Deliverable format

A single document with:

1. The full findings table (section 1-10, numbered).
2. A top-5 list: the five worst findings, in order, each with a one-line
   reason it's worse than the others.
3. For every finding, state plainly whether it was reproduced once or
   multiple times, and under what conditions (browser, network speed,
   signed in/out).
4. Nothing in this report should assert a root cause that wasn't directly
   observed in the code or the network trace. "Results are slow" is an
   observation; "results are slow because the backend has no index on this
   column" is a claim that needs the actual evidence (a slow query log, a
   code read) before it goes in the report.
