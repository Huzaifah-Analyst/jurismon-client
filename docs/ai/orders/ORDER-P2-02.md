# ORDER P2-02 — Admin Plan Catalogue Management & Dynamic Pricing

> **From**: Lead engineer
> **To**: Implementing agent (Antigravity)
> **Repo**: `jurismon-client` · **Branch**: `claude/sweet-babbage-fz7sbz`
> **Read first**: `docs/ai/rules.md` (all 11 rules are binding), `docs/ai/architecture.md`, `docs/ai/memory.md`
> **Status gate**: P2-01 (`c3f4466`) is code-complete but **not deployed** (DEBT-05). Do not deploy anything. Code only.

---

## 1. Objective

Give the admin a working Plans tab that can change what JurisMon sells — plan name, display price, PayPal plan id, active/inactive, and trial length — and have the change take effect on the running server **without a restart**, without ever letting the displayed price drift from what PayPal actually charges.

---

## 2. Current state (verified by scan, do not re-derive)

| Fact | Location |
| :--- | :--- |
| Catalogue is read once at module import | `api/main.py:92` — `PLAN_CATALOGUE = _load_plan_catalogue()` |
| Loader reads `config/plans.json`, returns a safe empty catalogue on failure | `api/main.py:77-89` |
| 14 read sites depend on the global | `api/main.py:431,432,440,458,1068,1073,1454,1478,1487,1517,1533,1534` |
| Public catalogue endpoint exists | `api/main.py:427` `GET /api/plans` |
| **Nothing consumes `/api/plans`** — no frontend fetch anywhere | `grep "api/plans" frontend/*.html` → no hits |
| Public prices are hardcoded in three places | `frontend/index.html:45-46` (JSON-LD `"price": "49.00"`), `:1176` (`$49`/mo), `:1192` (`$468`/yr) |
| Admin read endpoint exists, no write endpoint | `api/main.py:1511` `GET /api/admin/plans` |
| Admin Plans tab renders from a client array, read-only | `frontend/admin.html:1129` (`const PLANS = []`), `:1785-1810`, panel at `:968` |
| Admin auth guard to reuse | `api/auth.py:120` `require_admin` |
| Existing plan tests | `tests/test_admin_dashboard.py:75,84,95,107,316,323` |
| Current catalogue | 2 plans: `professional_monthly` $49/mo, `professional_annual` $468/yr, `trial_days: 14`, USD |

---

## 3. The trap that defines this task — read twice

`price` in `config/plans.json` is **display copy only**. The amount actually billed lives in the PayPal plan identified by `paypal_plan_id`. Editing `price` to 59.0 does not charge anyone $59 — it puts a false number on the pricing page and in the JSON-LD that Google indexes, while PayPal keeps taking $49. That is a refund-grade defect and a false-advertising exposure.

**Therefore the write path is not a free-text price editor.** Implement it as follows:

- A price edit is accepted **only** when the submitted price matches the live PayPal plan's billing amount, verified server-side against PayPal before the file is written.
- To actually change what customers pay, the admin must point the catalogue entry at a **new** PayPal plan id (PayPal plans are effectively immutable for existing subscribers). Existing subscribers stay on their old `paypal_plan_id` and are grandfathered — their row in `subscriptions.plan_id` must not be rewritten.
- `api/main.py:1454` and `:1487` resolve subscriber plan metadata by `paypal_plan_id`. Retired plan entries must stay resolvable (keep them in the file with `is_active: false`) or every grandfathered subscriber's plan name turns into `null` in the admin table and on their account page.

---

## 4. Required work

### 4.1 Kill the import-time cache (DEBT-01)

- Replace the `PLAN_CATALOGUE` module global with `get_plan_catalogue()` returning a cached dict plus an explicit invalidation path. Cache on `config/plans.json` mtime, or hold the dict behind a module-level accessor that the write endpoint refreshes.
- Update **all 14 read sites** listed in §2. Leave no reference to the old global.
- Return a defensive copy — callers must not be able to mutate the cache in place.

### 4.2 PayPal price verification helper

- In `api/payments/paypal_provider.py`, add a method to fetch a plan by id from PayPal (`GET /v1/billing/plans/{id}`) and return its billing amount, currency and interval.
- Mirror the existing provider's token/auth and error handling — do not introduce a second HTTP client.
- When PayPal credentials are absent (`paypal_provider.client_id` falsy), verification is **unavailable**, not **passed**: reject the write with `503`, the same way `api/main.py:466` already does. Never silently accept an unverified price.

### 4.3 Admin write endpoints

`PUT /api/admin/plans/{plan_id}` — guarded by `require_admin`:

- Accepts `name`, `price`, `paypal_plan_id`, `is_active`. Pydantic model, all fields optional, at least one required.
- Validates: price > 0 and ≤ 100000; `paypal_plan_id` matches `^P-[A-Z0-9]{20,30}$`; name 1-80 chars; `paypal_plan_id` unique across the catalogue (the test at `tests/test_admin_dashboard.py:323` already asserts uniqueness — keep it green).
- Verifies the resulting `(price, interval)` against PayPal per §4.2 before writing. Mismatch → `409` with both numbers in the detail message.
- Refuses to deactivate the last active plan (`409`) — an empty catalogue breaks `POST /api/subscriptions/create` at `api/main.py:457`.

`PATCH /api/admin/plans` — `trial_days` (0-90) and `currency` (ISO-4217, 3 letters) only.

Both:

- Write atomically: serialize to a `.tmp` file in the same directory, then `os.replace()` onto the target. A half-written catalogue takes down checkout.
- Preserve key order and the field set of every untouched plan — the file is hand-maintained and reviewed in diffs.
- Invalidate the cache immediately after a successful write and return the full new catalogue, so the UI re-renders from the server's truth rather than from optimistic local state.
- Log the change at INFO with old value, new value, and the admin token subject.

### 4.4 Admin UI — `frontend/admin.html`

- Make each `.plan` card in the Plans tab editable: inline edit for name and price, a PayPal plan id field, an active toggle, plus Save and Cancel. Keep the existing `.plan` / `.plan-top` / `.plan-price` classes and the token set (`--surface`, `--line`, `--ink`, `--muted`) — this must look native to the page, not bolted on.
- Add a `trial_days` / `currency` control for the catalogue-level `PATCH`.
- Reuse the page's existing toast and auth-failure patterns (see the auth-required placeholders at `:1779` and `:2052`). On `409`, surface PayPal's number against the submitted one in the toast — the admin needs to see *why*.
- Re-render from the endpoint response. Do not mutate `PLANS` optimistically and do not reload the page.
- **Rule 4 is binding**: no element referenced before it exists in DOM order, and no `if (!el) return` guards added to paper over ordering — fix the order instead.
- **Rule 3 is binding**: no placeholder, sample, or fabricated plan rows. If the fetch fails, the card area says so plainly.

### 4.5 Wire the public page to the catalogue

The whole point of admin pricing control is that the public page changes. It currently cannot.

- Fetch `GET /api/plans` on `frontend/index.html` load and render the two pricing cards at `:1176` and `:1192` from the response.
- Keep the current hardcoded markup as the pre-fetch/failure state so the page never shows an empty or `$—` card.
- Update the JSON-LD `price` at `:45-46` from the same response (rewrite the `application/ld+json` block's text content after fetch).
- Same treatment for `active-plan-price` on `frontend/account.html:465` **only if** it is not already resolving dynamically — P2-01 added dynamic plan resolution, so check first and do not duplicate it.

### 4.6 Tests

Extend `tests/test_admin_dashboard.py` (all 269 existing tests must stay green):

- Write endpoint requires admin (401/403 unauthenticated; 403 with a customer token).
- Successful name edit; successful price edit when PayPal agrees.
- `409` when the submitted price disagrees with PayPal.
- `503` when PayPal credentials are unset.
- `409` on deactivating the last active plan.
- `409` on a duplicate `paypal_plan_id`.
- **Cache invalidation**: write a new price, then `GET /api/plans` **in the same process** returns the new value. This is the DEBT-01 regression test and the most important one in the set.
- A grandfathered subscriber on a now-inactive plan still resolves a plan name in `GET /api/admin/subscribers`.
- Atomic write leaves no `.tmp` file behind, on success or on forced failure.
- Mock PayPal — no live API calls in the suite. Restore `config/plans.json` in teardown; a test must never leave the real catalogue mutated.

---

## 5. Out of scope — do not touch

- No deployment. No SSH. No `scripts/deploy.sh`. The VPS stays on `c7c01a0`.
- No new migration. This task writes JSON, not SQL. (If you believe you need one, stop and ask — next free number is `008`.)
- No changes to `config/sites.json`, the crawler, the diff engine, or the extractor.
- No creating or modifying live PayPal plans. `scripts/create_paypal_plan.py` is the admin's manual tool; do not call it from the API.
- No rewriting of `subscriptions.plan_id` for existing rows.
- No push to the `client` remote (`curtiskelton88/jurismon`). `origin` only.
- No new runtime dependency.
- Do not touch the jurisdiction count copy — `45f139d` just settled it ("N live jurisdictions, M tracked").

---

## 6. Acceptance criteria

1. `./venv/Scripts/python.exe -m pytest -q` → 269 + new tests, all passing, zero skips added.
2. `grep -n "PLAN_CATALOGUE" api/` returns nothing outside the accessor's own definition.
3. Editing a price through the admin UI changes the public pricing card and the JSON-LD **without restarting Uvicorn**.
4. A price that disagrees with PayPal is refused, and the admin sees both numbers.
5. `git diff --stat` touches only: `api/main.py`, `api/payments/paypal_provider.py`, `frontend/admin.html`, `frontend/index.html`, `tests/test_admin_dashboard.py`, plus `docs/ai/tasks.md` and `docs/ai/memory.md` (board and record update).
6. Commit on `claude/sweet-babbage-fz7sbz`, Conventional Commits, body stating what was verified and what was not.

---

## 7. Report back

- Commit SHA and `git diff --stat`.
- Pytest tail (pass count).
- The exact PayPal endpoint and response field used for price verification.
- Any contradiction found between this order and the code — quote `file:line`. This scan is current as of `45f139d`; if something has moved, say so rather than working around it.
