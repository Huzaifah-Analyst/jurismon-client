# Production & Review Failure Log

This document records the major defects that escaped to production or survived initial code review during Phase 1. It details why each failure occurred, how it was uncovered, what safeguards now prevent it, and what patterns engineers must look out for in future sessions.

---

## 1. SQLite / PostgreSQL Schema & Column Drift

### What happened
On three separate occasions during development, changes were made to the database access layer that functioned flawlessly in local unit tests but immediately crashed production upon deployment:
1. New customer authentication columns (`password_hash`, `is_verified`, `verification_code`, `trial_ends_at`, `subscription_status`, `paypal_subscription_id`) were added to the SQLite initialization method, but no matching PostgreSQL migration was written for Supabase (commits `e58817c`, `7950456`).
2. Type mismatch on `is_active` and `sources` columns, where SQLite flexibly treats `1`/`0` as truthy integers, but PostgreSQL strictly enforces boolean column constraints (`BOOLEAN NOT NULL DEFAULT TRUE`).
3. The `sources_skipped` column was added to `crawl_runs` in `_init_sqlite_schema()` ([db/repository.py:145](file:///d:/fiverr%20client/malok%20mading/db/repository.py)), but no PostgreSQL migration was created, causing the crawl recording query to fail on Supabase (commit `9df6dbc`).

### Why it happened
In [db/repository.py:51-175](file:///d:/fiverr%20client/malok%20mading/db/repository.py), the `_init_sqlite_schema()` method uses dynamic `CREATE TABLE IF NOT EXISTS` and `ALTER TABLE ADD COLUMN` statements. When developers added features locally, they added columns to SQLite. The local test suite ran exclusively against SQLite and reported 100% passing tests. PostgreSQL running on Supabase never received corresponding migrations in `db/migrations/*.sql`.

### How it was found
During live testing and deployment on the VPS: database queries threw `column "sources_skipped" does not exist` and HTTP 500 errors during crawl completion.

### What prevents it now
The schema parity test suite in [tests/test_schema_contract.py:TestSQLitePostgresSchemaParity](file:///d:/fiverr%20client/malok%20mading/tests/test_schema_contract.py) (introduced in commit `9df6dbc`). It introspects the SQLite tables initialized by `_init_sqlite_schema()` and scans every migration file in `db/migrations/`, asserting that every single SQLite column has an explicit, corresponding migration in PostgreSQL. The test suite fails if any column is added to SQLite without a matching migration.

### What to watch for
Never add a column or table to `_init_sqlite_schema()` without creating a numbered migration in `db/migrations/` in the same commit. Always run `pytest tests/test_schema_contract.py` before pushing.

---

## 2. Missing Supabase Branches in Repository Data Mutation Methods

### What happened
Methods responsible for writing user verification data — specifically `set_verification_code()` and `verify_user_email()` in [db/repository.py](file:///d:/fiverr%20client/malok%20mading/db/repository.py) — contained logic that executed only against the local SQLite database via `self._connect()` (commits `e58817c`, `74172a1`). There was no `if self.supabase:` branch implemented for these methods.

### Why it happened
The repository was originally authored with a dual-mode fallback architecture: write to Supabase if connected, otherwise write to SQLite. During rapid implementation of the authentication flow, the developer implemented only the SQLite query path. Because test fixtures intentionally mock or disconnect Supabase to avoid mutating production data, unit tests executed the SQLite path and passed completely.

### How it was found
During live end-to-end verification of customer registration on [https://jurismon.com](https://jurismon.com). Users entered their 6-digit confirmation code, but the server returned `Invalid verification code` because the verification code had been written to a local SQLite file on the VPS that the production Supabase queries never read.

### What prevents it now
Code review discipline and end-to-end integration tests in [tests/test_supabase_path.py](file:///d:/fiverr%20client/malok%20mading/tests/test_supabase_path.py), which explicitly test repository methods with a mock Supabase client to assert that both branches exist.

### What to watch for
Every data access method in `db/repository.py` must follow the dual-branch pattern:
```python
if self.supabase:
    # Remote PostgreSQL write via Supabase client
    return ...
# Local SQLite fallback write
with self._connect() as conn:
    ...
```

---

## 3. Empty Search Query Returning Zero Rows on PostgreSQL vs. All Rows on SQLite

### What happened
When a user opened the search interface with an empty search query (e.g., initial landing page load), SQLite returned all recent documents using `SELECT * FROM documents WHERE ... LIKE '%%'`. However, in production on PostgreSQL, the search returned zero documents, leaving the homepage completely blank for weeks despite 773 records existing in the database (commit `2bc5ae3`).

### Why it happened
In PostgreSQL, full-text search was executed using `plainto_tsquery('english', q)`. When `q` was empty (`""`), `plainto_tsquery('')` generated an empty `tsquery` that matches zero documents. SQLite's fallback query used `LIKE '%""%'`, which matches everything.

### How it was found
Discovered during visual review of the live production search page: searching for anything worked, but loading the homepage with default parameters presented a completely empty table.

### What prevents it now
In [db/repository.py:347-360](file:///d:/fiverr%20client/malok%20mading/db/repository.py), empty search strings are explicitly intercepted before constructing the tsquery: if `query` is empty or whitespace-only, the repository executes a standard timestamp-ordered select query rather than a full-text search vector query. Regression tests in `tests/test_api_and_db.py` verify that `GET /api/documents?q=` returns documents on both database engines.

### What to watch for
PostgreSQL tsquery functions (`to_tsquery`, `plainto_tsquery`, `websearch_to_tsquery`) have distinct parsing rules and fail or return empty on empty strings, punctuation-only inputs, or boolean operators.

---

## 4. Pushing to GitHub Without Executing VPS Deployment

### What happened
Five successive bug fixes and improvements were committed and pushed to the GitHub repository over multiple days, but none of the changes appeared on [https://jurismon.com](https://jurismon.com) (commit `caf1537`). The live production site continued running outdated code while the engineering team believed the issues were resolved.

### Why it happened
Assumed deployment automation: developers assumed that pushing to the `main` or tracking branch triggered automatic deployment to the VPS. In reality, the VPS had no continuous deployment runner or webhook listener configured.

### How it was found
The client inspected the live admin panel and reported that bugs previously declared "fixed" were still visible on the live domain. Checking `git log` on the VPS revealed that the production server was five commits behind origin.

### What prevents it now
The manual deployment runbook in [docs/HANDOVER.md:68-89](file:///d:/fiverr%20client/malok%20mading/docs/HANDOVER.md). Every production release requires SSH access to the VPS and running:
```bash
cd /opt/jurismon && bash scripts/deploy.sh
```
Followed by inspecting `curl -s https://jurismon.com/api/health` and reviewing live browser screenshots.

### What to watch for
`git push` updates the remote git repository; it never updates the running server. A task is not complete until deployed and verified on the live hostname.

---

## 5. Fabricated Admin Dashboard Data Surviving in Four Successive Rounds

### What happened
The administrative dashboard (`frontend/admin.html`) was initially built as a static frontend mockup containing hardcoded placeholder data. Replacing fake data with real API feeds took four separate, painful rounds of fixes because reviewers missed embedded mock data repeatedly:
1. **Round 1**: Hardcoded `PLACES` JavaScript array with fictional municipal names (e.g., "Timberline Township", "Clearwater City Council") (commit `42bf680`).
2. **Round 2**: Hardcoded summary string in the HTML: `"47/50 sources operational (7 Cloudflare protected, 12 dead links)"`. The actual numbers were 41/65, and 47+7+12 = 66 ≠ 50 (commit `42bf680`).
3. **Round 3**: A visible static paragraph directly above the footer: `<p class="foot">Showing sample data. Connect Supabase and PayPal to load live records.</p>` (commit `ca1efc4`).
4. **Round 4**: An individual source "Run now" button with a click handler that set the row status to "running", waited 1800ms with `setTimeout()`, and displayed a toast claiming `<jurisdiction> crawled successfully` without making any network request (commit `c7c01a0`).

### Why it happened
- Incomplete grep audits: Reviewers searched for specific keywords like `mock` or `fake` or specific place names. They missed strings written as static HTML paragraphs, inline numbers, and simulated UI animations.
- Verifying structure rather than data origin: Tests checked whether table rows rendered, but did not assert that the text content originated from the API response payload.

### How it was found
Discovered when the client logged into their live dashboard, noticed conflicting numbers (47 + 7 + 12 ≠ 50), and scrolled to the bottom to see "Showing sample data" on a production dashboard.

### What prevents it now
- Automated string assertion tests in [tests/test_api_and_db.py:test_pages_contain_no_sample_or_fictional_data_indicators](file:///d:/fiverr%20client/malok%20mading/tests/test_api_and_db.py) scanning all HTML files for sample data markers.
- Removal of simulated client-side handlers in commit `c7c01a0`.

### What to watch for
When inheriting or creating frontend templates, search comprehensively for hardcoded data, simulated timeouts, and static disclaimer copy. Never simulate an operational action on the client side.

---

## 6. `#auth-gate` Declared After the Closing `</script>` Tag

### What happened
When an administrator clicked "Log out" in the admin dashboard, the session was cleared, but the dashboard remained on screen with frozen loading spinners. The admin login modal gate never appeared, rendering the panel unusable (commit `e10c07b`).

### Why it happened
In [frontend/admin.html](file:///d:/fiverr%20client/malok%20mading/frontend/admin.html), the `<div id="auth-gate">` element was placed at line 2260, **after** the closing `</script>` tag at line 2256. At parse time, `document.getElementById('auth-gate')` executed when the script loaded, but the element did not yet exist in the DOM, returning `null`.
Because the JavaScript code defensively wrapped DOM manipulations in `if (authGate) { authGate.style.display = ... }`, the code silently skipped showing the modal without throwing any runtime JavaScript exceptions or console errors.

### How it was found
Found when testing the logout flow in a live browser. Reviewers had previously only tested the authenticated happy path (logging in with a pre-stored token in `localStorage`).

### What prevents it now
- Moving `#auth-gate` above the `<script>` block in `frontend/admin.html`.
- Automated regression test in `tests/test_api_and_db.py:test_admin_auth_gate_order` verifying that `#auth-gate` precedes `<script>` in the raw HTML file.

### What to watch for
- Defensive `if (element)` null-guards can hide fatal DOM structural defects. If an element is mandatory for page function, its absence should log an error or fail loudly.
- Always test every lifecycle state of a page: signed out, invalid credentials, token expired, loading, and signed in.

---

## 7. PayPal Webhook Missing `PAYMENT.SALE.COMPLETED` Event

### What happened
The PayPal webhook endpoint (`POST /api/payments/webhook`) initially handled `BILLING.SUBSCRIPTION.ACTIVATED` and `BILLING.SUBSCRIPTION.CANCELLED`, but did not handle `PAYMENT.SALE.COMPLETED` (commit `6a22bd1`).

### Why it happened
Initial testing used PayPal sandbox subscription creation, which triggers `BILLING.SUBSCRIPTION.ACTIVATED`. The developer assumed that this single event was sufficient for the entire subscription lifecycle. However, for recurring monthly or annual billing cycles, PayPal sends `PAYMENT.SALE.COMPLETED` upon each successful renewal charge.

### How it was found
Discovered during audit of PayPal IPN/Webhook lifecycle documentation prior to client delivery. Without handling sale completion, subsequent monthly renewals would not extend the subscription expiry or refresh active status.

### What prevents it now
[api/payments/paypal_provider.py:110-125](file:///d:/fiverr%20client/malok%20mading/api/payments/paypal_provider.py) explicitly processes `PAYMENT.SALE.COMPLETED` by extracting the subscription ID, resolving the user account via `custom_id` or payer email, and updating `subscription_status = 'active'`.

### What to watch for
Subscription webhook handlers must support the full state lifecycle: activation, recurring payment success, payment failure/denial, suspension, and cancellation.

---

## 8. SSH Password Authentication Active Due to Cloud-Init Drop-In Override

### What happened
During production server hardening on the Hostinger VPS, `scripts/vps_setup.sh` configured `/etc/ssh/sshd_config` with `PasswordAuthentication no`. Despite this, SSH password authentication remained active, leaving the server open to password brute-force attacks (commit `c22d4eb`).

### Why it happened
Ubuntu 22.04 cloud instances utilize a cloud-init drop-in configuration file located at `/etc/ssh/sshd_config.d/50-cloud-init.conf`, which sets `PasswordAuthentication yes`. Under OpenSSH's configuration parser rules, the first directive encountered takes precedence, and `Include /etc/ssh/sshd_config.d/*.conf` appears at the very beginning of `/etc/ssh/sshd_config`. The drop-in overrode the main configuration file.

### How it was found
Verified by attempting an SSH connection from a test client without specifying an SSH key; the server prompted for a password rather than rejecting the connection with `Permission denied (publickey)`.

### What prevents it now
Hardening scripts in `scripts/vps_setup.sh` explicitly remove or overwrite `/etc/ssh/sshd_config.d/50-cloud-init.conf` and create a high-priority drop-in `/etc/ssh/sshd_config.d/99-hardened.conf` setting `PasswordAuthentication no`.

### What to watch for
On modern Linux distributions, settings in `/etc/ssh/sshd_config` are frequently overridden by drop-ins in `/etc/ssh/sshd_config.d/`. Always inspect the active configuration with `sshd -T | grep passwordauthentication`.

---

## 9. Secret Credentials Committed to Repository History

### What happened
A sensitive API credential was included in two committed configuration files, exposing it in the git commit history across both the internal repository and the client's repository (commit `315e8c7`).

### Why it happened
During initial local environment bootstrap, credentials were saved in sample configuration files rather than being isolated exclusively in `.env`.

### How it was found
Automated credential pattern scanning and manual commit review prior to Phase 1 delivery.

### What prevents it now
- The compromised credential was immediately revoked and rotated at the external provider.
- Working trees were purged of the file, and `.gitignore` was updated to exclude all `.env*` files (except `.env.example`).
- Ground Rule R3 and Rule 9 of [06_WORKING_RULES.md](file:///d:/fiverr%20client/malok%20mading/docs/context/06_WORKING_RULES.md) strictly forbid hardcoding credentials.

### What to watch for
Never include real API keys, tokens, or passwords in repository files, commit messages, or chat transcripts. Use environment variables exclusively.

---

## The Recurring Architectural Patterns

Across all nine incidents, the same systemic patterns caused defects to survive review:

1. **SQLite hides what PostgreSQL enforces**:
   SQLite is lenient with dynamic schemas, untyped columns, and missing constraints. PostgreSQL is strict. A feature tested only on SQLite is unverified.
2. **A passing test suite is not evidence that production works**:
   If unit tests mock the production service (Supabase) or execute fallback branches, green test reports only prove that the fallback code executes.
3. **An API returning correct JSON is not evidence that the UI displays it**:
   Verifying that an endpoint returns `{status: "ok"}` does not guarantee the frontend DOM renders it, binds handlers correctly, or avoids hardcoded mock overlays.
4. **A null-guard turns a critical bug into silent failure**:
   Wrapping DOM references in `if (element)` suppresses errors in the browser console. If a UI component is mandatory, its absence must log an error.
5. **Verifying one state (logged in) proves nothing about another (logged out)**:
   Testing only the happy path misses initialization order bugs and broken unauthenticated states.
6. **Pushing is not deploying**:
   `git push` commits code to GitHub; it never updates running VPS services. Deployment requires executing `scripts/deploy.sh` on the server.
