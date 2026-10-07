# Frontend Audit

> **Purpose**: JurisMon's live frontend, measured against `frontend-standard.md`.
> **Method**: live production checks on `https://jurismon.com` (headers, timing, payload bytes) plus a code read of `frontend/`, `api/main.py`, `deploy/nginx.conf`. Every finding below is from a real request or a real line of code, not a guess.
> **Date**: Oct 7, 2026, against production commit `6376244`.
> **Next**: `ORDER-P2-16.md` is the fix plan built from this audit.

---

## 1. Why pages look stale after a refresh — CONFIRMED

```
curl -s -D - -o /dev/null https://jurismon.com/
HTTP/1.1 200 OK
last-modified: Tue, 06 Oct 2026 17:57:44 GMT
etag: "bc9fc5a860939c33c90387b3204c8ebb"
(no Cache-Control header at all)
```

Every page (`/`, `/about`, `/account`, `/admin`, `/terms`, `/privacy`) is served through `api/main.py` with plain `FileResponse(...)` — `api/main.py:272-320`. Starlette's `FileResponse` sets `Last-Modified` and `ETag` automatically but sets **no `Cache-Control`**.

Per RFC 7234, a response with `Last-Modified` and no `Cache-Control` gets **heuristic freshness caching**: the browser picks its own cache lifetime, commonly ~10% of the file's age. The longer it has been since the last deploy, the longer a browser will silently reuse the old copy with no request at all.

This is exactly the client's report, confirmed by outside research on the same pattern:

> "Starlette's StaticFiles sends ETag/Last-Modified but no Cache-Control, so browsers heuristically cache HTML and keep loading the previous build after a deploy." — [i2mint/enlace PR #47](https://github.com/i2mint/enlace/pull/47)

**Standard rule violated**: 3.1, 3.3.

---

## 2. Why results load a few seconds after the page — CONFIRMED, with numbers

Real browser timing on the homepage (`performance.getEntriesByType`, not a guess):

| Request | TTFB | Duration | Bytes |
| :--- | --: | --: | --: |
| `/` (the page itself) | 586ms | — | 75 KB |
| `/static/assets/logo.png` | 284ms | 305ms | 15 KB |
| `/api/sources` | 1,109ms | 1,113ms | 350 bytes |
| `/api/plans` | 303ms | 407ms | 520 bytes |
| `/api/search?q=` | 1,332ms | **3,505ms** | **325 KB** |

The homepage fires `fetch('/api/search?q=')` with an empty query on every load — `frontend/index.html:1318`. For a signed-out visitor this request takes **3.5 seconds** and ships **325 KB**, and only then does the result list fill in. Until it resolves, `<ul id="results"></ul>` — `frontend/index.html:1058` — sits empty. No skeleton, no placeholder: `grep -c skeleton frontend/index.html` is 0.

### 2a. The backend ships the full dataset even when the visitor is locked out of it

```
GET /api/search?q=  (unauthenticated)
is_gated: true
items returned: 2          <- the teaser the visitor actually sees
results.snapshots: 30      <- but still fully returned
results.diffs: 30          <- but still fully returned
full payload: 357,585 bytes
results-only portion: 306,321 bytes  (86% of the payload)
```

`api/main.py:469-503`: `results = repo.search_snapshots_and_diffs(query=q)` runs unconditionally, and the full `results` dict is returned in the JSON body even when `items` is correctly truncated to a 2-item teaser. One snapshot alone carries `cleaned_text` of **42,257 characters** — the complete legal document text — for a record the gated visitor is never shown.

86% of the bytes sent to an anonymous visitor are for content that visitor cannot see.

**Standard rule violated**: 4.5, 5.5. Confirmed against outside practice: common API page sizes are 20-50 records with a hard server cap ([getknit.dev](https://getknit.dev/blog/how-to-determine-the-appropriate-page-size-for-a-paginated-api/)); this endpoint has no `limit` parameter at all.

### 2b. No compression anywhere, at either layer

```
curl -H "Accept-Encoding: gzip, br" .../api/search?q=
(no content-encoding header in the response)

grep gzip deploy/nginx.conf   -> no output
grep GZipMiddleware api/main.py -> no output
```

Neither nginx nor FastAPI compresses a single response. JSON and HTML both compress 70-90% with gzip ([asoasis.tech](https://asoasis.tech/articles/2026-03-29-0252-api-response-compression-gzip-brotli/)); this alone would very likely take the 325 KB search payload under 80 KB without touching a single line of application logic.

**Standard rule violated**: 1.1 (indirectly — slow data delays perceived readiness).

---

## 3. No loading state exists on the homepage — CONFIRMED

`grep -n "skeleton\|loading" frontend/index.html` returns nothing. The result list is a bare `<ul>` that is empty until `fetchLiveSearch()` resolves. For 1-3.5 seconds depending on network, the page looks finished (header, search box, filters all present) while the one thing the visitor came for is blank.

**Standard rule violated**: 2.1, 2.2, 2.5.

---

## 4. Zero frontend tests exist — CONFIRMED

```
grep -l TestClient tests/*.py -> 4 files, all backend API/DB tests
find . -iname "*.spec.js" -o -iname "*playwright*test*" -> nothing
```

303 backend tests exist and are good. Not one test renders a page, checks a loading state, or drives a browser flow. Every bug the client found by hand (stale refresh, slow results, logo, the account-page spinner) is a bug that no test would have caught, because no test looks at the front end at all.

**Standard rule violated**: all of section 10.

---

## 5. Logo is a small raster PNG, not SVG — CONFIRMED

```
frontend/assets/logo.png: 278 x 72, PNG, 14.8 KB
```

Displayed at `height:30px` (`frontend/index.html:961`), so it is being scaled down on normal screens — fine at 1x, soft on a 3x phone screen, since 30px CSS height needs ~90px of source at 3x and the source is only 72px tall total. No dark-mode variant. No `width`/`height` attributes on the `<img>` tag (inline `style` substitutes for height only).

**Standard rule violated**: 6.1, 6.2.

### 5a. `/static/` assets are not cache-busted

`deploy/nginx.conf:81-84`: `location /static/ { expires 7d; }`. The logo keeps the same filename (`logo.png`) across deploys, so a future logo change will not reach a visitor who loaded the site in the last 7 days — the opposite problem from the HTML, but the same root cause: no content-hash in the filename, no way for the browser to tell old from new except waiting out a fixed timer.

**Standard rule violated**: 3.2.

---

## 6. Live walkthrough — signup, login, about, account (Oct 7, 2026)

Tested by hand against production (`https://jurismon.com`) and, for the four authenticated account states, against a local server forced onto an isolated SQLite database (`SUPABASE_URL` unset for that process) seeded with throwaway test users — **production data was never touched**. The account page HTML served locally was first diffed byte-for-byte against the live page and confirmed identical, so this is a true test of what is live.

**Note on the client's screenshot**: the floating spinner in the screenshot the client sent was Fiverr's own image still loading, not a JurisMon bug — confirmed by the client. Removed from this audit; it was never a real finding.

### 6a. Signup and email verification — PASS

Registered a real throwaway account end to end: form submit → `POST /api/auth/register` (200) → code-entry screen appears in under 2 seconds with the submitted email echoed back correctly. Submitted a deliberately wrong 6-digit code and got a clear red inline error, "Invalid confirmation code. Please check your email and try again." Resend link present. No issues.

### 6b. Login with wrong credentials — FAIL, new finding

```
POST /api/auth/login -> 401 Unauthorized
Result: the modal silently closed. No error message shown anywhere.
```

Signup shows a clear red banner on a wrong code. Login shows **nothing** on a wrong password — the modal just closes and the visitor is back on the homepage with no idea what happened to their attempt. Same form, same app, two different behaviours. This is the kind of thing that reads as "broken" even though the backend did the right thing (401 is correct) — the frontend threw the error away.

**Standard rule violated**: 4.2 (every fetch must handle non-2xx explicitly — this one does not).

### 6c. A third spot still says "65" without "live/tracked" — FAIL, new finding

The Oct 5 decision was "41 live jurisdictions, 65 tracked" everywhere customer-facing. Two spots were fixed. A third was missed:

```
frontend/index.html:1367
"Free Preview Mode: ... Start your 14-day free trial for full text
across all 65 jurisdictions."
```

This is the exact banner shown to every anonymous visitor who searches without an account — the highest-traffic unauthenticated surface on the site — still making the unqualified "65" claim the client asked removed.

**Standard rule violated**: 4.7 (no claim should exist in two forms after a correction) and reopens the business risk from the Oct 5 decision.

### 6d. About page — PASS

All content accurate, ingestion stat correctly shows "41 live jurisdictions, 65 tracked" (the one place this was fully fixed), zero console errors, zero failed requests.

### 6e. Account page, signed out — PASS

Clean signed-out state, correct call to action, no errors.

### 6f. Account page, all four authenticated states — mostly PASS, one new finding

Walked through Trial, Active, Paused, and Cancelled-in-period with real seeded users and real JWTs:

| State | Visual | Behaviour |
| :--- | :--- | :--- |
| Trial, no subscription | Correct, matches client's own screenshot | Pass |
| Active | Correct | Pass, but see below |
| Paused | Correct, access date and paused-since date both right | Pass |
| Cancelled, in paid period | Correct, red notice is clear | Pass |

**New finding**: the Active state shows a raw internal identifier to the customer with no explanation —

```
SUBSCRIPTION ID
I-ACTIVE-1
```

A zoning lawyer with no reason to know what a PayPal subscription id looks like sees a cryptic code sitting on their account page. It is their own id, not a security leak, but it is implementation detail that belongs in a support ticket, not the customer's screen.

**Standard rule violated**: 5.4 (an internal id should not appear in the customer-facing DOM without a reason to).

### 6g. Account page at 375px — minor finding

No horizontal overflow (`scrollWidth === clientWidth === 375`, confirmed). But the header stacks into three separate full-width rows — "Back to Search" button, then the account email as its own line, then "Sign Out" — instead of a compact single bar. Not broken, just wasteful of a small screen's vertical space.

**Standard rule violated**: 8.1 is technically met (no scroll), but this misses the spirit of 8.3/8.4.

### 6h. Admin page, signed out — PASS

Clean, no console errors.

---

## 7. What the research surfaced for fixing these, without adding dependencies

| Problem | Fix, matching this project's zero-dependency style |
| :--- | :--- |
| No compression | `app.add_middleware(GZipMiddleware)` — built into Starlette/FastAPI already, or `gzip on;` in nginx. No new package. ([oneuptime.com](https://oneuptime.com/blog/post/2026-01-25-network-compression/view)) |
| Stale HTML on refresh | `Cache-Control: no-cache` on every `FileResponse`, keeping the existing ETag so a refresh is a cheap 304, not a full re-download. ([mojoauth.com](https://mojoauth.com/implement-caching/implement-caching-with-fastapi)) |
| No loading state | Pure CSS skeleton (shimmer via `background-position` keyframes), no JS library — this is how 20 of 22 surveyed skeleton implementations work. `role="status"` + `aria-live="polite"` for screen readers. ([css-tricks.com](https://css-tricks.com/building-skeleton-screens-css-custom-properties/)) |
| Unbounded search payload | Add `limit`/`offset` to `/api/search`, default 20-50, hard-capped — standard REST pagination, no library needed since the repository method already takes a query string. ([getknit.dev](https://getknit.dev/blog/api-pagination-best-practices/)) |
| Logo softness | Re-export the existing logo as SVG (it is almost certainly vector-drawn already, given it is a wordmark) — zero new dependency, just a different export. |

No framework, no build step and no new runtime dependency is needed for any of these. All five are fixable inside the current vanilla-HTML, vanilla-JS, FastAPI-serves-files-directly architecture.

---

## 8. Summary scorecard against `frontend-standard.md`

| Section | Verdict |
| :--- | :--- |
| 1. First paint | Partial — shell is static and fast (586ms TTFB), but the page looks "ready" before it is |
| 2. Loading states | Fail — no skeleton anywhere, confirmed by grep |
| 3. Stale content | Fail — no `Cache-Control` on any HTML response, confirmed by header dump |
| 4. Data fetching | Fail — unbounded payload, sequential calls on the account page, no abort/timeout, a failed login shows no error |
| 5. Backend contract | Fail — gated response still ships ungated data, a raw subscription id reaches the customer |
| 6. Assets | Fail — raster logo, no hash-based cache busting |
| 7. Structure | Pass — DOM order is correct, no unexplained null guards found in this pass |
| 8. Responsive | Partial — no overflow at 375px anywhere tested, but the account header wastes space stacking into three rows |
| 9. Accessibility | Not audited this pass |
| 10. Testing | Fail — zero frontend tests exist |

---

## 9. Every problem found, in one table

| # | Problem | Where | Severity | How it will be fixed |
| :-- | :--- | :--- | :--- | :--- |
| 1 | No `Cache-Control` on any HTML page, so refresh can show yesterday's deploy | `api/main.py:272-320`, every `FileResponse` | High — this is the client's own complaint | Add `Cache-Control: no-cache` to every HTML response; keep the existing ETag so a refresh is a cheap 304, not a full reload |
| 2 | `/api/search` ships the full matched dataset even to a gated/teaser visitor — 86% of the payload (306 KB of 357 KB) is content the visitor is not shown | `api/main.py:469-503` | High — this is the client's "results load slowly" complaint, with a cause | Truncate `results.snapshots`/`results.diffs` to match the teaser `items` when `has_access` is false; add `limit`/`offset` for authenticated requests too |
| 3 | No compression anywhere — nginx or FastAPI | `deploy/nginx.conf`, `api/main.py` | High — multiplies every other payload problem | Add `GZipMiddleware` in FastAPI (three lines, no new dependency) |
| 4 | No loading state anywhere on the homepage; `<ul id="results">` is just empty for 1-3.5 seconds | `frontend/index.html:1058` | High — makes a working page look broken | Pure CSS skeleton rows shaped like a result card, shown the instant the fetch starts, `aria-live="polite"` region |
| 5 | A failed login (401) shows no error at all — the modal just closes | `frontend/index.html`, login submit handler | High — looks exactly like "the site is broken" | Add the same inline error banner the signup form already has, reused for both forms |
| 6 | "Free Preview Mode" banner still says "across all 65 jurisdictions" — the exact claim corrected everywhere else on Oct 5 | `frontend/index.html:1367` | High — reopens a decision the client already made, on the highest-traffic banner on the site | Rewrite to "41 live jurisdictions, 65 tracked," matching the header and About page |
| 7 | Raw PayPal subscription id shown on the customer's account page with no explanation | `frontend/account.html`, Active/Paused state markup | Medium — not a leak of someone else's data, but unexplained technical detail on a lawyer-facing page | Remove from the default view, or label and tuck it under a "details" disclosure |
| 8 | Logo is a 278×72 raster PNG, not SVG; no dark-mode variant; not cache-busted (`expires 7d` on a fixed filename) | `frontend/assets/logo.png`, `deploy/nginx.conf:81-84` | Medium | Re-export as SVG; add a dark-mode variant; adopt content-hashed filenames for `/static/` |
| 9 | Account page header stacks into three full-width rows at 375px instead of one compact bar | `frontend/account.html` header markup | Low — not broken, just wasteful | Lay out email + buttons on one row within the existing breakpoint |
| 10 | Zero frontend tests of any kind | whole `frontend/` directory | High — every bug above would have been caught by a 10-minute test, not a client screenshot | Add the four test layers from `frontend-standard.md` §10, starting with the states and flows this audit just walked by hand |

---
