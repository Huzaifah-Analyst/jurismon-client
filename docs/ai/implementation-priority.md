# Implementation priorities, 10 October 2026

User-approved order. Numbers below are priorities, not frontend fix-plan IDs.

| Priority | Work | Status |
| --- | --- | --- |
| 1 | Verify repository, deployment parity and existing order scope | Verified code and deployment; historical payment records differ from current user statement |
| 2 | Remaining frontend bugs and dark mode | Report fixes verified and released 11 October; separate OTP delivery-failure follow-up remains |
| 3 | Backend cache headers, compression and search latency investigation | Cache/compression verified and live c837276; search concurrency fix locally verified |
| 4 | Regression, paid subscription states, cross-browser and accessibility QA | Core checks completed; physical devices, all modal/admin-tab audits and Lighthouse remain uncovered |
| 5 | Evidence-based case studies using available captured changes | Pending |
| 6 | Housekeeping: About punctuation and existing chat-log changes | Pending |
| 7 | Repair broken US city and county sources | 8 of 10 broken US sources repaired locally; NYC and Santa Clara blocked; production ingestion pending |
| 8 | Remove navigation and portal boilerplate from extracted legal text | Pending |
| 9 | Honest coverage and exclusions section | Pending |
| 10 | Page-by-page competitor gap list, prepared for Google Sheets | Pending |
| 11 | Define scope, deliverables, timeline and budget for new competitor-driven implementation | Pending |

## Commercial context

- The user reports a current $200 order placed and payment received for existing setup work.
- The older handoff separately records Phase 1 at $200 and Parts 1+2 at $100. Repository documents cannot verify the current Fiverr transaction; do not overwrite the user's current statement with the older record.
- The $100 email alerts/watchlists and $150 source expansion orders have not been placed, per the user. Do not implement these unordered features.
- Competitor analysis does not authorize new competitor-driven features. Define their implementation scope and budget separately.
- Test changes locally and in a real browser. Ask the user before production deployment.

## Repository verification

- Branch: `claude/sweet-babbage-fz7sbz`; development HEAD: `e54ac5c`.
- After successful `git fetch client`, `git diff --stat client/main HEAD` was empty before this session's changes.
- Client release: `49f01e713c7f7da17a4bebbd810efa020393de5a`.
- Production `/api/health` returned `status: ok`, `version: 49f01e7`, `database: ok`.
- Baseline test output: `306 passed, 2 warnings in 48.17s`. Warnings: Starlette TestClient deprecation and pytest cache permission failure.
- Pre-existing local changes preserved: modified `docs/archive/chat-log.md`, untracked `.claude/settings.local.json`, and untracked `docs/context/2026-10-10/`.
- Migration files already include `008`; the next number is `009`. Older architecture/rules references to next migration `008` are stale.

## Frontend fix-plan item 13

- Confirmed cause: `checkCrawlStatus()` ran once on load/trigger with no recurring status fetch.
- Added a three-second timeout after a running status. Requests do not overlap.
- Terminal statuses stop polling and enable the crawl button. Temporary status failures retry; 401/403 return to sign-in.
- Logout and page exit cancel scheduled polling and in-flight requests. Stale session responses cannot overwrite the signed-out UI.
- Regression tests use a real local Uvicorn API, genuine admin login, and isolated SQLite crawl rows. No production crawl, payments or emails are triggered.
- Targeted browser checks: `4 passed in 37.37s`.
- Final full regression command: `./venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`; output: `310 passed, 1 warning in 94.28s`. The remaining warning is the pre-existing Starlette TestClient deprecation.
- Status: implemented locally, not deployed.

## Remaining frontend batch

- Item 3: both real admin plan 409 responses (price mismatch and last active plan) display readable toasts. Reproduced successfully in light and dark modes with opacity confirmed at 1 and screenshots captured. No handler change was warranted. The current catalogue-settings PATCH route does not contain a 409 branch.
- Item 8: the authenticated boot previously called `render()` before `/api/auth/me` returned, showing an empty result state. It now immediately shows the search skeleton. Source coverage displays a loading/error message until real counts arrive, with no fallback 41/65 claims.
- Item 14: reproduced a 464px page at a 375px viewport for a signed-in customer. The pill row was already contained; the signed-in header email caused the overflow. Compact headers now keep account controls visible and put the email on the account page at mobile widths. Pills retain their own horizontal scroll; the preview banner stacks on mobile.
- Item 16: a genuine wrong OTP moved the code field 27.0625px. Verification now reserves feedback space and restores focus to the code field after rejection. Browser checks cover 375px and desktop.
- Item 15: all six pages use shared semantic color tokens and OS/browser `prefers-color-scheme`. The stylesheet has a content hash in its filename so an old cached asset cannot hide the change. Existing light colors and page layouts are retained.
- Shared theme: `frontend/theme.83c2aa669eb3.css`.
- Targeted verification: `16 passed in 82.16s`. Includes previous crawl polling tests, signed-out/signed-in mobile checks, delayed session loading, real source API failure, OTP layout/focus, both 409 states, and six-page light/dark checks at 375px and 1280px.
- Final full regression output: `322 passed, 1 warning in 170.38s`. Command: `./venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`. The warning is the existing Starlette TestClient deprecation.
- CI now installs Playwright Chromium before pytest so browser regressions run there too. The existing deployment gate is unchanged. Workflow YAML parsed successfully; hosted CI has not been run during this session.
- Inline JavaScript syntax checks passed on all frontend pages. No page JavaScript errors occurred in the six-page theme pass.
- Screenshots are local QA artifacts under ignored `test-results/frontend/`. They reflect real API responses from isolated SQLite test data, not production coverage or customer accounts.
- Cross-browser and automated accessibility audits remain scheduled for priority 4. These browser checks used Chromium.
- All changes remain local. No commit, push or deployment has been performed.

## User review follow-up: corrected plan

The earlier browser checks passed their covered cases, but did not establish
complete end-to-end frontend behavior. The frontend completion claim is withdrawn.
User review added the cases below. Preserve the user's local `trial_days: 45`
change in `config/plans.json`; do not revert it as test cleanup.

| Order | Finding and evidence | Work | Acceptance check |
| --- | --- | --- | --- |
| 1 | Local `/api/plans` returns 45, but signup verification and unverified password reset still pass `trial_days=14`. Public trial copy also hardcodes 14. | Read configured trial duration when granting new trials; use API-backed trial copy across home, account and transactional email. Handle zero-day configuration explicitly. | Set 45 and 67 in an isolated catalogue: newly verified accounts get matching stored start/end dates and public copy matches. Existing account trial dates remain intact. Verify zero-day behavior too. |
| 2 | The OTP review account is still unverified; the original supplied review code no longer matches its stored code. Its replacement code expiry has also elapsed. The local mailer is disabled. | Audit signup, resend and reset delivery failures. Do not claim an email was sent when delivery failed. Keep failed resend from invalidating a usable previous code. Provide a local-only review mailbox/test harness outside the production UI. | Genuine invalid, expired, delivered, resent and failed-delivery responses behave correctly; fresh local review code verifies; field position/focus remain stable. |
| 3 | Homepage review uses an empty local database. Fast localhost responses can replace the skeleton before a visible paint. Earlier delayed-session test did not cover all search/auth transitions. | Verify initial load, search, login and logout with real pending requests under browser throttling. Fix any uncovered state or stale-response issues. Avoid adding arbitrary network delays merely to make an animation visible. | Pending requests show skeletons; successful empty responses show the empty state; old responses cannot overwrite a newer search or auth state. Test with and without real captured records. |
| 4 | Successful homepage login/logout do not currently render a success notification. Result entrance animations have no result rows to animate on this empty database. | Add accessible, restrained success feedback for login, verification and logout; use the existing motion style where content/state transitions warrant it. Respect reduced-motion preferences. | Notifications appear after actual success, errors stay visible, keyboard focus is sensible, and reduced motion disables nonessential animation. |
| 5 | Theme screenshots covered six pages but mostly signed-out views. Authenticated badge colors still contain inline light-theme values in JS. | Check and repair light/dark behavior for signed-in, trial, paid, paused, cancelled, OTP and admin error states using real isolated DB records. | Relevant text, badges, fields and buttons remain readable at mobile/desktop widths in both modes. |
| 6 | Earlier pass ran Chromium only and did not include an automated accessibility audit. | Run regression tests, Firefox/WebKit flows and axe/Lighthouse after fixes. Test catalogue changes on a temporary config, not the user's working file. | Publish actual results and remaining limitations. Do not label uncovered cases as passed. |
| 7 | Backend performance work remains pending. | Continue cache headers, compression and measured search latency investigation once the frontend follow-up is verified. | Check response headers, compressed sizes and server-side timing evidence without claiming an unmeasured speed improvement. |

After this follow-up, retain the previously approved order: case studies,
housekeeping, broken US sources, extraction, honest coverage, competitor gap
sheet, then scope/budget for new competitor-driven features. Email alerts and
88-source expansion remain unordered. No deployment without user approval.


## Frontend problem 1: configured trial offer

- Home navigation, registration tab/description/submit, email confirmation button,
  preview banner and locked-result CTA now use the real `/api/plans` trial duration.
- Account signed-out trial link also reads the catalogue. Existing account badges
  continue using actual remaining days; removed the invented 14-day fallback.
- Zero-day catalogue offers account creation without promising a free trial.
  Failed catalogue requests retain generic account-creation labels.
- Preserved the user's `config/plans.json` setting of 45 days. Tests patch isolated
  catalogue reads for 45, 67 and 0; they do not write the working configuration.
- Validation: `./venv/Scripts/python.exe -m pytest tests/test_frontend_fixes.py -q
  -p no:cacheprovider`: 16 passed in 94.64s. Both edited pages pass Node JavaScript
  syntax checks; scoped `git diff --check` passed.
- Backend trial grants still hardcode 14 days and require a separate fix. This
  frontend change does not establish correct trial expiry on newly verified users.
- Manual review: refresh localhost; check 45-day navigation, registration and
  confirmation labels; check the signed-out account link. An existing account's
  14-day remaining badge reflects its stored trial and should not become 45.
- User verification: awaiting confirmation. Commit: pending user confirmation.
  No push or deployment. Earlier unrelated local changes remain uncommitted.

- User follow-up: trial offer was visible. At the user's request, restored catalogue trial_days from 45 to 14; running local `/api/plans` verified 14. Admin changes update the edited frontend offer labels after page refresh. Backend trial grants and transactional email copy still need configuration parity; existing trial dates remain unchanged. No commit yet.


## Next fix: one configured trial duration

- Current working catalogue remains 14 days; running local `/api/plans` verified 14.
- All customer-facing API trial grants now read the current admin catalogue:
  signup verification and first verification through password reset. Registration
  uses the same setting; signup and resend HTML/plain-text email copy are aligned.
- Gated search text and the Terms trial offer no longer hardcode 14 days. Home and
  account offer labels already use the same public catalogue API.
- A zero-day setting grants no trial access and makes no free-trial promise.
- Configuration changes affect offers and trials activated after the change.
  Already verified users retain their stored expiry; repeated verification and
  password resets do not restart or extend their trial.
- Validation: combined authentication, schema contract, Supabase path and browser
  regression run: 63 passed, 1 existing Starlette deprecation warning in 78.57s.
  Final trial configuration tests including genuine admin login/PATCH and audit
  recording: 10 passed, 1 existing warning in 8.65s. Catalogue persistence for this
  admin test is redirected to a temporary file; working plans.json is untouched.
- Covered configured durations: 14, 34, 45, 67 and zero (appropriate API/browser
  cases), activation-time setting changes, email content and preserved old expiry.
- Home/account/terms JavaScript syntax passed; scoped diff whitespace check passed.
- Local preview server restarted with updated backend; no external email/payment
  providers enabled. Current preview URL: http://127.0.0.1:8000.
- Manual verification: admin Plans setting 34, save; refresh signed-out home,
  account and Terms to see 34; restore 14 and refresh to see 14. Existing account
  remaining days reflect its own expiry. Local email delivery is disabled, so
  email/trial activation checks above use isolated state and a captured mailer.
- Status: awaiting user review before commit. No push or production deployment.


## 11 October 2026: verified release preparation

User authorized completing pending verification, fixing QA report full-table
item #2, pushing GitHub changes and making the result live.

- Item #2: About copy and metadata now describe selected US local portals plus
  international national registries. Removed claims of complete municipal
  coverage, guaranteed historical reconstruction, perfect boilerplate removal
  and section-level alerts. Counts come only from the current sources API;
  unavailable counts display an error. Broken sources and extraction repairs
  remain separate work, not completed by this copy correction.
- Loading verification found stale search responses could replace newer search
  or authentication results. Added request version checks and verified with
  genuine API responses delivered out of order. Authenticated boot hides the
  signed-out controls until session verification completes.
- Login/verification/logout success feedback is accessible and uses semantic
  colors. Authenticated badges now use the shared light/dark palette.
- Genuine local subscription records verified active, paused, cancelled within
  period and cancelled expired account views at 375px in light/dark mode. No
  live PayPal lifecycle calls. Admin 409 messages remain covered by real local
  error responses.
- Chromium, Firefox and WebKit mobile authenticated search/logout/account
  smoke checks: 3 passed in 20.65s. Desktop OS browsers and physical iOS/Android
  devices were not tested; WebKit is engine coverage, not a physical Safari run.
- Full regression excluding those three separately run engine cases:
  352 passed, 3 deselected, 1 existing Starlette deprecation warning in 200.70s.
- New out-of-order response regression: 1 passed in 7.67s (added after that full
  run collected its tests). All inline JavaScript syntax checks passed.
- axe-core 4.10.3 WCAG 2 A/AA and 2.1 AA checks on six pages, both light/dark:
  initial admin count contrast finding corrected; final 12 views reported no
  violations. Views include signed-in home/account and authenticated admin
  overview. Modal states and every admin tab were not exhaustively audited;
  this is automated axe coverage, not a Lighthouse audit or certification.
- CI installs all three Playwright engines. Old tests that assumed the local
  working catalogue must always be 14 were corrected or explicitly isolated.
- Local catalogue is now 10 days, reflecting the user's later admin change.
  Preserve that working file and exclude it from the release; production
  catalogue duration is checked independently. No source configuration edits.
- Release commits exclude pre-existing chat-log, local settings and context
  changes. Use a single-parent client release commit without development history.
- Commit, push and live verification references will be recorded after release.


### Release outcome and live follow-up

- Development commit dba9eea pushed to origin; single-parent client release
  5eb6eca pushed to client/main and deployed through the existing deploy script.
- Public health verified status ok, database ok and version 5eb6eca. Service and
  crawl timer active. Authenticated production price-history endpoint returns
  200; production trial_days remains 14.
- Live mobile smoke found a 2px overflow on signed-out admin header; isolated
  signed-in tests exposed long source-status text overflowing too. Header now
  wraps and status text stays within its available width. Four light/dark,
  signed-in/out 375px browser checks passed in 6.07s.
- Follow-up patch will be released before marking live mobile checks complete.

- Admin follow-up: dev b9460e4; client release 02352a6 pushed and deployed.
  Live admin mobile overflow resolved.
- Continuing the live pass after web fonts loaded found Privacy processor-table
  overflow at 375px. Fixed mobile column sizing and wrapping. Four 320/375px,
  light/dark checks passed in 8.92s. This is a further narrow release correction.


### Final verified release, 11 October 2026

- Privacy correction dev commit: 4364149. Final client release: f9dbc15.
- Both GitHub remotes received the reviewed code. Final client release deployed
  successfully; systemd API and crawl timer active. Production catalogue stays
  14 days; the user's local 10-day catalogue file remains excluded/preserved.
- Final public browser review passed all six pages in light and dark at 375px
  after fonts were ready: 12 views, no horizontal page overflow and no page
  JavaScript errors. Live trial CTA verified 14; About scope and API counts
  verified. Artifact: ignored test-results/frontend/live-release-review.json.
- Production health was verified against the final release by this browser run:
  version f9dbc15, database ok. Price-history endpoint was also authenticated
  and verified 200 after the primary code deployment.
- Verification complete for the recorded coverage. Source repairs/extraction,
  backend performance, exhaustive modal/admin-tab accessibility, Lighthouse
  and physical mobile devices remain separate work. No claim that all possible
  frontend states or the content-quality defects are fixed.
- Final release notes are committed/pushed to the development remote separately
  so the runtime release references can be recorded after deployment.


## How the previous release was implemented

| Work | Implementation | Verification |
| --- | --- | --- |
| Trial-setting sync | Customer activation and email copy read config/plans.json through the catalogue helper. Frontend home/account/Terms read /api/plans. Existing account expiry is preserved. | Isolated 14/34/45/67/zero-day cases, genuine admin PATCH, stored expiry and email assertions. |
| Loading/auth feedback | Initial skeleton precedes session hydration; request versions reject stale responses; successful auth changes render a status message. | Delayed and out-of-order genuine API responses; login/logout browser checks. |
| Crawl polling | Repeat every three seconds while running; stop at terminal state or logout and abort stale requests. | Genuine local crawl rows and authenticated admin requests. |
| Theme/mobile fixes | Shared content-hashed semantic color stylesheet; mobile header/pill containment; admin status wrapping and Privacy table wrapping. | Light/dark viewport checks, engine smoke tests, final live six-page checks after fonts loaded. |
| OTP stability | Reserved error space and restored input focus after a rejected code. | Real wrong-code 400 at mobile and desktop widths. |
| QA #2 honest scope | Replaced complete-municipal and perfect-extraction claims with actual local/international scope and limitations; source counts read the API. | Browser checks, genuine source records and unavailable-count behavior. |
| Release | Selected reviewed files, excluded user's config/chat changes, made single-parent client release commits, pushed both remotes and ran the existing VPS deploy script. | Final live version f9dbc15, database ok, API/timer active, 12 mobile light/dark views passed. |

## Current work: QA full-table #3, #9 and #10

### #3: extraction and source labels

Evidence: read-only production samples confirmed nested sources.name, German
RSS catalogue text, Canada CKAN wrappers and an empty NZ snapshot. Captured the
public pages and the actual Australian legal-text iframe for regression cases.
Sanitized committed fixture subtrees omit scripts, forms, session metadata and
nonces; original captures remain ignored local artifacts.

Changes:
- API formatting reads the actual nested Supabase source name, or SQLite's flat
  source_name. Missing names say Source unavailable, not an invented authority.
- The extractor rejects the known German RSS update catalogue and CKAN resource
  wrappers; feed/RDF catalogue XML is rejected as metadata, not legal text.
- XML legislation uses a non-networking XML parser with entity expansion off,
  selecting the statutory body. XHTML still follows HTML noise stripping.
- Legal article headers are retained; navigation, tabs and breadcrumbs removed.
  Source content_selector is honored by the crawler without editing sites.json.
- The Australian official registry's same-host embedded legal HTML is fetched
  before extraction, so wrapper navigation is not stored as statute text.
- Empty extracted responses are skipped before document/snapshot writes.

Limits: existing stored snapshots/diffs are unchanged. Re-extraction/backfill
of historical dirty rows is not complete. The configured NZ XML URL returned a
zero-byte body; rejecting that body does not repair the upstream URL. No live
crawl, source-config edits or historical data writes were performed.

### #9: response cache policy

- All HTML responses: no-cache, preserving FileResponse ETag/Last-Modified.
- Anonymous public sources counts: public, max-age=60.
- Public plan catalogue: no-cache, so admin changes revalidate.
- Search, auth, admin, errors, mutations and requests with Authorization:
  no-store. API Vary includes Authorization to separate public/private results.
- Existing Nginx static-asset policy remains unchanged. This is response policy,
  not a server-side query cache or a measured latency improvement.

### #10: negotiated response compression

- FastAPI GZipMiddleware, minimum body size 1000 bytes, compression level 5.
- Clients must accept gzip; identity clients and small bodies stay uncompressed.
- Vary: Accept-Encoding retained; decompressed JSON matches the identity body.
- Real isolated admin sources payload measured 32,095 identity bytes vs 4,322
  gzip wire bytes. This is a local payload measurement, not production latency.

Validation:
- Broad regression: 385 passed, 3 engine cases deselected, one existing Starlette
  deprecation warning in 157.33s. Additional AU/XHTML extraction coverage was
  added after the broad run collected tests.
- Final targeted extraction/cache/compression suite: 33 passed, one existing
  warning in 4.19s. Includes original extractor tests, captured government pages,
  genuine isolated SQLite ingestion and genuine admin-authenticated compression.
- Current changes are local and awaiting user review before commit/release.
  Existing config/plans.json (10 days), chat-log and local context are preserved.

- Final cache/compression browser smoke: Chromium, Firefox and WebKit, 3 passed in 12.52s. No production release was made for this current batch.
- Local review server started at http://127.0.0.1:8000 with isolated SQLite and external providers disabled. Genuine curl checks: home 200 with gzip/no-cache/ETag, plans 200 with no-cache, search 200 with no-store. Current batch remains uncommitted for user review.

## User verification: QA #3

- User ran tests/test_extraction_quality.py on 11 October 2026: 14 passed in 2.17s.
- New extraction and source-label changes approved by the verification workflow; commit them separately from pending cache/compression changes.
- Historical snapshot backfill and the empty NZ source remain unresolved; no claim that existing production records have been repaired.
- #9/#10 remain local pending user verification. No current-batch push or deployment.
- QA #3 committed after user verification: b868b76. Cache/compression API hunks and their tests remain uncommitted, separately awaiting review. No push/deployment for this commit.

## User verification: QA #9 and #10

- User ran tests/test_response_policy.py on 11 October 2026: 13 passed, one existing Starlette deprecation warning, 4.19s.
- User measured 32,095 identity bytes and 4,305 gzip bytes.
- User authorized commit and GitHub push, including the previously verified extraction fix b868b76.
- Selected release files exclude user trial configuration, chat log and local context.
- Next work: QA #11 measured search latency investigation and QA #12 per-source repair.

## Release and next fixes: 11 October 2026

### Verified release

- Development commit e3582ba includes user-verified #9/#10 and the #3 commit record.
- Both GitHub remotes pushed successfully. Client main release: c837276, parent f9dbc15.
- Ran the existing VPS deploy script. API and crawl timer active.
- Live read-only health check: status ok, version c837276, database ok.
- User-modified plans.json (10 days), chat log and local context excluded.

### QA #11: measured search latency and concurrency

- Read-only production repository samples, five requests per query, milliseconds:
  - Empty query: 985.2, 162.2, 180.2, 197.9, 170.4.
  - parking: 308.4, 88.5, 110.1, 110.4, 95.1.
  - zoning: 248.3, 129.4, 102.5, 102.2, 540.3.
- Supabase search performs two blocking SDK HTTP requests. The async search
  endpoint called these directly, blocking the event loop while awaiting I/O.
- Changed the endpoint to a synchronous FastAPI route, so database and account
  access checks execute in the framework worker pool. Query semantics, exact
  counts and access gating are preserved; no server-side response cache added.
- Added a concurrency regression with genuine isolated SQLite: hold the search
  read open, confirm health completes before search is released, then confirm
  normal gated search output. This verifies isolation, not a claimed reduction
  in a single query's database time.
- Cold-connection and upstream variance remain. No claim of uniform sub-second
  production latency or that the whole variance problem is resolved. The new
  route change has not been deployed pending user verification.

### QA #12: broken-source maintenance

- Audited all 24 previously inactive configured sources read-only. Local probe
  artifact: ignored test-results/source-audit-20261011.json.
- Rechecked reachable US alternatives from the VPS because local requests and
  production network access differed materially.
- Updated only eight authorized source objects in sites.json. IDs, source count
  and unrelated objects are preserved. Discovery uses narrow official legal
  links, excluding unrelated navigation, application forms and tracking pages.
- Each restored source has genuine adapter discovery plus actual PDF extraction
  evidence. Health details explicitly say ingestion pending, not already ingested.

| Source | Discovered documents | Verified legal PDF text | Scope |
| --- | --- | --- | --- |
| San Diego | 16 | Update 115: 4 pages, 4,414 cleaned characters | Official zoning amendments |
| San Bernardino | 21 | Ordinance 4309: 19 pages, 38,032 cleaned characters, VPS OCR | Development-code amendments and ordinances |
| Miami-Dade | 12 | District regulations: 48 pages, 128,981 cleaned characters | Published zoning district regulations |
| Austin | 20 | Rule 161-26.15: 4 pages, 6,737 cleaned characters | Development regulatory update documents |
| Harris | 2 | Water-well regulations: 9 pages, 8,973 cleaned characters, VPS OCR | Published water-well and stormwater regulations |
| Dallas | 2 | Floodplain regulations: 34 pages, 73,293 cleaned characters | Published floodplain regulations and fire code |
| Tarrant | 2 | September 2026 manual: 74 pages, 48,474 cleaned characters | Current development and engineering manuals |
| Bexar | 1 | Court order: 2 pages, 2,519 cleaned characters | Published stormwater fee court order |

- NYC homepage and adopted-rule listing respond 200, but genuine individual
  rule pages/PDFs return 403 from both local and VPS checks. Keep inactive.
- Santa Clara's replacement official planning domain still returns 403 from
  VPS and local checks. Keep inactive. No CAPTCHA/access-control bypass used.
- Fourteen other inactive international/API sources remain separately unresolved:
  Alberta, Calgary, Quebec, Montreal, London, Glasgow, Edinburgh Gazette,
  Melbourne, UK catalogue API, both Canada Justice sources, NZ API, EU CELLAR,
  German XML index. The initial audit is recorded; not all are proven permanently
  inaccessible. NZ API needs a client key; the German index now responds but
  points to XML ZIP archives unsupported by the current ingestion path.
- Austin document.cfm and Bexar DocumentCenter return PDF without .pdf suffix.
  Crawler now inspects Content-Type and PDF signature before HTML extraction,
  reusing the fetched response. Regression verifies both advertised PDF and
  octet-stream PDF handler bodies through genuine isolated SQLite ingestion.
- Captured public-link-only fixtures support repeatable adapter regression.
  No document binaries, secrets or sessions committed.
- No live crawl, source database writes or historical backfill performed. These
  fixes do not establish exhaustive coverage or make all 65 sources operational.

### Verification and next user check

- Targeted extraction, concurrency, response policy, schema contract, Supabase
  branches, adapters, customer gating, crawler, notifications and API regression
  run together after the source repairs. Results recorded below.
- New #11/#12 code and documentation remain local for the agreed user review
  before commit. Previously verified #3/#9/#10 are already pushed and deployed.
- User command: .\venv\Scripts\python.exe -m pytest tests/test_search_concurrency.py tests/test_source_repairs.py -v -p no:cacheprovider --basetemp=test-results/user-search-source-check

- Final combined regression: 196 passed, one existing Starlette deprecation warning, 15.33s. Selected tracked-file whitespace check passed.

## Browser verification requested by user: QA #11/#12

- Opened real Chromium against the existing local review server at 478px width.
  parking/zoning repeated three times each: six genuine HTTP 200 responses,
  truthful empty state, no page JavaScript errors and no page overflow.
- Genuine admin form login succeeded. Browser checked all eight repaired source
  IDs, URLs, active flags and health labels against config, and confirmed NYC
  and Santa Clara remain inactive. Austin filter rendered the genuine source row.
- Initially local SQLite still showed 41: its stored source records were stale.
  Attempting the real update revealed upsert_source conflicted on base_url,
  causing a primary-key error when a stable source ID received a replacement URL.
- Fixed Supabase conflict selection to ID when supplied, retaining base_url for
  callers without ID. SQLite updates by stable ID and persists real health,
  activity, jurisdiction and status fields, preserving omitted fields and existing
  document relationships. No schema changes or production data writes.
- Regression stores an old source/document, updates its URL/status, verifies one
  source and preserved document relation; Supabase conflict test updated.
- After the fix, synced exactly eight genuine configurations into isolated local
  review SQLite. Browser verified operational count 49, total 65. This represents
  verified source configuration, not completed ingestion or complete coverage.
- 124 relevant regression tests passed, one existing warning, 16.27s.
- Added actual Chromium concurrency regression: delayed genuine SQLite search
  remains open while a second browser tab loads health. Both concurrency tests
  passed, 4.24s. Production single-query latency variance remains unresolved.
- Local review server restarted to load the persistence fix and health checked.
- Screenshots/evidence are ignored test-results/browser-review-11-12: mobile-search.png,
  admin-austin-source.png, admin-sources.png and report.json. New changes remain local.
- Trial configuration remains the user's 10 days; no trial-setting edit performed.

## User-authorized deployment and QA #23/#24/#25

### Deployment of verified #11/#12 fixes

- User explicitly requested deployment after browser verification.
- Development commit f63acc9; clean client main release e33ef18, parent c837276.
  Both remotes pushed and existing VPS deploy script completed successfully.
- Synced exactly the eight verified source configurations into existing production
  source IDs via Supabase conflict on ID. Did not run a crawl or change billing.
- Production health: version e33ef18, database ok; public sources 49/65; trial14.
- Genuine live Chromium checks: six pages at mobile width, light/dark, 12 checks
  passed with no page JavaScript errors or horizontal overflow after fonts loaded.
- Existing historical extraction/backfill, remaining inactive sources and upstream
  latency variance are still pending. Source activation does not prove ingestion.

### QA #23: paid account states

- Expanded existing genuine local SQLite subscription-state checks to active,
  suspended/paused, cancelled within paid period and cancelled expired.
- All four states checked in light/dark at 375px and 1280px on three engines:
  48 state views, genuine API authentication and server-returned search access.
- Added UI pause, resume, cancellation abort, cancellation confirm and expiry
  transitions on each engine. Actions use genuine API endpoints and persisted
  local database state. PayPal operations explicitly mocked, lifecycle email
  disabled. No real charge, subscription mutation or external email used.
- Expired cancellation checked for denied access, not merely a visible badge.

### QA #24: browser engines

- Chromium, Firefox and WebKit run actual authenticated search and account flows
  against a real isolated Uvicorn server. Search is typed in the page; logout
  changes to genuine gated results. No response or UI-state mocks.
- Initial combined state/lifecycle/engine run: 54 passed, 33 deselected, 234.85s.
- WebKit is engine coverage, not a run of native Safari on macOS/iOS. Physical
  mobile Safari/Chrome and native Safari remain uncovered in this Windows setup.

### QA #25: automated accessibility audit and fixes

- Vendored unmodified axe-core 4.10.3 for repeatable offline QA, retaining its
  MPL/copyright notice. It is a test dependency, not shipped to customer pages.
- Run the complete default axe ruleset, including best-practice checks, after
  fonts and finite UI transitions settle; retain violations and incomplete nodes.
- Audit real signed-out six-page views; login/register/OTP/wrong-code/reset and
  plan dialogs; trial and all four paid states; cancellation dialog; authenticated
  admin, Plans tab and inline plan editor. Mobile/desktop and light/dark.
- Found and fixed missing admin login/edit-field labels, invalid chart/list
  semantics, duplicate region names, unfocusable horizontally scrolling tables,
  inactive badge contrast, missing account h1 headings and cancellation heading
  order. Auth dialog's referenced heading did not exist; added a real accessible
  heading that follows the selected login/register/verification mode.
- Axe checks supplement manual keyboard/screen-reader evaluation. They are not
  a Lighthouse performance audit, complete accessibility certification or proof
  that every possible dynamic state was reached.
- Evidence: ignored test-results/qa-23-25/account screenshots and accessibility
  JSON reports. New QA fixes are local; deployed release remains e33ef18.
- Full regression: 451 passed, one dependency deprecation warning, in 491.31s.
- Final post-ARIA accessibility audit: 4 passed in 102.59s, 84 views with zero
  confirmed violations. Incomplete automated checks remain for manual review.

- Expanded default axe audit and post-fix lifecycle rerun: 7 passed in 102.08s.
  Audit covers 21 real views per viewport/theme combination, 84 views total,
  with zero automated violations. Inconclusive contrast checks (single-digit
  counters, native select and overlapping modal backgrounds) are retained for
  manual review, not counted as proven passes.
- Full default axe exposed additional missing heading/region semantics. Avatar
  and keyboard-hint accessible labels received valid roles after review of
  incomplete ARIA checks; the final audit verified these follow-ups.
- QA #23 local paid-state/lifecycle verification complete with provider mocks.
  QA #24 three-engine coverage complete; native Safari/physical devices pending.
  QA #25 automated axe coverage complete; manual keyboard/screen-reader and
  inconclusive contrast review pending. New QA changes committed separately from
  the deployed e33ef18 release; no new production billing actions performed.
