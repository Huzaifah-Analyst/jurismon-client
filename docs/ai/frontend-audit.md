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

## 6. Account page loading sequence — PARTIALLY VERIFIED

Code-confirmed: `init()` in `frontend/account.html:770-800` makes `GET /api/auth/me` then `GET /api/account/subscription` in sequence (not parallel), each gated behind the previous one resolving. `state-loading` (`frontend/account.html:409`, a centered `.spinner`) is shown for the full duration of both calls.

**Not yet reproduced**: the client's screenshot shows a spinner appearing to float over already-rendered account content. Only one spinner element exists in the markup (`frontend/account.html:410`), inside `#state-loading`, which the code hides before showing `#state-active` — a straightforward read of `hideAllStates()` (`:739-748`) does not explain an overlap. Reproducing this needs a real authenticated session (OTP email, real trial user); I have not done that against production and will not fabricate a root cause I have not seen happen. Flagging as open, not closed.

**Standard rule violated**: unresolved pending reproduction.

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
| 4. Data fetching | Fail — unbounded payload, sequential calls on the account page, no abort/timeout seen |
| 5. Backend contract | Fail — gated response still ships ungated data |
| 6. Assets | Fail — raster logo, no hash-based cache busting |
| 7. Structure | Pass — DOM order is correct, no unexplained null guards found in this pass |
| 8. Responsive | Not audited this pass (deferred to the fix-plan verification step) |
| 9. Accessibility | Not audited this pass |
| 10. Testing | Fail — zero frontend tests exist |
