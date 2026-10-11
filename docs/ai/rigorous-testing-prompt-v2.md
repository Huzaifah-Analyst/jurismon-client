# Rigorous Testing Prompt v2 — JurisMon

Paste this whole document as the instruction to a testing agent (or follow it by hand). It
supersedes `docs/ai/rigorous-testing-prompt.md` for this and future rounds: same spirit, same
discipline, but sharpened with what the first live pass against `https://jurismon.com` and
`/admin` actually found. Use it both as a **regression check** (did the fixes in
`docs/ai/frontend-fix-plan.md` actually land, cleanly, with nothing new broken) and as a
**general-purpose rigor template** for any future pass on this site.

Reference docs: `docs/ai/frontend-standard.md` (what "good" means), `docs/ai/frontend-audit.md`
and the JurisMon QA Report doc (what was found before), `docs/ai/frontend-fix-plan.md` (what was
promised to be fixed, in what order).

## Rules for the tester (unchanged, non-negotiable)

1. Test the real, running site. Do not assume; open it and watch it happen.
2. Every finding needs: the exact page/URL, the exact steps to reproduce, what happened, what
   should have happened, and a screenshot or network trace if the finding is visual or
   timing-related.
3. Never invent a number, a percentage, or a "likely cause" that wasn't directly observed. If
   the cause is unclear, say so and say what would confirm it.
4. Do not create real subscriptions, do not trigger live PayPal charges, do not send real
   emails to addresses you do not own. Use throwaway test accounts (a public Mailinator inbox
   is fine) for signup/login flows.
5. Report in a table: `# | Page | Finding | Severity | Repro steps`. Group by page. Severity is
   High (breaks the product or the business claim), Medium (wrong/confusing but not broken), Low
   (polish).
6. **New: a claim made by the frontend, the About page, or a code comment is not evidence.**
   Verify it against what the server actually returns or what the repository actually contains.
   "The code says X" and "production does X" are different facts; state which one you checked.
7. **New: when something looks fixed, prove the old failure mode is actually gone**, don't just
   confirm the new behavior exists. If the bug was "X leaks in the response," confirm the
   response no longer contains X, not just that the UI doesn't render it.

## 0. Regression pass: the 25 prior findings

Before any fresh exploration, walk the full findings table from the JurisMon QA Report
(`docs/ai/frontend-fix-plan.md` batches 1 to 3) one by one. For each of the 16 real problems and
3 documented gaps, note: **Fixed / Still broken / Partially fixed / Not attempted**, with the
same repro steps used last time so the comparison is apples to apples. Do not skip this section
even if the fix plan's commit messages claim it's done. Specific traps to check:

- **Item 1 (paywall leak)**: `fetch('/api/search?q=')` signed out. Confirm the response body has
  **no `results` key at all** when `is_gated:true`, not just that it's smaller. Then confirm a
  signed-in trial/admin request still gets the full `results` object (the fix must not have
  over-trimmed the authenticated path).
- **Item 3 (silent admin errors)**: trigger both known 409s (a price that doesn't match PayPal;
  deactivating the last active plan) against the **live** site, not local. Confirm a message
  actually renders in the DOM (query for it, don't just eyeball the screenshot) within 2 seconds
  of the rejected save.
- **Item 4 (undeployed P2-14)**: `GET /api/admin/plans/changes` with a valid admin token must
  return 200, not 405. `document.getElementById('plan-changes-body')` must exist and, after one
  real plan edit, must contain a new row with the correct old and new value.
- **Item 5 (giant result card)**: load the page, measure every `main li` element's
  `getBoundingClientRect().height` via script, not by scrolling and eyeballing. None should
  exceed roughly one screen height without a collapsed "show more" state.
- **Item 9/10 (caching/compression)**: re-pull headers for `/`, `/about`, `/account`, `/admin`,
  `/api/sources`, `/api/plans`, `/api/search`. Confirm `Cache-Control` is present and
  `content-encoding` is present on every JSON response over 1KB.
- **Item 2 (claim vs. content)**: whichever path was chosen (fix sources or soften copy), check
  that the two now actually agree. If sources were fixed, re-run the "open 10 source links"
  check from section 3 below and confirm a majority are now genuinely municipal/county, not just
  that the broken-link count went down.

Anything marked "Still broken" or "Partially fixed" goes straight into the final report's top
findings regardless of what section 1 to 10 below turns up.

## 1. Performance and loading

- Hard-refresh `/`, `/about`, `/account`, `/admin` with DevTools Network open. Record total load
  time, time to first content, and whether any JSON or HTML response over 1KB is missing
  `content-encoding`.
- Check `Cache-Control` on every HTML and API response listed above; note presence and value.
- Load the homepage, navigate away, come back, and watch for a moment (screenshot immediately
  after navigation, then again 2 seconds later) where placeholder or logged-out content is
  visible to an **already-authenticated** user before the real session hydrates. This was a
  confirmed bug last round; confirm it is gone, not just less noticeable.
- Search for a common term 3 times, record latency each time, note the variance. Do not
  attribute a cause unless you have a server-side log or query plan to point to.
- Compare the anonymous vs. signed-in `/api/search` response size for the same query. The
  anonymous one should now be close to the size of its 2-item teaser, not multiples larger.

## 2. Signup, login, verification

Same as before, unchanged: register with a throwaway email, confirm the code screen shows the
right address, submit a wrong code, submit wrong/non-existent login credentials, register an
already-used email, run the password reset flow, submit every form empty. Confirm every path
still shows a specific, accurate error (this was all passing last round; the job here is to
confirm no regression).

## 3. Search and results, content quality

- Zero-match search, clear-search recovery, filter tab counts matching the active filter: same
  checks as before.
- **Read, don't skim, at least 8 result previews.** For each: does it read like actual
  legal/statutory text, or like scraped page furniture (site navigation, "Go to resource,"
  RSS instructions, breadcrumbs)? Name the source and section for every one that's garbage. This
  was the single biggest content finding last round (item 2/6); a partial fix needs a real
  recount, not a spot check.
- Pick 10 "Open source document" links across different results. Open all 10. Note how many are
  genuinely a municipal/county portal versus a national/federal registry. State the count, don't
  estimate it.
- Click "Show full section" on a locked result. Confirm the paywall copy is logically consistent
  with what the preview already showed.
- Copy a result's link, open it in a new tab, confirm it deep-links and auto-expands that exact
  result.

## 4. Public claims and copy, cross-checked against the server

- Every number on the public site (jurisdiction counts, source counts, pricing) gets checked
  against `GET /api/sources` and `GET /api/plans` **at the moment of testing**, not against a
  memory of what it said before.
- Re-read the About page's specific technical claims (named platform integrations, named
  processing steps like OCR or layout stripping) against what the crawler/extractor code and the
  admin Sources table actually show. Flag anything still aspirational.

## 5. Account page, every reachable state

Signed out, trial active, and (new, now that item 7 should be fixed) confirm "Subscribe to
Professional" actually opens a working plan-selection/checkout path from the account page, not
just that it does something. Paid/paused/cancelled states remain out of scope unless a safe
seeded-test method now exists per item 23 of the fix plan; if so, use it and test all of: pause,
resume, cancel-with-reason, confirming PayPal state and local state agree after each action, and
that a transactional email arrives with the correct plan name, amount, and date.

## 6. Admin panel

- Log in, confirm every tab loads real data: Sources, Subscribers, Plans, Price Change History
  (new, confirm it exists and works, see section 0), Webhook log, Crawl control.
- Edit a plan's name only; confirm it updates immediately and a history row appears.
- Attempt a price edit that doesn't match PayPal's live price; confirm both the refusal and that
  the error is now visible on screen.
- Attempt to deactivate the only active plan; same check.
- Trigger a manual crawl. This time, watch the status line for at least 30 seconds without
  reloading the page. It should update on its own (confirm new `/api/admin/crawl/status`
  requests are actually firing over that window), not stay frozen on "started just now."
- Re-check the Sources health table. Count operational vs. broken again; compare the new count
  (especially for US county/city sources specifically) against the 10-of-21-broken baseline from
  last round.

## 7. Responsive and visual

- 375px, 768px, 1280px, 1920px on `/`, `/about`, `/account`, `/admin`, `/terms`, `/privacy`.
  Measure `document.documentElement.scrollWidth` vs `clientWidth` at each width via script, don't
  just look for overflow visually. At 375px specifically, re-check the filter-pill row and the
  top-bar controls (trial badge, email, Account button) that were cramped last round.
- Toggle OS/browser dark mode (`prefers-color-scheme: dark`), reload every page, note current
  behavior precisely.
- Zoom to 200%, confirm reflow not clipping.

## 8. Accessibility

- Tab through the entire homepage: search box, filter tabs, sort dropdown, each result's
  expand/copy/open-source controls, header nav, login/register. Confirm every stop has a visible
  focus indicator (check `outline` and `box-shadow` via computed style, not just by eye).
- If a real Lighthouse or axe run is available this round, run it on `/`, `/account`, `/about`
  and report the score plus every Serious/Critical issue by name. If not available, say so
  explicitly rather than skipping the section silently.
- Confirm images have `alt` text and icon-only buttons have `aria-label` via DOM query.
- Confirm loading and error states use `aria-live` rather than silently changing content.

## 9. Error handling and edge cases

- Block `/api/search` specifically (route interception or a scoped `fetch` override) and reload;
  confirm the rest of the page still works and a real error state shows.
- Submit `<script>alert(1)</script>` and a quote-breakout payload in search; confirm via
  `innerHTML` inspection, not just visual check, that nothing executes.
- Put a tampered/invalid JWT in `localStorage` and load `/account`; confirm a clean re-login
  screen, not a broken half-render.
- True offline (DevTools offline mode, not a fetch override) on the homepage; confirm a sensible
  message, not an infinite skeleton.

## 10. Cross-browser

Repeat section 3 (search) and one account state in Chrome, Firefox, Safari (or WebKit), and one
mobile browser if all four are actually available this round. If only one engine is available,
say so plainly in the report rather than presenting single-browser results as general.

## Deliverable format

1. Section 0's regression table first: Fixed / Still broken / Partially fixed / Not attempted
   for all 25 prior items, each with fresh repro evidence.
2. The full findings table for anything new found in sections 1 to 10, same numbered format as
   before.
3. A top-5 list of the worst items across both the regression table and anything new, each with
   a one-line reason it's worse than the next.
4. For every finding: reproduced once or multiple times, under what conditions (browser, network
   speed, signed in/out).
5. Nothing asserts a root cause that wasn't directly observed in the code or the network trace.
