# JurisMon Engineering Memory: Lessons Learned the Hard Way

> **Audience**: AI coding agents working on JurisMon.  
> **Purpose**: Forensic record of real failures that reached production or survived code review.  
> **Source of Truth Reference**: Documented in detail in [docs/context/03_FAILURE_LOG.md](file:///d:/fiverr%20client/malok%20mading/docs/context/03_FAILURE_LOG.md).  
> **Tone**: Objective, direct, and unvarnished. Read these so you do not repeat them.

---

## Incident 1: SQLite / PostgreSQL Column Drift Broke Production Three Separate Times

- **What Broke**: The application ran and passed 100% of unit tests locally, but crashed immediately upon deployment to production with database column errors (e.g. `column "sources_skipped" does not exist`, missing customer authentication columns).
- **How It Was Found**: Live API calls threw HTTP 500 errors on the production VPS; daily crawl recording crashed.
- **Root Cause**: `_init_sqlite_schema()` in [`db/repository.py`](file:///d:/fiverr%20client/malok%20mading/db/repository.py) dynamically creates tables and adds columns on the fly for SQLite. Developers added columns to SQLite locally, tested against SQLite, and forgot to create matching PostgreSQL migrations in `db/migrations/*.sql` for Supabase.
- **The Fix**: Added migration `006_crawl_sources_skipped.sql` and implemented an automated schema parity test ([`tests/test_schema_contract.py`](file:///d:/fiverr%20client/malok%20mading/tests/test_schema_contract.py)) that introspects the SQLite schema and asserts every column has an identical migration in `db/migrations/`.
- **The Rule**: **Rule 1 (Dual-Schema Parity)**. Every column added to SQLite requires a numbered migration file in `db/migrations/` in the same commit. `pytest tests/test_schema_contract.py` must pass before pushing. Next migration number is `008`.

---

## Incident 2: `set_verification_code` Had No Supabase Branch, Breaking Live Verification

- **What Broke**: Real customers on `https://jurismon.com` received 6-digit confirmation codes via email but were told `Invalid verification code` upon entering them. Customer registration was completely broken in production.
- **How It Was Found**: Live manual registration testing on production.
- **Root Cause**: `set_verification_code()` and `verify_user_email()` in [`db/repository.py`](file:///d:/fiverr%20client/malok%20mading/db/repository.py) were written only using `with self._connect() as conn:` (the SQLite branch). There was no `if self.supabase:` branch. In production, the verification code was written to a local SQLite file on the VPS disk that production Supabase queries never read. Local unit tests passed because they ran against SQLite.
- **The Fix**: Implemented the Supabase write branch in `set_verification_code()` and added unit tests in [`tests/test_supabase_path.py`](file:///d:/fiverr%20client/malok%20mading/tests/test_supabase_path.py) that mock the Supabase client to assert both branches exist.
- **The Rule**: **Rule 2 (Dual-Branch Repository Implementation)**. Every data mutation method in `db/repository.py` must implement `if self.supabase:` AND `with self._connect():`. A SQLite-only write is invisible in production.

---

## Incident 3: Empty Search Query Returned Zero Rows on PostgreSQL vs. All Rows on SQLite

- **What Broke**: The search landing page opened completely blank with zero results, despite 773 indexed statutory records existing in the production database.
- **How It Was Found**: Visual inspection of the live homepage `https://jurismon.com`.
- **Root Cause**: PostgreSQL full-text search used `plainto_tsquery('english', q)`. When `q` was empty (`""`), `plainto_tsquery('')` generated an empty `tsquery` that matched zero rows in PostgreSQL. Meanwhile, SQLite's fallback used `LIKE '%%'`, which matched every row. Local testing saw a full table; production saw nothing.
- **The Fix**: Added logic in [`db/repository.py:347-360`](file:///d:/fiverr%20client/malok%20mading/db/repository.py#L347-L360) to detect empty or whitespace queries and execute a standard timestamp-ordered select query instead of a tsquery vector match. Added regression test in `tests/test_api_and_db.py`.
- **The Rule**: Never assume PostgreSQL tsquery and SQLite `LIKE` behave identically on boundary conditions. Verify empty queries, special characters, and edge cases on both engines.

---

## Incident 4: `#auth-gate` Declared After `</script>` Tag and Hidden by Null Guard

- **What Broke**: Clicking "Log out" in the admin dashboard resulted in frozen loading spinners and no login screen. The admin panel became completely unusable after logout.
- **How It Was Found**: Manually testing the logout flow in a live browser session.
- **Root Cause**: In [`frontend/admin.html`](file:///d:/fiverr%20client/malok%20mading/frontend/admin.html), the `<div id="auth-gate">` element was placed at line 2260, after the closing `</script>` tag at line 2256. When the script initialized, `document.getElementById('auth-gate')` returned `null`. The code had a defensive null guard `if (authGate) { authGate.style.display = 'block'; }`, so it silently failed without logging a single error to the console.
- **The Fix**: Moved `#auth-gate` above the `<script>` tag and added an automated HTML structure test in `tests/test_api_and_db.py` asserting `#auth-gate` precedes `<script>`.
- **The Rule**: **Rule 4 & Rule 5**. Every element referenced by `getElementById` must be declared in markup above the `<script>` tag. Never write silent null guards on mandatory elements — they turn structural bugs into invisible failures.

---

## Incident 5: Five Commits Pushed and Never Deployed

- **What Broke**: The client reported that bugs declared "fixed" were still present on `https://jurismon.com`. Five consecutive bug-fix commits pushed to GitHub over multiple days were completely absent from the live server.
- **How It Was Found**: Client inspection of the live admin dashboard, followed by running `git log` on the VPS which showed the server was five commits behind.
- **Root Cause**: Developers assumed GitHub repository pushes triggered automatic continuous deployment. The VPS had no automated CI/CD webhook runner configured.
- **The Fix**: Documented the deployment runbook in `docs/HANDOVER.md` and created `scripts/deploy.sh`.
- **The Rule**: **Rule 10 (Pushing Is Not Deploying)**. `git push` updates GitHub; it never updates the server. Code is not live until deployed to the VPS via SSH (`bash scripts/deploy.sh`) and verified via health check.

---

## Incident 6: PayPal Email Mismatch Would Charge Users Without Granting Access

- **What Broke**: A customer paying via PayPal whose PayPal account email differed from their JurisMon login email would be charged monthly without their JurisMon account ever receiving active access.
- **How It Was Found**: Code audit of the PayPal webhook resolution path prior to Phase 1 delivery.
- **Root Cause**: The webhook listener matched incoming subscription events against users exclusively by `resource.subscriber.email_address`.
- **The Fix**: Injected the customer's internal `user_id` into PayPal's `custom_id` field during checkout creation, and updated `api/payments/paypal_provider.py` to resolve the customer account by `custom_id` first before falling back to payer email.
- **The Rule**: Never rely on external payment processor email addresses as primary identity keys. Always bind external subscriptions to internal user identifiers via `custom_id`.

---

## Incident 7: Admin Panel Shipped Fabricated Counts Requiring Four Removal Rounds

- **What Broke**: The admin dashboard displayed conflicting, invented numbers ("47/50 sources operational (7 Cloudflare protected, 12 dead links)" when the real operational count was 41/65, and 47+7+12=66≠50). It also contained static paragraphs stating "Showing sample data" and a fake "Run now" button that toasted success without calling the server.
- **How It Was Found**: The client logged into the dashboard, noticed the math did not add up, and found the "Showing sample data" notice at the bottom of the page.
- **Root Cause**: The admin panel was originally scaffolded from a frontend prototype with mock arrays, static placeholder copy, and simulated client-side timeouts. Reviewers looked for the word "mock" but missed hardcoded HTML strings and simulated `setTimeout()` handlers across four review cycles.
- **The Fix**: Purged all mock arrays, deleted simulated click handlers, wired metric chips to live API feeds (`/api/admin/metrics`), and added automated assertion tests scanning HTML files for sample data markers.
- **The Rule**: **Rule 3 & Rule 8**. Never ship placeholder strings, fake counters, or simulated actions. If a feature or data point is not available from the server, display "—" or do not render it.

---

## Incident 8: Account Page Shipped a Preview Renderer and Produced Nine Faked Screenshots

- **What Broke**: The customer account page (`frontend/account.html`) shipped with a `?preview_state=` parameter and a `renderPreviewState()` function that fabricated mock user emails, fake subscription IDs (`I-SUB-ACTIVE-PREVIEW`), and hardcoded prices (`$49.00 / month`). Nine delivery screenshots were generated through this mock path, creating the illusion that customer subscription controls worked while hiding that real subscribers would see raw PayPal plan IDs and unpopulated prices.
- **How It Was Found**: Code review of `frontend/account.html` and inspection of delivery screenshots.
- **Root Cause**: The screenshot script used `?preview_state=` rather than logging into the application and setting up real database state. The preview path returned early, so the real code path never executed in the visual test.
- **The Fix**: In Task Packet P2-1-FIX (commit `c3f4466`), deleted `renderPreviewState` entirely, removed hardcoded prices from markup, resolved human-readable plan names and prices from `PLAN_CATALOGUE` in `GET /api/account/subscription`, and rewrote `scripts/capture_account_screenshots.py` to seed real users in an isolated SQLite database and authenticate via genuine JWT tokens.
- **The Rule**: **Rule 3 & Rule 6**. Never build preview renderers that bypass real server responses. Screenshots must be generated from real sessions against a real backend. A mock screenshot is worse than no screenshot because it masquerades as verification.
