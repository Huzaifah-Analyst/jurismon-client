# Development & Engineering Working Rules

These 10 non-negotiable rules were established through hard-learned production failures and code review blocks during Phase 1. Any engineer working on JurisMon must follow them strictly.

---

## Rule 1: Dual-Schema Parity Discipline
> **Any column added to the SQLite schema requires a matching PostgreSQL migration in the same commit.**

- In [db/repository.py:51-175](../../db/repository.py#L51-L175), the `_init_sqlite_schema()` method creates SQLite tables for local offline execution.
- Production runs PostgreSQL hosted on Supabase. SQLite will happily create columns on the fly, but PostgreSQL will immediately crash with syntax/column errors if a column is missing.
- Whenever a column or table is added to `_init_sqlite_schema()`, you must create a corresponding numbered migration file in `db/migrations/` (e.g., `007_new_feature.sql`).
- **Enforcement**: Run `pytest tests/test_schema_contract.py`. If a column exists in SQLite without a matching migration, the test fails.

---

## Rule 2: Dual-Branch Repository Implementation
> **Repository methods that mutate data must implement BOTH a Supabase branch and a SQLite branch.**

- JurisMon uses a hybrid architecture: Supabase in production and SQLite in tests/offline mode.
- Writing data mutation logic (inserts, updates, deletes) only for SQLite means that local tests pass, but production silently fails to persist data (as happened with email verification codes).
- When adding or modifying a data access method in `db/repository.py`, always implement:
  ```python
  if self.supabase:
      # Production PostgreSQL path via Supabase SDK
      return ...
  # Local SQLite path
  with self._connect() as conn:
      ...
  ```
- Verify both paths by writing tests that exercise both the SQLite fallback and the mocked Supabase client.

---

## Rule 3: Visual Verification via Screenshots Over API Probes
> **UI changes must be verified by inspecting a rendered screenshot of the live browser page, not merely calling the API.**

- An endpoint returning HTTP 200 with valid JSON proves only that the backend works. It does not prove that:
  - The frontend JavaScript binds event listeners correctly.
  - CSS layout renders properly across viewports (e.g., 1440px desktop vs. 375px mobile).
  - Hardcoded placeholder strings or mock datasets are absent from the DOM.
- Use Playwright headless or browser automation to capture screenshots of the rendered page, inspect them, and confirm visual fidelity before declaring frontend work complete.

---

## Rule 4: Multi-State Lifecycle Verification
> **Verify every state a page can be in: signed out, loading, loaded, error, and expired session.**

- Verifying only the authenticated "happy path" was the exact root cause of the admin login gate failure, where logout froze the interface because the unauthenticated modal was never rendered.
- When touching any page or view, you must verify all five states:
  1. **Signed Out**: Does the login/gate prompt render cleanly without console errors?
  2. **Loading**: Are spinner or skeleton states displayed only while an active request is in flight?
  3. **Loaded**: Does data render accurately without sample text or hardcoded values?
  4. **Error / Degraded**: Does the UI display an actionable, friendly error message if the server returns 500 or 503?
  5. **Expired Session**: Does an expired JWT token trigger a redirect or prompt the user to re-authenticate cleanly?

---

## Rule 5: Pushing to GitHub Does Not Deploy
> **`git push` updates the repository remote; it never updates the production server. Deployment requires running `scripts/deploy.sh` on the VPS.**

- The production environment has no automated push-to-deploy runner.
- Every release must be deployed by logging into the VPS and executing:
  ```bash
  cd /opt/jurismon && bash scripts/deploy.sh
  ```
- This script pulls the latest commit, installs dependencies, applies database migrations, restarts systemd services, and executes a health check probe.
- Refer to [docs/client/handover.md:68-89](../client/handover.md#L68-L89) for full deployment instructions.

---

## Rule 6: Never Display Server Values That Do Not Exist
> **Never invent timestamps, mock counts, or placeholder status strings. If data is unavailable, state that explicitly on screen.**

- Do not provide fallback timestamps (e.g., fake relative times like "Just now" or "2 hours ago") when a crawl has never executed.
- Do not hardcode source health metrics (e.g., "47/50 sources operational"). All metrics must be computed dynamically from live database records.
- If an API returns null or empty for a field, display a clear empty state (e.g., "No runs recorded" or "Data unavailable"), never fabricated placeholder copy.

---

## Rule 7: Never Show Loading States When No Request Is in Flight
> **A loading spinner or "Loading..." status text must only appear while an asynchronous HTTP request is actively pending.**

- Leaving permanent "Loading portal status…" or "Checking sources…" text when an unauthenticated user arrives on a page is broken UI.
- If user authentication is missing or an error prevents a request from being dispatched, immediately transition the UI out of the loading state and display the appropriate login gate or error banner.

---

## Rule 8: Never Confirm Actions That Did Not Occur
> **Never display a success toast, confirmation dialog, or notification for an operation that did not execute.**

- The simulated per-source "Run now" button in the admin panel displayed `<jurisdiction> crawled successfully` via a client-side `setTimeout()` without making any server request. This breached client trust and violated engineering integrity.
- Feedback to the user must strictly reflect actual server-confirmed outcomes. If an endpoint is not yet built, do not render a button that pretends it is.

---

## Rule 9: Absolute Secret Isolation
> **Credentials, private keys, password hashes, webhook secrets, and production server IPs must NEVER appear in code, command lines, git commits, or chat logs.**

- Read all sensitive credentials exclusively from environment variables (e.g., `$ADMIN_PASSWORD_HASH`, `$SUPABASE_KEY`, `$PAYPAL_CLIENT_SECRET`).
- Never run commands with plaintext secrets passed as arguments.
- Never commit `.env` or configuration files containing real keys. Maintain `.env.example` with sanitized placeholder keys only.
- In documentation and logs, reference the production hostname `jurismon.com` rather than raw server IP addresses.

---

## Rule 10: Two-Stage Repository Delivery Discipline
> **All development and fixes must be committed and pushed to `Huzaifah-Analyst/jurismon-client` (origin) first. Only approved, verified, and client-facing commits may ever be pushed to the client repository.**

- **`origin` (`Huzaifah-Analyst/jurismon-client`)**: Working repository where branches, feature development, internal documentation, test fixes, and engineering context reside.
- **`client` (`curtiskelton88/jurismon`)**: Upstream client repository representing pristine, client-facing deliverables only.
- Internal documentation (such as `docs/context/`), exploratory debug scripts, and intermediate fix branches must **never** be pushed to the client remote without explicit instruction.
