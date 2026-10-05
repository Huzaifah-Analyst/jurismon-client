# JurisMon Agent Engineering Rules

> **Audience**: AI coding agents modifying this repository.  
> **Format**: Direct, non-negotiable operational instructions.

---

### RULE 1: Dual-Schema Parity
- Whenever you add a column or table to `_init_sqlite_schema()` in [`db/repository.py`](../../db/repository.py), you **MUST** create a matching numbered SQL migration in [`db/migrations/`](../../db/migrations/) in the same commit.
- Use the next sequential number. As of now, migrations exist from `001` through `007`. **The next migration file is `008_<name>.sql`**.
- PostgreSQL column types are strict (`BOOLEAN DEFAULT TRUE`, not `INTEGER 1`).
- **Enforcement**: Run `pytest tests/test_schema_contract.py`. If this test fails, you are not allowed to push.

---

### RULE 2: Dual-Branch Repository Implementation
- Every data access method in [`db/repository.py`](../../db/repository.py) that performs writes, updates, or deletes **MUST** implement both execution branches:
  ```python
  if self.supabase:
      # Production PostgreSQL branch via Supabase SDK
      return ...
  # Local SQLite fallback branch
  with self._connect() as conn:
      ...
  ```
- **Never implement a write solely for SQLite.** Local tests run against SQLite and will give you a false sense of success, while production (which uses Supabase) will silently fail to persist data.
- Verify both paths by running tests that test SQLite and tests that mock the Supabase client ([`tests/test_supabase_path.py`](../../tests/test_supabase_path.py)).

---

### RULE 3: Zero Fabricated Data in Any UI
- **Never place fabricated data in any frontend page or API endpoint.**
- Do NOT declare fake arrays (e.g. mock municipalities like "Timberline Township").
- Do NOT hardcode placeholder numbers or fake metrics (e.g. "47/50 sources operational").
- Do NOT build mock or preview renderers (`preview_state`, `renderPreviewState`, `I-SUB-ACTIVE-PREVIEW`).
- Do NOT write `||` fallbacks that substitute plausible fake values for missing data (e.g. `data.plan || "JurisMon Professional"` or `trial_days || "14"`).
- If server data is missing, display an em-dash (`"—"`), show a clear empty state, or hide the element entirely. Never invent data the server did not return.

---

### RULE 4: DOM Element Declaration Order
- In all HTML templates (`frontend/*.html`), **every element queried by `document.getElementById()` MUST be declared in markup ABOVE the `<script>` tag that queries it**.
- Scripts must be placed at the very bottom of the `<body>`, immediately before `</body>`.
- An element placed after a script will evaluate to `null` at script execution time and cause silent initialization failures.

---

### RULE 5: No Failure-Masking Null Guards
- **A null guard that hides a structural failure is worse than a hard crash.**
- Never write defensive guards like `if (authGate) { authGate.style.display = 'block'; }` on mandatory UI components. If `#auth-gate` is missing from the DOM, a silent guard suppresses the error, leaving the application frozen in a broken state without logging an error.
- If an element is essential for application lifecycle, throw a clear error or log a fatal console warning if it is not found.

---

### RULE 6: Evidence Requires Genuine Authentication & Server State
- A screenshot captured via a URL parameter (`?preview_state=active`) or client-side mock is **NOT evidence** that a feature works.
- Screenshots must be captured by Playwright logging into a genuine running backend server, obtaining a real JWT bearer token, and rendering genuine data retrieved from a database.
- For error states, force the API to genuinely return HTTP 500/503.
- If you cannot reach a state without faking it, state honestly in your report that you could not reach it. An honest negative report is valuable; a fabricated screenshot destroys trust.

---

### RULE 7: Absolute Secret & Credential Isolation
- **Never commit credentials.**
- Do not commit API keys, private tokens, passwords, database passwords, or JWT secrets in code files, git commit messages, log output, or markdown reports.
- Read all secrets from environment variables (`.env`).
- Never edit or commit `.env`. Use `.env.example` to document required variable keys.

---

### RULE 8: Preserve `config/sites.json` Byte-for-Byte
- [`config/sites.json`](../../config/sites.json) defines the active 65 municipal and statutory sources.
- **Do not touch, reformat, reorder, or modify `config/sites.json`** unless the user's task packet explicitly instructs you to modify sources.
- Even whitespace diffs in `config/sites.json` are rejected.

---

### RULE 9: Never Rewrite Git History
- Never run `git push --force`, `git push --force-with-lease`, `git rebase`, or `git reset --hard` on published remote branches.
- Fix defects by creating forward, cleanly described fix commits.

---

### RULE 10: Pushing Is Not Deploying
- `git push origin <branch>` updates the GitHub remote repository. **It does not touch the VPS.**
- The production server at `https://jurismon.com` does not run automatic push-to-deploy webhooks.
- Production deployment requires logging into the VPS over SSH and executing:
  ```bash
  cd /var/www/jurismon && bash scripts/deploy.sh
  ```
- Never declare a task "deployed" merely because you pushed commits to GitHub.

---

### RULE 11: Never Run Subscription Lifecycle Calls Against Live PayPal
- `.env` in production and testing may contain live PayPal API credentials (`PAYPAL_MODE=live`).
- **Never trigger `suspend`, `activate`, or `cancel` API calls against live PayPal IDs in automated test runs or screenshot capture scripts.**
- Tests must use mocked provider calls (`patch.object(main.paypal_provider, ...)`). Genuine API calls against PayPal can only be run when explicit PayPal Sandbox credentials are provided.
