# Frontend Fix Plan

> Source: the "JurisMon QA Report" doc, tested live against production
> (`https://jurismon.com`, commit `6376244`) on Oct 8, 2026, plus
> `docs/ai/frontend-audit.md`. 25 findings total: 16 real problems, 6
> confirmed-working checks, 3 coverage gaps (documented, not bugs).
>
> **This is a plan only. Nothing here is implemented yet.** Fixes land one
> at a time, in this order, each one verified before moving to the next.

---

## Batch 1: the 5 worst (fix first)

These are the QA report's own "Top 5 worst" list, each one picked because it
either breaks the business model, breaks trust on the first thing a visitor
reads, or means a shipped feature silently doesn't exist in production.

### 1. Paywall is cosmetic, the full locked content is already in the response: SHIPPED (`44e3863`)

- **Where**: `api/main.py:502`, `GET /api/search`
- **What's wrong**: the gated branch returns `"results": results`, the
  complete, untruncated `diffs` and `snapshots` arrays (one `diff_payload`
  alone is 127 KB; one snapshot's `cleaned_text` is 41,650 characters) even
  though `items` is correctly cut to a 2-item teaser. Anyone can read
  everything "Professional" is supposed to cost $49/month for, with a plain
  `fetch`, no login.
- **Confirmed root cause**: yes, read directly. The frontend never uses the
  raw `results` key, it reads `items` and the top-level `total_snapshots`/
  `total_diffs`. `results` can be dropped from the gated response outright.
- **Planned fix**: when `has_access` is false, do not include `results` in
  the response body at all. Keep `total_snapshots`/`total_diffs` (already
  top-level, already correct) so the homepage's result counts keep working.
- **Risk if we get this wrong**: under-trimming leaves the leak; over-trimming
  breaks the authenticated (`has_access: true`) path, which legitimately needs
  the full `results` object. The fix only touches the `not has_access`
  branch.
- **Verify**: anonymous `fetch('/api/search?q=')`, confirm the body has no
  `results` key, confirm `items` and the homepage still render correctly
  signed out and signed in.
- **Done (Oct 8)**: `results` removed from the gated branch. Verified
  locally: anonymous payload dropped from 357,585 to 44,466 bytes (87.5%
  smaller), homepage still renders 2 teaser results and the correct counts,
  no console errors. Two existing tests updated (`test_search_endpoint`,
  `test_search_with_empty_query` now assert `results` is absent, not
  present) and two new regression tests added
  (`test_search_gating_anonymous_response_drops_the_raw_results_dict`,
  `test_search_gating_long_document_teaser_is_capped_not_complete`). Full
  suite: 305 passed. Deployed Oct 8, release `b5f53bb` (superseding `44e3863`). Verified live: anonymous `/api/search?q=` dropped from 357,585 to 1,625 bytes for the exact query that originally leaked. **A second leak in the same endpoint was found after the first fix shipped**: `item['segments']` (what the frontend actually renders a diff-type teaser from) was never capped, only `item['full']` was. Found by the user directly inspecting the live response, not caught by this session's own verification pass. Fixed in `c42d1c5`, same 240-char cap applied to `segments` on the gated path. Full suite: 306 passed.

### 2. The core claim doesn't match the core content

- **Where**: product scope question, not one file. `/about` promises
  Municode/Granicus/CivicPlus municipal integrations; live "Newest" results
  are dominated by national-level foreign legislation (Germany, NZ, UK,
  Australia, Canada), and several previews are unstripped site chrome, not
  legal text.
- **Confirmed root cause**: partially. We know *what* is showing (national
  registries, not municipal sources) because `config/sites.json` and the
  crawl history say so. We do not yet know whether this is a sort-order
  issue (US municipal results exist but sort below the foreign ones) or a
  genuine catalogue-mix issue (the foreign sources are simply producing more
  volume right now because 10 of 21 US county/city sources are broken, item
  12 below).
- **Planned fix**: this is a product/business decision, not a code fix to
  make unilaterally. Two honest options exist: (a) fix the 10 broken US
  sources so municipal content dominates again, which is the real fix but is
  its own piece of crawler work, or (b) if that takes time, soften the About
  page's language so it doesn't overstate what's live right now. **This item
  needs your call before any code changes**: see "Needs a decision" below.
- **Verify**: after whichever path is chosen, re-sort "Newest" and confirm
  the first page of results matches what the About page claims.

### 3. Admin silently swallows its own error messages

- **Where**: `frontend/admin.html`, the plan-save handler (`handleSavePlan`)
  and the catalogue-settings save handler.
- **What's wrong**: a rejected save (409, PayPal price mismatch or
  last-active-plan guard) shows nothing in the UI at all. The admin has no
  way to know why their edit didn't take.
- **Confirmed root cause**: not yet. Code read during the P2-02 build showed
  a `toast(errData.detail || ...)` call on the `!res.ok` path: on paper this
  should already show the error. Needs a live reproduction against the
  current deployed JS to see why the toast isn't appearing (wrong selector,
  JS error earlier in the handler, a toast element that's hidden/mis-styled,
  or production simply not running the code we think it's running).
- **Planned fix**: reproduce first, then fix whatever the reproduction shows.
  Do not patch blind.
- **Verify**: trigger both known 409 cases (price mismatch, deactivate last
  plan) and confirm a visible, readable error each time.

### 4. A "finished" feature isn't actually live

- **Where**: `frontend/admin.html` Price Change History table,
  `GET /api/admin/plans/changes`.
- **What's wrong**: this is ORDER P2-14, built and tested locally
  (`428efa0`), never deployed. Production returns 405 on the endpoint and the
  table doesn't exist in the live DOM.
- **Confirmed root cause**: yes. This isn't a bug, it's an undeployed
  release.
- **Planned fix**: no new code. Deploy the already-built, already-tested
  P2-14 work (same release flow as before: squash onto `client/main`, push,
  `deploy.sh`, then `run_migrations.py` for migration `008`).
- **Verify**: `GET /api/admin/plans/changes` returns 200 on production, the
  table renders, a price edit appends a row.

### 5. A single result can be 14,198 pixels tall, SHIPPED (`c413888`)

- **Where**: `frontend/index.html`, `itemHTML()`, the `.redline`/`.full-text`
  rendering of `d.plain`/`d.full`.
- **What's wrong**: no length cap on the rendered preview. The top "Newest"
  result rendered 41,650 characters in one unbroken block, pushing all other
  30 results off-screen.
- **Confirmed root cause**: yes, read directly, `itemHTML()` has no
  truncation logic for the `snapshot` type's inline preview.
- **Planned fix**: cap the visible preview to a sensible length (a few
  hundred characters, matching the server-side 240-char teaser logic already
  used for the gated case) with a "Show full section" expand, which already
  exists as a UI pattern on this page, reused rather than reinvented.
- **Note**: this gets smaller as a problem once #1 is fixed, since the
  oversized payload driving it is the same root data, but the frontend still
  needs its own cap regardless of what the backend sends, a well-behaved
  renderer shouldn't trust the backend to always behave.
- **Verify**: the same "Aktualitätendienst" result, measure
  `getBoundingClientRect()` height before and after, confirm it's bounded and
  expandable.
- **Done (Oct 8)**: `capPlainText()` and `capSegments()` added to
  `frontend/index.html`, both cap at 240 characters, wired into `itemHTML()`
  for both the snapshot and diff types. "Show full section" untouched,
  still shows the complete text. Verified with a synthetic 52,000 character
  document (both types) and against real data (DCAT XML, 1,493 chars): all
  three render around 207 to 208px, down from the unbounded original.
  Full suite: 306 passed. Committed in `c413888` along with the rest of the
  reviewed Live Feed batch (skeleton, tab animation, stale banner fix, and
  removal of every em dash/en dash from the batch per updated global style
  rules). Not deployed yet.

---

## Batch 2: next 10

Ordered High severity first, then Medium.

| # | Problem | Where | Root cause known? | Planned fix |
|---|---|---|---|---|
| 6 | Result previews read as scraped site furniture (nav menus, CKAN "Go to resource" boilerplate), not legal text | `crawler/`, `extractor/`, specific sources (German RSS source, NZ/AU open-data portals) | Partially, same class as `frontend-audit.md` §6j's AU finding, but now confirmed across multiple sources, not just one | Needs its own extractor investigation per affected source, out of frontend scope; this plan schedules it, a separate crawler-focused pass does it |
| 7 | "Subscribe to Professional" (trial-active state) navigates home instead of opening checkout | `frontend/account.html` | Not yet, needs a read of that button's click handler | Point it at the existing paywall/plan-selection modal already used elsewhere on the site, not a new flow |
| 8 | Hardcoded placeholder flash (0 results, generic title) visible ~1-2s on every load/nav, even when already logged in | `frontend/index.html`, initial render before data hydrates | Yes, this is audit finding #2/#4, already scoped: unbounded `/api/search` payload + no skeleton on the authenticated path specifically | The skeleton work already done locally on this branch covers signed-out load; needs the same treatment confirmed for the already-logged-in case, since QA reproduced it there specifically |
| 9 | No `Cache-Control` on any page or API response | `api/main.py`, every `FileResponse` and JSON route | Yes, `frontend-audit.md` §1 | `Cache-Control: no-cache` on HTML (keep the existing ETag for cheap 304s); a short `max-age` or `no-store` on API JSON, scoped per endpoint |
| 10 | No compression (gzip/br) anywhere | `api/main.py`, `deploy/nginx.conf` | Yes, `frontend-audit.md` §1 | `GZipMiddleware` in FastAPI, three lines, no new dependency |
| 11 | Search latency varies 410ms-1538ms for the identical query | `/api/search` | No, observed only, QA report is explicit that no server-side evidence was available to attribute a cause | Needs a server-side look (query plan, connection pooling) before any fix is proposed, not blind tuning |
| 12 | 10 of 21 US county/city sources (48%) are broken; 24/65 total non-operational | `config/sites.json`, crawler | Yes, per-source, already itemized in the admin panel's own health labels | Crawler maintenance work, source by source, not a frontend fix, feeds directly into item #2 above |
| 13 | "Run Crawl Now" triggers a real job but the UI never polls status again, stays frozen on "started just now" | `frontend/admin.html`, crawl-trigger handler | Yes, confirmed no repeat `/api/admin/crawl/status` calls after the first | Add a polling interval (every few seconds) until the job reaches a terminal status, then stop |
| 14 | 375px horizontal overflow on the homepage, filter-pill row not contained | `frontend/index.html`, `.pills` | Yes, the "Full snapshots 30" pill extends past the viewport | Constrain `.pills` to scroll within its own row rather than pushing the page wide, matching the pattern already used for the admin webhook table |
| 15 | No dark mode anywhere | all pages | Yes, confirmed absent, `frontend-standard.md` requires it | Scoped as its own pass once the above are stable, add `prefers-color-scheme` variants for the existing token set, no redesign |

---

## Batch 3: final 10 (polish, confirmed-working, and documented gaps)

| # | Item | Status | Action |
|---|---|---|---|
| 16 | OTP error banner shifts the code field ~26px without refocusing it | Low severity, layout-shift only, not confirmed broken | Reserve the error banner's space in the layout before it's needed, so it doesn't push content |
| 17 | Only 1 webhook log entry exists (a rejected test event) | Not a defect, consistent with 0 real subscribers | No action, note and move on |
| 18 | All auth error paths (empty fields, wrong OTP, wrong password, duplicate email, password reset) show clear, correct errors | **Confirmed working**, pass | No action |
| 19 | Reflected-XSS payload in the search box is properly escaped | **Confirmed working**, pass | No action |
| 20 | A tampered JWT in `localStorage` is cleanly rejected, no broken page | **Confirmed working**, pass | No action |
| 21 | Blocking `/api/search` shows a clear error state, rest of the page stays functional | **Confirmed working**, pass | No action |
| 22 | Pricing and jurisdiction counts match live API data everywhere displayed | **Confirmed working**, pass | No action |
| 23 | Paid-subscription account states (active, paused, cancelled) not testable without a real PayPal charge | Documented gap, not a bug | Test these against the local seeded-SQLite method already used earlier in this session, once item #7's checkout dead-end is fixed |
| 24 | True cross-browser testing (Firefox, Safari, mobile) not performed, Chromium only | Documented gap | Re-run the search and one account-state flow in at least Firefox and Safari before calling the frontend pass done |
| 25 | Full Lighthouse/axe accessibility audit not run, only a lightweight manual check | Documented gap, partial | Run a real automated audit (Lighthouse, in a real browser) once the above visual/structural fixes land, so it's auditing the fixed version, not the current one |

---

## Needs a decision before we touch it

**Item 2** (the About page claim vs. live content mix) is the one item in
this plan that isn't purely a code fix. Fixing the 10 broken US sources is
real crawler work with its own timeline; softening the About page's wording
is fast but changes what we tell visitors. Your call on which comes first,
or whether we do both: fix sources now, and only soften copy if the fix
takes longer than expected.

---

## Working order once you say go

1. Item 1 (paywall leak): highest severity, smallest, safest fix, do it alone first.
2. Item 5 (14,198px result) and item 8 (placeholder flash) together, since both live in the same render path.
3. Item 4 (deploy P2-14): no new code, just ship what's built.
4. Item 9 + 10 (cache headers + compression) together, same release.
5. Item 3 (admin silent errors): once reproduced.
6. Items 7, 13, 14: independent, small, any order.
7. Item 15 (dark mode) on its own.
8. Items 2 and 12 (content mix / broken sources): once you've decided the approach.
9. Item 11 (latency variance): only after a real server-side look, not guessed at.
10. Items 24, 25 (cross-browser, full a11y audit): last, so they test the fixed site, not the current one.

Each item gets implemented, tested, and shown to you before moving to the next.
