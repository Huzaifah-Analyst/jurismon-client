# ORDER P2-15 — Create PayPal Plans From the Admin Panel

> **From**: Lead engineer
> **To**: Implementing agent (Antigravity)
> **Repo**: `jurismon-client` · **Branch**: `claude/sweet-babbage-fz7sbz`
> **Read first**: `docs/ai/rules.md` — **Rule 11 is the whole shape of this task, read it before anything else**
> **Type**: Backend + admin UI against a live payment provider. No deployment.

---

## 1. Why

Phase 2 Part 2 was sold to the client with this bullet:

> *"You set subscription pricing yourself from the admin panel — no code, no developer needed"*

Half of that is true. `c1f9ea2` lets the admin edit the catalogue, and the price is verified against PayPal so the page can never advertise a number PayPal is not charging. But PayPal does not allow a plan's price to be edited once it exists. Changing what new subscribers actually pay means **creating a new PayPal plan**, and today the only way to do that is:

```
python scripts/create_paypal_plan.py --price 59 --interval MONTH --confirm
```

That is a terminal, a Python environment and a developer. The bullet says there is none. Close that gap.

---

## 2. Current state (scanned, do not re-derive)

| Fact | Location |
| :--- | :--- |
| Existing CLI tool, with a `--confirm` safety gate | `scripts/create_paypal_plan.py` |
| Its dry-run philosophy: print the plan, create only on `--confirm` | `scripts/create_paypal_plan.py:1-14` |
| Provider methods already present | `api/payments/paypal_provider.py:135` `create_subscription`, `:199` `get_subscription`, `:222` `cancel_subscription`, `:238` `suspend_subscription`, `:254` `activate_subscription`, `:270` `get_plan_details` |
| **No plan-creation method on the provider** | the script talks to PayPal directly |
| Token helper to reuse | `api/payments/paypal_provider.py:39` `_get_access_token` |
| Plan write endpoint | `api/main.py:1628` `PUT /api/admin/plans/{plan_id}` |
| Admin guard | `api/auth.py:120` `require_admin` |
| Admin Plans tab | `frontend/admin.html:968` |
| Current catalogue | `professional_monthly` $49/mo, `professional_annual` $468/yr |
| Production | `b0d8bd4` |

---

## 3. Rule 11 — read this before writing any code

`docs/ai/rules.md` Rule 11: **never run subscription lifecycle calls against live PayPal.** This task creates real, permanent objects in the client's real PayPal account. A PayPal plan cannot be deleted — only deactivated — so a careless test run leaves permanent junk in the client's billing account, visible to them and to their accountant.

Therefore:

- **Every test mocks PayPal. No test, at any point, touches the live API.** Not once, not "just to check the shape of the response".
- The endpoint is **two-step and explicitly confirmed**, mirroring the `--confirm` gate the existing script already has. Step one returns a preview of exactly what would be created and creates nothing. Step two creates it, and only when the request carries an explicit confirmation flag.
- During development you do not call live PayPal to see what comes back. Read `scripts/create_paypal_plan.py` for the request and response shapes — it is already written and already correct.
- If you believe you need one live call to proceed, **stop and ask**. Do not decide that yourself.

---

## 4. Required work

### 4.1 Provider method

`create_plan(...)` in `api/payments/paypal_provider.py`, returning the new plan id.

- Reuse `_get_access_token` and the module's existing error handling. Do not introduce a second HTTP client or a second auth path.
- Port the product/plan request bodies from `scripts/create_paypal_plan.py` rather than reinventing them. That script was written against the live API and works.
- When credentials are absent (`client_id` falsy), raise the unavailable path — never a silent success.

### 4.2 Two-step admin endpoints

`POST /api/admin/plans/paypal/preview` — `require_admin`:
- Takes name, price, interval, currency, trial days.
- Returns exactly what would be sent to PayPal. **Creates nothing.**

`POST /api/admin/plans/paypal/create` — `require_admin`:
- Same body plus `confirm: true`. Without it, `400`, and the message says a preview must be confirmed.
- Creates the PayPal product and plan, returns the new plan id.
- **Does not silently repoint the catalogue.** Creating a plan and switching customers onto it are two decisions; the admin makes the second one with the existing `PUT /api/admin/plans/{plan_id}` by pasting the new id in. Say so in the response.
- Validates the same bounds as the existing write path: price > 0 and ≤ 100000, interval in `month`/`year`, currency ISO-4217, name 1-80 chars.
- Writes a plan-change audit row if ORDER P2-14 has landed; if it has not, log at INFO and note the dependency in your report.

### 4.3 Admin UI

In the Plans tab, a "Create a new PayPal plan" panel:

- Fields for name, price, interval, currency, trial days.
- **Preview first, always.** The create button is disabled until a preview has been fetched for the current field values; changing any field clears the preview and disables it again.
- The confirmation step states, in plain words the client will understand: *this creates a permanent plan in your live PayPal account and cannot be undone; existing subscribers are not affected and stay on their current price.*
- On success, show the new plan id and tell the admin the next step is to point a catalogue entry at it.
- Native styling, existing tokens and toast patterns. **Rule 4** on DOM ordering. **Rule 3** — no fabricated plan ids in any state.
- Readable at 375px — **Rule 10**.

### 4.4 Keep the script

`scripts/create_paypal_plan.py` stays. It is the fallback when the admin panel is unreachable and it is referenced in the client handover docs. Do not delete it and do not make it import from the API.

### 4.5 Tests

All PayPal interaction mocked.

- Preview returns the request body and makes no create call — assert the mock was never called.
- Create without `confirm: true` returns 400 and makes no call.
- Create with confirmation returns the new plan id.
- Both endpoints require admin; a customer token gets 403.
- Credentials unset → the unavailable path, not a false success.
- Validation bounds rejected as specified.
- Creating a plan does **not** modify `config/plans.json` — assert the file is byte-identical afterwards.

---

## 5. Out of scope

- No deployment, no SSH. Production stays at `b0d8bd4`.
- No automatic migration of existing subscribers to a new plan. PayPal requires each subscriber to approve a plan change; that is a separate piece of work and the client has been told so.
- No deleting or deactivating existing PayPal plans from the panel.
- No changes to the crawler, `config/sites.json`, or the diff engine.
- No push to the `client` remote. `origin` only.
- No new runtime dependency.

---

## 6. Acceptance criteria

1. `./venv/Scripts/python.exe -m pytest -q` → all green, including every new test, with PayPal mocked throughout.
2. Preview creates nothing, provably — the test asserts on the mock.
3. Create refuses without explicit confirmation.
4. No live PayPal object was created at any point during this work.
5. `git diff --stat` touches only `api/payments/paypal_provider.py`, `api/main.py`, `frontend/admin.html`, the test modules, and `docs/ai/tasks.md`.

---

## 7. Report back

- Commit SHA, `git diff --stat`, pytest tail.
- An explicit statement that no live PayPal call was made, and how you are sure.
- The preview response body verbatim.
- A screenshot of the create panel in its pre-preview, previewed, and confirmed states.
