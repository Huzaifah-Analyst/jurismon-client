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
