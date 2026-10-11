# Implementation priorities, 10 October 2026

User-approved order. Numbers below are priorities, not frontend fix-plan IDs.

| Priority | Work | Status |
| --- | --- | --- |
| 1 | Verify repository, deployment parity and existing order scope | Verified code and deployment; historical payment records differ from current user statement |
| 2 | Remaining frontend bugs and dark mode | Reopened after user review: trial configuration, OTP delivery, loading and auth feedback need another pass |
| 3 | Backend cache headers, compression and search latency investigation | Pending |
| 4 | Regression, paid subscription states, cross-browser and accessibility QA | Pending |
| 5 | Evidence-based case studies using available captured changes | Pending |
| 6 | Housekeeping: About punctuation and existing chat-log changes | Pending |
| 7 | Repair broken US city and county sources | Pending |
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
