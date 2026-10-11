# JurisMon implemented work ledger

Updated 11 October 2026. Append future implementation here; current outstanding
work is in [remaining-work.md](remaining-work.md). Detailed older work history:
[implementation-priority.md](implementation-priority.md).

Implementation, verification and deployment are separate states. A passing
mocked-provider test does not prove live PayPal lifecycle or inbox delivery.

## Existing product baseline

| Work | How implemented | Evidence / limits |
| --- | --- | --- |
| Modular daily crawler and source catalogue | Platform adapters, per-source config, VPS systemd crawl service/timer | 65 configured sources. Fresh API marks 49 operational; this does not prove all 49 delivered legal documents. Manual crawl/polling observed live. |
| Extraction/OCR, snapshots and legal diffs | HTML/PDF parsing, OCR fallback, timestamped Supabase/SQLite persistence and section/paragraph comparison | Code and regression tests exist. Live contaminated/empty snapshots remain; extraction is not universally clean. |
| Search and teaser paywall | Snapshot/diff search, truncated anonymous items, authenticated full results | Fresh live anonymous response has no results key; admin response retains it. Card previews 129.48-250.08px across 31 live authenticated results. |
| Authentication and trial | Signup, six-digit verification, JWT sessions, login and forgot/reset password | Genuine local API/browser checks; live mailbox delivery not exercised in this round. Delivery-failure bug remains. |
| Billing integration and customer account controls | PayPal checkout/webhooks; pause/resume/cancel and period-based access; transactional confirmation templates | Existing shipped code. Four states and lifecycle transitions verified locally with explicit provider mocks. No real charges/lifecycle calls performed. |
| Admin pricing and trial configuration | Dynamic catalogue, guarded plan edits, atomic settings reload and audit rows | Live name-only edit/history verified then restored. Both genuine 409s rendered within 2s. No claim that arbitrary price input creates a new PayPal plan. |
| Public pages, brand and basic SEO | About, Terms, Privacy, footer/contact, client logo/icons, metadata/canonical/sitemap | Six pages opened live. Broader SEO, case studies and marketing tools not delivered. |
| Health/deployment operations | Genuine /api/health DB check, nginx/TLS, systemd, explicit deploy script | Live e33ef18 reports database ok. Push alone does not deploy. |

## Verified fixes and releases

| Work | What changed and why | Verification | Release state |
| --- | --- | --- | --- |
| Paywall response leaks | Removed raw results and capped teaser segments as well as text | Fresh signed-out response: gated, 2 items, no results key; admin path full, 31 items | Live; historical fixes b5f53bb/c42d1c5. |
| Oversized previews | Client caps snapshot/diff previews while retaining explicit expand controls | All 31 authenticated live cards measured below 251px collapsed | Live. |
| Loading/auth/search transitions | Immediate skeleton during session/search requests, stale-response guards, real success feedback | Genuine delayed/out-of-order response and login/logout browser regressions | Live frontend release f9dbc15, retained in e33ef18. |
| Responsive themes and OTP stability | Compact signed-in header, contained pills/tables, semantic light/dark tokens, reserved OTP feedback space/focus | Fresh 48 live page-width/theme measurements show no horizontal overflow; local wrong-OTP checks | Live. |
| Configured trial duration | Home/account/Terms/signup/verification/email copy and trial activation use admin catalogue; zero-day handling; preserve existing expiries | Tests cover 14/34/45/67/0 and activation changes. Live trial 14; user's local 10 preserved | Live. |
| About scope correction | Describes selected US local sources and international national registries; removes absolute history/extraction claims | Current About copy/code and browser checks | Live, but homepage municipal-only wording and dedicated exclusions section remain. |
| Cache and compression | Endpoint-specific cache policy, HTML revalidation, gzip for sizeable JSON | Fresh live HTML and source/search responses compressed; authorized APIs no-store; existing response-policy tests | Development e3582ba; live release c837276, retained in e33ef18. |
| Extraction quality guards | Reject catalogue/RSS/XML metadata and empty legal text; preserve actual XML statute sections; inspect embedded Australian legal document | 14 extraction regression tests; live dirty records show further path/backfill work is needed | Development b868b76; live release c837276, retained in e33ef18. |
| Search concurrency | Synchronous search handler executes blocking repository/access work in worker pool | Slow-search/independent-health API and real-browser checks | Development f63acc9; live e33ef18. Latency variance remains. |
| Eight existing US source repairs | Updated official document links for San Diego, San Bernardino, Miami-Dade, Austin, Harris, Dallas, Tarrant and Bexar; handle PDF MIME/signature; stable ID upsert | Real official legal documents/extraction and upsert tests; eight configs synced into existing production IDs | Development f63acc9; live e33ef18. Post-crawl ingestion verification pending. |
| Paid/cross-engine QA | Four paid states in two widths/themes across Chromium/Firefox/WebKit; genuine local JWT/DB; explicit provider mocks for transitions | 48 state views plus lifecycle/search checks. One Firefox navigation timeout in latest full run; 3 isolated reruns pass | Tests in development b67560f; no production billing changes. |
| Accessibility semantics | Real labels/headings/dialog name/roles, scroll-region focusability, inactive badge contrast | Latest local axe: 84 views, zero confirmed violations. Incomplete contrast/manual review retained; closed-modal Tab bug newly found | Development b67560f; NOT deployed. |

## Current testing/documentation round

- Applied the user-supplied Rigorous Testing Prompt v2 to live e33ef18 and
  isolated current code. Full regression: 450 passed, one Firefox navigation
  timeout, one existing dependency warning, 569.16s. Exact failed case passed
  three isolated reruns: 9.60s, 8.23s and 8.28s. No unsupported cause assigned.
- Extra audit harness: two checks completed in 60.68s (auth/deep-link/reflow,
  genuine 31s polling), plus mail-failure evidence capture in 5.25s. These are
  observation collectors, not proof that every recorded behavior is correct.
- Fresh three-engine live search/filter/clear/zero-match/account/gate checks
  completed without page JavaScript errors. All ten selected source URLs were
  attempted; source/content classifications and access limits are in the report.
- Live plan edits were restored: Professional $49/month and Professional
  (Annual) $468/year, both active; trial14. Test audit-history rows remain as
  genuine records of the reversible edits.
- Manual live crawl was started as required by the prompt. Seventeen successful
  status responses were observed across over 60 seconds; final status still
  running. Do not mark the run complete or all documents clean.
- Created separate client context, remaining-work backlog, this implementation
  ledger and [rigorous report](../reports/2026-10-11-rigorous-testing-v2.md).
  No application fix or new deployment was performed in this documentation round.

## Append format for future work

For each R-ID, record date, concrete change, files/approach, actual verification,
limitations, development commit and deployed version (or not deployed). Update
remaining-work.md only when the stated acceptance check is met. Payment status
belongs in client-context.md and requires its own evidence.

## R-02: Authentication email failure handling, 11 October 2026

- Signup and confirmation resend now return HTTP 503 when the mail provider
  rejects delivery, throws, or code persistence fails. The registration form
  remains visible on failure, rather than claiming a code was sent.
- Shared dispatch helper in `api/main.py` persists replacement codes only after
  provider acceptance, using the existing SQLite/Supabase repository method.
  Failed initial signup leaves an unverified account with no active code or trial;
  retry can complete registration. Failed resend keeps the old code and expiry.
- Forgot-password uses the same helper and preserves prior usable codes on failure.
  Its response remains identical for known/unknown emails to avoid account
  enumeration. Reset screen and resend notification say a request was made,
  without claiming an email was sent. Existing rate limits remain.
- Added eight meaningful regression cases in `tests/test_auth_delivery.py`,
  including provider false/exception, initial retry, persistence refusal and a
  genuine Chromium flow against temporary SQLite/real API: failed signup,
  successful retry, failed resend, old-code verification, and reset feedback.
  Existing authentication tests now explicitly mock successful provider acceptance.
- Verification: authentication/trial/API/Supabase/schema selection: 121 passed
  in 40.40s. After extending the reset browser check, delivery/notification/
  subscription selection: 49 passed in 20.46s. Each reports one existing
  Starlette/httpx deprecation warning. These are overlapping selections, not
  170 unique tests. No full-suite claim, external email, or billing call.
- Provider acceptance does not prove inbox arrival; controlled mailbox QA remains
  R-11. Delivery and database persistence are separate operations: an accepted
  email followed by failed persistence receives no success response. Concurrent
  successful replacements retain the existing latest-code behavior.
- Development commit: the commit containing this R-02 entry (locate with
  `git log --oneline --grep="fix: handle authentication email delivery failures"`).
  Not pushed or deployed in this repair. Production remains e33ef18.

## R-03: Dialog keyboard lifecycle, 11 October 2026

- Auth and paywall overlays begin inert/aria-hidden. A shared controller opens
  one dialog, remembers background inert state and restores it on close.
  Focus moves inside, wraps on Tab/Shift+Tab, and returns after Escape/backdrop/
  close-button handling. Pointer opener tracking fixes WebKit's non-focusing clicks.
- Genuine browser keyboard regression checks both dialogs across Chromium,
  Firefox and WebKit. Closed overlays receive no focus through 30 Tab presses.
- Initial verification found a WebKit focus-return failure; corrected and reran.
  Final keyboard/accessibility selection: 7 passed in 90.97s. Existing auth delivery
  selection previously passed 8 cases alongside two keyboard cases; WebKit failure
  was the only initial failure. No native Safari claim.
- Files: frontend/index.html and tests/test_dialog_keyboard.py. Development commit
  containing this entry; not deployed. Live remains e33ef18.

## R-04: Genuine crawl metrics, 11 October 2026

- Repository reads today's UTC crawl rows and latest run in both SQLite and
  Supabase. Production query errors surface instead of becoming invented zero
  counts from a local database. No schema change required.
- Admin overview/status include crawl_metrics. Dashboard counts started runs,
  running runs and failed/partial runs; latest status/time comes from crawl_runs,
  not source timestamps. Polling refreshes both widgets after real run completion.
  Removed the misleading source-health bars labelled as 14-day failed runs.
- Real isolated admin browser starts a genuine recorded run and observes completion.
  UTC cutoff, prior-day exclusion, empty state and Supabase failure handling tested.
- Metrics/polling/Supabase/schema selection: 28 passed in 42.67s.
- Files: db/repository.py, api/main.py, frontend/admin.html,
  tests/test_crawl_metrics.py. Development commit containing this entry;
  not deployed. No live crawl triggered for this verification.

## R-12 and R-16 copy: Honest coverage, 11 October 2026

- Added dedicated About coverage/exclusions section, linked on homepage. Explains
  configured versus recorded operational status versus captured documents, mixed
  local/international scope, restricted/unreachable sources, incomplete historical
  captures and legal-effective-date limits. No source count implies ingestion.
- Corrected homepage, preview/trial and plan copy. Removed About's unsupported
  monetary risk range and claim that unavailable amendment email alerts are live.
- Browser check uses actual repository counts (including automatically seeded
  catalogue), follows the coverage link and checks limitations. Initial test assumed
  an empty catalogue; fixed its assumption rather than changing application data.
- Coverage plus real-PDF/extractor/source repair checks: 34 passed in 4.92s.
  Broader frontend browser regression is recorded separately when complete.
- Files: frontend/index.html, frontend/about.html, tests/test_coverage_browser.py.
  Development commit containing this entry; not deployed. This does not close
  case studies or validate every historical document.

## R-05 partial: PDF ingestion and historical audit, 11 October 2026

- Found and fixed `.pdf` branch unpacking three values from a four-value extractor.
  Genuine generated PDFs now store legal text through suffix and MIME/signature paths.
- Added conservative capture_issue checks for empty text, known Germany catalogue,
  Canada dataset/resource wrappers and Australian registry furniture. Ingestion rejects
  these captures and does not create amendment diffs against contaminated baselines.
  Known XML/HTML guards and embedded Australian legal-document following remain.
- Added read-only paginated historical audit CLI for SQLite and Supabase, emitting
  snapshot IDs/versions/reasons without text, credentials or destructive writes.
  This produces a reviewable remediation manifest; it is not a cleanup/backfill.
- Extraction/audit/source-repair/extractor/crawler selection: 49 passed in 3.06s.
  Both backend read paths and unchanged snapshot history tested. Earlier sandbox
  run hit pytest temporary-directory permissions; escalated rerun passed.
- Production read-only API check still shows polluted historical records from before
  this repair; existing manual crawl remains running. No source ingestion or legal
  case study is marked verified from source-health metadata.
- Files: scripts/run_crawler.py, extractor/capture_quality.py,
  scripts/audit_capture_quality.py, tests/test_capture_quality.py,
  tests/test_extraction_quality.py. Development commit containing this entry;
  not deployed. R-05 remains open for historical remediation and source backfill.

### Broader browser verification after coverage changes

Existing frontend selection: 84 passed, plus the initial coverage test's catalogue
count assumption failure (286.08s). Corrected coverage test passed in the separate
34-check selection recorded above. The full selection ran before that test correction;
do not present the original run as fully passing.

## R-14/R-15 preparation: Competitor gaps, 11 October 2026

- Reviewed official ZoneWire home, API docs, pricing, states, meetings, blog and
  comparison pages, plus Bassett's current early-access page. Paid behavior was not
  tested. Pricing/home counts and API availability wording differ; noted explicitly.
- Created 19-row Google Sheets import CSV with page links, actual JurisMon matches/
  gaps, useful/deferred recommendations, priority, dependencies and effort estimates.
- Prepared optional scope/acceptance/delivery ordering and budget formula. Preserved
  historical $100/$150/$25 quotes; no new invented commercial offer or payment claim.
- Verified CSV round-trip: header plus 19 rows. No connected Google Sheets session;
  CSV is importable, not claimed delivered to a sheet. Final selection/rate pending.
- Files: docs/client/competitor-gap-list-2026-10-11.csv and
  docs/client/competitor-implementation-scope.md. Development commit containing entry.

## R-09: Search request load and measured reads, 11 October 2026

- Increased typing debounce from 120ms to 300ms, aborts superseded requests,
  preserves version guards and cancels pending typing timers on Escape/clear.
  Abort does not guarantee cancellation of an already running database query.
- Real browser types parking at 40ms/character: one search request. Immediate
  Escape after editing emits one empty-query request and no delayed stale search.
  Search/loading/login/older-response selection: 7 passed in 29.67s.
- Read-only production repository samples (ms): empty 1522.91/148.43/138.06;
  zoning 289.58/202.81/139.66; parking 135.02/94.31/83.37. These include SDK/network
  round trips, not SQL execution time. Serialized result sizes 293789/759185/280554
  bytes respectively, not compressed wire sizes. No unsupported root cause assigned.
- Evidence: ignored test-results/remaining-search-measure.json. Files:
  frontend/index.html, tests/test_search_requests.py. Development commit containing
  entry; not deployed. Database query-plan tuning remains optional follow-up.

## R-05 continuation: Reversible capture quarantine, 11 October 2026

- Added is_searchable/quality_reason to snapshots and diffs in SQLite and matching
  migration 009 (PostgreSQL BOOLEAN default TRUE). Existing captures remain searchable
  until explicitly reviewed; original text, IDs, timestamps and versions are preserved.
- Both backend search paths and their counts exclude quarantined rows. Visibility
  operations preserve other review reasons, hide dependent diffs, and restore a diff
  only after all referenced snapshots are visible. Production write errors surface;
  no accidental local fallback mutates a different database.
- Audit CLI defaults to read-only, --apply quarantines a fresh conservative audit,
  --restore-manifest restores only that operation. Operation ID/manifest saved before
  writes so partial failures remain reviewable/restorable. No delete operation.
- Source-only crawler CLI supports repeatable --source IDs and rejects unknown IDs
  before database writes. It enables verifying repaired sources without launching
  an unbounded whole-catalogue run; default scheduled scope is unchanged.
- Verification: before quarantine additions, full suite 477 passed in 514.64s,
  one existing dependency warning; former Firefox timeout not reproduced. After
  additions, quarantine/audit/extraction/Supabase/schema/API selection: 118 passed,
  one warning in 15.77s; real browser/ingestion selection 37 passed in 5.61s.
  Final affected selection after row-count/subset adjustments: 51 passed in 7.36s.
- Read-only live evidence: 3755 snapshots checked, 2343 known non-document patterns
  flagged; all eight repaired source IDs had zero stored documents at the read.
  See docs/reports/2026-10-11-capture-source-review.md. Sixteen unresolved endpoints
  reviewed; index 200 responses alone did not justify activating sources.
- Production migration connection verified via SELECT 1 without exposing credentials.
  Migration/application/release status will be appended after actual execution.

## R-06: Check crawl dispatch before acknowledging start, 11 October 2026

- Production had a running crawl record while the systemd crawl unit was inactive.
  The previous Popen path discarded stderr and did not check the command exit code;
  process creation alone could acknowledge a failed dispatch. The precise historical
  failure is not proven by that observation.
- Dispatch now awaits a checked, noninteractive systemctl command in a worker thread
  with a ten-second timeout and --no-block. Rejected/timed-out dispatch schedules the
  existing background runner with the same run ID instead of silently losing the job.
- Verification: dispatch, API and metrics selection 75 passed in 18.09s, one existing
  dependency warning. Tests cover accepted dispatch, nonzero exit and timeout, and
  verify that fallback schedules exactly one job for the recorded run.
- Files: api/main.py and tests/test_crawl_dispatch.py. Not yet released.

### Production preparation and current authorized scope

- User confirmed existing fixes and promised deliverables first; unplaced alerts/
  watchlists and 88-source expansion remain outside this implementation batch.
- Applied only migration 009 to production in one PostgreSQL transaction, recorded
  its checksum, and notified PostgREST to reload schema. Verified both tables have
  non-null BOOLEAN is_searchable default TRUE and nullable TEXT quality_reason.
  Existing records remain visible; no quarantine or deletion occurred in this step.
- Fresh process check: crawl unit inactive, MainPID=0, no run_crawler.py process;
  API NoNewPrivileges=yes. Historical running record is not proof of an active crawl.

## Verified production release and cleanup, 11 October 2026

- Full isolated regression before release: 486 passed in 521.69s, one existing
  dependency warning. Clean client release 0c8d0a4 pushed and deployed using the VPS
  script; service/timer active, production health database ok, trial setting 14.
- Genuine live Chromium checked six public pages in light/dark at mobile width,
  plus authenticated admin: zero axe violations, no overflow or JavaScript errors.
  Incomplete axe checks remain manual QA. Closed dialogs, focus trap, Escape and
  return focus passed on live Chromium, Firefox and WebKit. Evidence ignored under
  test-results/remaining-live; no mocked frontend or paid lifecycle requests.
- Applied fresh conservative quarantine: 3755 snapshots audited; 2343 snapshots
  and 1852 dependent diffs hidden from search. No records/text deleted. Restore
  manifest saved before mutation on VPS and copied locally to ignored
  test-results/production-capture-quarantine.json. Reason timestamp
  capture_audit:2026-10-11T13:20:23.079757+00:00. Unflagged is not certified legal.

## R-06 continuation: Report actual ingestion failures

- Successful link discovery no longer counts as a successful source when document
  fetching/extraction/persistence fails or no usable stored documents exist.
  Verified unchanged searchable documents count as success; rejected captures and
  per-document failures are retained in crawl error details. documents_found still
  means discovered/attempted documents, not new snapshots.
- A failed snapshot/document persistence confirmation is now reported explicitly.
- Affected extraction, dispatch, capture and metrics tests: 37 passed in 12.29s.
  Covers failed fetch, empty discovery, mixed rejected/legal captures, real PDFs and
  unchanged legal documents. This follow-up is not in release 0c8d0a4 yet.

## R-05/R-06: Executed backfill and storage-error repair

- Outcome follow-up deployed as ea54057. Source-only production run 83e4a73e
  finished partial_failure at 14:05:09 UTC: 7/8 successful, 76 discovered documents,
  60 actual new baseline captures, zero new diffs. Mail explicitly disabled.
- Actual stored captures: San Bernardino 21, Austin 20, Miami-Dade 12, Harris 2,
  Dallas 2, Tarrant 2, Bexar 1. San Diego 0: all 16 PDF downloads timed out.
  Updated only these eight config blocks from evidence; degraded San Diego remains
  active for daily retry. Config status synchronization follows final release.
- Historical stale running record was marked failed by existing recovery. No
  completed-run claim assigned to an unconfirmed dispatch. Raw snapshots increased
  3755 to 3815 from new captures; raw diffs remain 2647; no history deleted.
- Ingestion source/document/snapshot/diff writes and latest-baseline lookup now
  raise production storage errors instead of redirecting into SQLite. Five failure
  cases prove no local database access on a configured Supabase error. Local
  SQLite remains supported when no production client is configured.
- Storage/extraction/schema selection: 44 passed. Updated old characterization
  test to require no redirected write. Final complete suite: 498 passed in 528.38s,
  one existing dependency warning. Intermediate full run had two test-expectation
  failures (496 passed), corrected and targeted API/case selection 75 passed before
  the final complete passing run. Do not report the intermediate run as passing.

## R-12/R-13/R-16: Evidence-backed case studies and housekeeping

- Added /case-studies and restricted /api/case-studies with two written examples:
  Austin preservation-bonus rule and San Bernardino Ordinance 4400. Reviewed
  official notices/listings; actual production captures contain the selected
  legal sections, verified internally without exporting source text. Versions/date
  are real; official legal dates are shown separately. Baselines, historical law
  limits and absence of customer/market-validation proof are explicit.
- Both SQLite and Supabase publication checks require a visible matching capture.
  Missing/quarantined evidence withholds a case; storage errors give 503/retry.
  The page uses textContent, supports light/dark/mobile, and has search deep links.
  No full captured text is exposed by the public case-study endpoint.
- Coverage displays actual inactive names/statuses from a restricted public
  summary; full source URLs/config remain admin-only. Local API/browser checks
  cover actual list counts and missing evidence, both storage branches, supporting
  terms, withheld captures, search links, overflow and axe.
- Documentation index now points to the current backlog/ledger/commercial context;
  old task board labelled historical. Next-migration guidance corrected to inspect
  current directory (009 exists; next 010). Raw client chat/settings untouched.
- Written evidence file: docs/client/case-studies-evidence.md. Final release pending.
- Google Sheets connected-session lookup returned no sessions; competitor CSV
  remains ready for import, not delivered to a live sheet. Native-zoom profile
  experiment did not change actual Chromium zoom; it does not close that QA gap.

## Final release acceptance, 11 October 2026

- Development implementation commit 408c97f published to origin. Clean client
  release e2693b7 pushed to client/main and deployed using the VPS script. Service
  and timer active; health version e2693b7, database ok. Documentation updates after
  acceptance do not imply a separate application deployment.
- Synced/read-back exactly eight reviewed source rows from released config. San
  Diego is degraded and still active for retry; public API reports 48 sources marked
  operational of 65 configured, with 16 inactive names/statuses only (no URLs/config).
- Genuine final live verification: 14 page/mode views across seven pages, light/dark
  mobile; two published evidence-backed cases; authenticated admin; trial 14; zero
  axe violations, no horizontal overflow or JavaScript errors. Chromium, Firefox
  and WebKit closed-dialog/trap/Escape/focus-return lifecycle passed.
- Initial live home axe measurement during finite result-card entry animations
  flagged contrast; repeated after animations settled passed. No CSS or failure
  filtering changed to obtain that pass. Axe incomplete items remain manual QA.
- Evidence: ignored test-results/remaining-live/verification.json and per-page axe
  JSON, production-backfill-final.json, production-case-evidence.json, and reversible
  quarantine manifest. Raw production excerpts/URLs export was rejected by automatic
  approval review; safer aggregate-only audit and internal supporting-section checks
  succeeded. No blocked content export was retried indirectly.
- Still external/manual: San Diego PDF availability, sixteen excluded endpoint
  replacements/adapters, controlled real inbox, PayPal Sandbox credentials, native
  device/screen-reader/200% zoom QA, connected Google Sheet, and selected competitor
  scope/rate. No ordered alerts/88-source expansion or fabricated market-validation
  evidence was added. Current backlog records these separately from shipped work.
