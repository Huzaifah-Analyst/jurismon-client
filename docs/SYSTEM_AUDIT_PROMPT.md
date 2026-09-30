# JurisMon — Deep System Audit Prompt

**Purpose:** find remaining instances of the bug classes this project has already
proven to contain. Every class below was found here, in this codebase, during
development. Where one instance existed, others usually do.

**How to use:** work through each section in order. For each, run the searches,
then *read the surrounding code* — grep alone will not settle any of these.
Record findings as `SEVERITY | file:line | what breaks | how to reproduce`.

**Do not fix anything while auditing.** Produce the finding list first, ranked.
Fixing mid-audit loses the thread and hides patterns.

---

## Ground rules

1. **A passing test proves nothing on its own.** For every behaviour claimed to
   be tested, break the code deliberately and confirm a test fails. If none
   does, the test is decorative. This project shipped a test that passed with
   the feature entirely removed.

2. **Trust the running system over the test suite.** Several bugs here were
   invisible to tests and obvious within thirty seconds of looking at the live
   page or the production database.

3. **Silence is the main enemy.** Nearly every bug found so far was swallowed by
   a broad `except` or a fallback, and surfaced as "no results" or "zero" rather
   than an error.

---

## Class 1 — Exceptions swallowed into a fallback

**Proven here:** `verify_webhook` called `requests.json.loads`, which does not
exist. `AttributeError` → caught → `return False` → every live PayPal webhook
rejected. Also: `.text_search().limit()` raised `AttributeError` → caught →
fell through to an empty SQLite file → search returned nothing in production
while the database held 773 matching rows.

**Search:**
```bash
grep -rn "except Exception" --include="*.py" . | grep -v venv
grep -rn -A3 "except" --include="*.py" . | grep -v venv | grep -B1 "return \(False\|None\|\[\]\|{}\)"
```

**For each hit, answer:**
- If this block runs, does the caller learn anything went wrong, or does it see
  a normal-looking empty result?
- Is the fallback a *different data source* (Supabase → SQLite)? If so, writes
  may be silently landing somewhere else. That is the worst case here.
- Does the log line name the operation and the cause, or just say "error"?

**Specifically re-examine:** every `if self.supabase:` branch in
`db/repository.py`. Each one falls through to SQLite on any exception. Confirm
each Supabase call chain against the installed postgrest-py, not against
assumption.

---

## Class 2 — Configuration read but never applied

**Proven here:** `mode: str = "sandbox"` then `self.mode = mode or os.getenv("PAYPAL_MODE")` — the truthy default meant the env var could never win, so live
mode was unreachable. `params` was read from `selectors_config` and never passed
to `fetch_page`. `DATABASE_URL` was read into a module variable and never used.

**Search:**
```bash
grep -rn "os.getenv\|os.environ" --include="*.py" . | grep -v venv
```

**For each variable found, verify it is actually consumed:**
```bash
# for each NAME above
grep -rn "NAME" --include="*.py" --include="*.html" . | grep -v venv
```

**Then check every function signature with a non-None default that is later
combined with `or`:**
```bash
grep -rn -E "def .*=[\"'][^\"']+[\"']" --include="*.py" . | grep -v venv
```
A default of `""`/`None` is fine. A truthy default followed by `x or fallback`
is the bug.

**Also check the reverse:** variables documented in `.env.example` that no code
reads, and variables the code reads that `.env.example` never mentions. Both
have occurred here.

---

## Class 3 — Security defaults that fail open

**Proven here:** `verify_webhook` returned `True` when no webhook id was set.
`SECRET_KEY` had a hardcoded fallback. Admin login compared plaintext against a
default of `admin123`.

**Search:**
```bash
grep -rn -iE "getenv\(.*,\s*[\"'][^\"']+[\"']\)" --include="*.py" . | grep -v venv
grep -rn -iE "return True|= True" --include="*.py" api/ crawler/ db/ | grep -iB2 -A2 "verif\|auth\|token\|secret\|admin\|permission"
```

**For each authentication, verification or authorisation path, ask:**
- What happens when the required configuration is absent — does it deny, or
  allow? It must deny.
- Is there any default credential, key or token anywhere in the tree?
- Does the production guard actually run? Start the app with `APP_ENV=production`
  and each required variable blanked in turn; it must refuse to boot each time.

---

## Class 4 — Dead code, and dead code that is also broken

**Proven here:** `verify_password` / `get_password_hash` were never called — and
were broken anyway, because passlib 1.7.4 cannot run against bcrypt 5.x. Wiring
them up without testing would have shipped a login that returned 500.

**Search:**
```bash
# every def, then confirm each is called somewhere
grep -rn "^def \|^    def " --include="*.py" api/ crawler/ db/ diff_engine/ extractor/ notifications/
```

**For each function with no caller:** decide delete or wire up. If wiring up,
**execute it once** before trusting it. Never assume an uncalled function works.

---

## Class 5 — Library version reality

**Proven here:** passlib vs bcrypt 5.x. Also `requirements.txt` had 24 version
mismatches against what was installed, five packages listed that were not
installed at all, and three installed packages nothing imported.

**Checks:**
```bash
pip list --outdated
python -m pip check
```
- Cross-check every import in the tree against `requirements.txt`, both
  directions.
- For every third-party call chain in the code, confirm it against the
  *installed* version's API. The Supabase builder-order bug was exactly this.
- Confirm a clean virtualenv built only from `requirements.txt` passes the suite
  on the Python version the **server** runs (3.14), not only the dev machine.

---

## Class 6 — Schema and code disagreeing

**Proven here:** `sources.id` was declared `UUID` while the catalogue identifies
sources by slug, so every upsert against real Postgres would have been rejected.
`health_status` and `status_detail` were displayed by the dashboard but absent
from both schemas.

**Checks:**
- For every column named in a PostgREST `select(...)` string, confirm it exists
  in `db/migrations/`. These strings are not type-checked and fail at runtime.
- For every field the frontend reads from an API response, confirm the API
  actually returns it.
- Compare the SQLite schema in `db/repository.py` against the Postgres
  migrations, column by column. They have drifted before.
- Run the migrations against a scratch Postgres and diff the result against what
  the code expects.

---

## Class 7 — Seeding and first-run gaps

**Proven here:** SQLite self-seeds from `config/sites.json`; Supabase did not, so
production started with an empty `sources` table. The seeder also omitted
`health_status`, so every source took the column default and the dashboard read
65/65 operational.

**Checks:**
- For each table, ask: on a brand-new deployment, who populates this? If the
  answer is "nobody", that is a finding.
- For each seeding path, confirm it writes **every** column the application
  later reads — not just the ones it happened to need at the time.
- Deploy to a scratch database from zero and confirm the app is usable without
  manual SQL.

---

## Class 8 — Frontend showing invented data

**Proven here:** the admin dashboard rendered twelve fabricated subscribers,
three fake plans with invented PayPal ids, and eight fictional webhook
deliveries — and computed monthly revenue from them. The public page hardcoded
"32 / 51" and falls back to `DEFAULT_DATA` when the API returns nothing, so it
still displays invented statutory amendments on an empty database.

**Search:**
```bash
grep -rn -E "DEFAULT_DATA|SAMPLE|MOCK|DEMO|dummy|placeholder|example\.com|\.example\b" frontend/
grep -rn -E "= \[$|= \{$" frontend/*.html | head -50
```

**For each literal dataset in the frontend, ask:**
- Can a user ever see this? On an empty database? On an API error?
- **This is a legal-monitoring product.** Displaying a fabricated statutory
  amendment is materially worse than displaying nothing. Any fallback that
  invents legal content should be replaced with an honest empty state.

**Decide explicitly** whether `DEFAULT_DATA` in `frontend/index.html` should
exist at all. Current behaviour: an empty search result silently shows demo
amendments as though they were real.

---

## Class 9 — Frontend/API contract drift

**Proven here:** the login gate stored its token under `jurismon_admin_token`
while the data fetches read `admin_token`, so every authenticated request
returned 401. The search endpoint returns both `results` and `items`; the page
reads only `items` and falls back to demo data when it is empty. The frontend
compared health against `healthy|degraded|failing` while the API sends
`operational|cloudflare_blocked|dead_link|unreachable|blocked_403|auth_required`,
so every count rendered zero.

**Checks:**
- Enumerate every `fetch()` in `frontend/`, and for each, compare the exact keys
  read against the endpoint's actual response.
- Enumerate every `localStorage` key written and read; confirm they match.
- For every value the frontend switches on (status, health, type), list the
  values the API can actually produce and confirm each is handled — including
  ones added later.
- Open every page with the browser console visible and confirm zero errors.
  **Use a fresh tab**; the console accumulates across navigations and stale
  errors have already caused confusion here.

---

## Class 10 — JavaScript that does not parse

**Proven here:** `frontend/index.html` contained a `catch` with no `try`. The
entire script block failed to parse, so *none* of the page's JavaScript ran —
the search box rendered but was never wired up. This survived undetected because
nothing checks frontend syntax.

**Check every HTML file:**
```bash
python - <<'PY'
import re, pathlib, subprocess, tempfile, os
for f in pathlib.Path('frontend').glob('*.html'):
    for i, b in enumerate(re.findall(r'<script[^>]*>(.*?)</script>', f.read_text(encoding='utf-8'), re.DOTALL)):
        if not b.strip(): continue
        t = tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8')
        t.write(b); t.close()
        r = subprocess.run(['node','--check',t.name], capture_output=True, text=True)
        print(f"{f.name} block {i}: {'OK' if r.returncode==0 else r.stderr.splitlines()[:3]}")
        os.unlink(t.name)
PY
```

**Then confirm each function that boot calls actually exists** — a call to a
function whose definition was lost is a silent no-op at best.

---

## Class 11 — UI that reports success it did not achieve

**Proven here:** the admin "Cancel" button set `status = "cancelled"` in
JavaScript and showed a success toast, without ever contacting PayPal. The
operator would believe a subscription was cancelled while the customer kept
being billed.

**Checks:**
- For every button that claims to change remote state, confirm it calls the API
  and only updates the view **after** a success response.
- For every optimistic update, confirm there is a rollback on failure.
- List every toast/success message and confirm each is only reachable on an
  actual success.

---

## Class 12 — Permissive test doubles

**Proven here:** the Supabase fake was a `MagicMock` that accepted any chained
call, so `.text_search().limit()` passed the suite and failed in production. The
fake now mirrors the real builder and rejects it.

**Checks:**
- For every `MagicMock` or hand-written fake, ask: what does the real object
  *refuse* to do? Does the fake refuse it too?
- Any fake standing in for an external API should reject at least one call the
  real API rejects, and there should be a test proving it.
- Prefer recorded real responses over invented ones for response shapes.

---

## Class 13 — Tests reaching real systems

**Proven here:** once production Supabase credentials were in `.env`,
`Repository()` picked them up regardless of the `db_path` the test passed, and
the suite wrote a `test-austin` row into the live database.

**Checks:**
- Run the full suite with production credentials present and confirm nothing is
  written anywhere real: check row counts before and after.
- Audit every object that resolves configuration from the environment at
  construction time; each is a candidate for the same problem.
- Confirm `tests/conftest.py` covers every such path, not only Supabase.

---

## Class 14 — Cross-platform and deployment mechanics

**Proven here:** shell scripts written on Windows carried CRLF; on Linux bash
failed at `set -euo pipefail` with `$'\r': command not found` and the script ran
half-parsed. `.gitattributes` fixes files that travel via git, but `scp` bypasses
it entirely.

**Checks:**
```bash
grep -rlI $'\r' --exclude-dir=venv --exclude-dir=.git . | head -20
```
- Every `.sh` must be LF before it reaches the server, however it gets there.
- Confirm `.gitattributes` covers every executable text type.
- Re-run `vps_setup.sh` and `deploy.sh` on a scratch server and confirm both are
  genuinely idempotent — they are documented as such.

---

## Class 15 — Resource handling

**Proven here:** `with sqlite3.connect(...)` manages the transaction, not the
connection. Eleven call sites leaked file handles; on Windows this also left
undeletable test databases behind.

**Search:**
```bash
grep -rn "open(\|connect(\|Session()\|requests.get\|requests.post" --include="*.py" . | grep -v venv | grep -v "with "
```
- Every connection, file and session: confirm it is closed on both the success
  and the failure path.
- Confirm the long-running crawl does not accumulate handles: run it and watch
  `ls /proc/<pid>/fd | wc -l` over time.

---

## Class 16 — Secrets

**Proven here:** the VPS root password sat in `docs/CHAT_LOG.md`; a Resend API
key was saved to `docs/` where `.gitignore` did not cover it. Neither was ever
committed, but both were one `git add -A` away.

**Checks:**
```bash
grep -rniE "password|secret|api[_-]?key|token|BEGIN .*PRIVATE KEY" \
  --exclude-dir=venv --exclude-dir=.git --exclude-dir=credentials . | grep -v "\.example"
git log --all -p | grep -inE "password|secret|api[_-]?key" | head -40
```
- Confirm `.gitignore` covers every place a credential could plausibly land, not
  only the places one has landed so far.
- Confirm no credential appears in any committed file or in git history.
- Confirm no credential is logged: grep the logging calls, not only the code.

---

## Class 17 — Operational blind spots

**Checks not yet done on this system:**
- `crawl_runs` is empty after a full crawl — the crawler never records a run.
  Nothing tracks whether the daily job ran at all.
- Confirm the GitHub Actions workflow actually succeeds end to end, not merely
  that it is configured.
- Confirm the crawl failure email genuinely sends — the Resend sending domain's
  verification status has not been confirmed, and the key is send-only so it
  cannot be queried.
- Confirm certificate auto-renewal works: `certbot renew --dry-run`.
- Confirm the service survives a reboot: `systemctl is-enabled jurismon`, then
  actually reboot.
- Confirm log rotation exists for `/var/log/jurismon/` — currently it does not,
  and `api.log` grows without bound.

---

## Deliverable

A ranked list. For each finding:

```
SEVERITY  BLOCKER | HIGH | MEDIUM | LOW
WHERE     file:line
WHAT      one sentence: what is wrong
BREAKS    concrete failure: given this input or state, this happens
PROOF     the command, request or steps that demonstrate it
```

Rank by *what it costs when it happens*, not by how hard it is to fix. On this
project the expensive failures have all been silent ones: money not taken,
searches returning nothing, a cancellation that never reached PayPal.

End with an explicit statement of **what was checked and found clean**, so the
absence of a finding is distinguishable from the absence of a look.
