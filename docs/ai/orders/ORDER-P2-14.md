# ORDER P2-14 — Price Change Audit Record

> **From**: Lead engineer
> **To**: Implementing agent (Antigravity)
> **Repo**: `jurismon-client` · **Branch**: `claude/sweet-babbage-fz7sbz`
> **Read first**: `docs/ai/rules.md` (Rule 1 — dual-schema parity — is the one that will bite here)
> **Type**: Migration + backend + admin UI. No deployment.

---

## 1. Why

Phase 2 Part 2 was sold to the client with this bullet:

> *"A record of every price change, with dates"*

What actually exists is one `logger.info` line at `api/main.py:1734` that writes the admin, the old plan and the new plan into the systemd journal. It is not stored, not queryable, and not visible anywhere in the admin panel. The client — who is not going to run `journalctl` — cannot see their own record. On a VPS the journal is also rotated and eventually deleted.

A pricing record that disappears is not a record. Build the real one.

---

## 2. Current state (scanned, do not re-derive)

| Fact | Location |
| :--- | :--- |
| The only existing "record" | `api/main.py:1734` — `logger.info("Admin %s updated plan %s: old=%s, new=%s", ...)` |
| Plan write endpoint | `api/main.py:1628` `PUT /api/admin/plans/{plan_id}` |
| Catalogue settings endpoint | `api/main.py:1745` `PATCH /api/admin/plans` |
| Admin read endpoint | `api/main.py:1511` `GET /api/admin/plans` |
| Admin Plans tab panel | `frontend/admin.html:968` |
| Admin guard | `api/auth.py:120` `require_admin` |
| Latest migration | `db/migrations/007_subscription_controls.sql` — **next free number is `008`** |
| Migration 007 as a style reference | `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, plain SQL, runs on both engines |
| Schema parity guard | `tests/test_schema_contract.py` |
| Repo method naming to follow | `db/repository.py:572` `record_subscription`, `:825` `record_webhook_event` |
| Production | `b0d8bd4`, migrations through `007` applied |

---

## 3. Required work

### 3.1 Migration `008_plan_change_log.sql`

A table recording one row per accepted change:

| Column | Purpose |
| :--- | :--- |
| `id` | Primary key, following the convention of the existing tables |
| `changed_at` | ISO timestamp, UTC |
| `changed_by` | The admin token subject |
| `plan_id` | The catalogue plan id, or null for a catalogue-level (`trial_days` / `currency`) change |
| `field` | Which field changed — `price`, `name`, `paypal_plan_id`, `is_active`, `trial_days`, `currency` |
| `old_value` | Previous value as text |
| `new_value` | New value as text |
| `paypal_plan_id` | The PayPal plan the change was verified against, when applicable |

**Rule 1 is binding and this is where it bites.** The migration must apply cleanly to Supabase PostgreSQL *and* the SQLite fallback, and `tests/test_schema_contract.py` must stay green. Follow 007's plain-SQL style; do not use a Postgres-only type, a Postgres-only default, or a serial/identity construct that SQLite rejects. If you need a type that differs between engines, say so in your report rather than quietly picking one and breaking the other.

One change request that modifies three fields writes three rows. That is deliberate — the client asked for a record of every change, and a single blob row cannot be read back as "when did the price go up".

### 3.2 Repository methods

In `db/repository.py`, following the existing dual-branch pattern (Supabase branch and SQLite branch, both implemented — a missing Supabase branch is the documented failure in `docs/ai/memory.md`):

- `record_plan_change(...)` — writes one row.
- `list_plan_changes(limit=100)` — newest first.

### 3.3 Wire the write endpoints

- `PUT /api/admin/plans/{plan_id}`: after the catalogue file write succeeds, write one row per changed field.
- `PATCH /api/admin/plans`: same for `trial_days` and `currency`.
- The log line at `api/main.py:1734` **stays**. A stored row and a journal line serve different purposes; do not remove the logging as "now redundant".
- Recording must not be able to fail the price change. If the insert raises, log at ERROR and still return success — the catalogue file is already written and the admin needs to know the price took effect. Report the discrepancy in the response rather than hiding it.

### 3.4 Read endpoint

`GET /api/admin/plans/changes`, guarded by `require_admin`, newest first, with a `limit` query parameter (default 50, max 200).

### 3.5 Admin UI

In the Plans tab (`frontend/admin.html:968`), below the plan cards: a "Price change history" table — date, admin, plan, field, old → new.

- Reuse the table styling already in that page. No new CSS system.
- **Rule 3**: if the fetch fails, say so. Do not render an empty table that reads as "no changes have ever been made".
- Empty state says "No pricing changes recorded yet" — which is honest and different from a failure.
- **Rule 4**: no element referenced before it exists in DOM order; no `if (!el) return` guards bolted on to hide ordering mistakes.
- Readable at 375px — **Rule 10**.

### 3.6 Tests

- Migration applies on both engines; `tests/test_schema_contract.py` green.
- A price edit writes exactly one row with correct old and new values.
- A three-field edit writes three rows.
- A rejected edit (PayPal mismatch → 409, last-active-plan → 409) writes **zero** rows. A record of changes that never happened is worse than no record.
- `GET /api/admin/plans/changes` requires admin; returns newest first; respects `limit`.
- A failing insert does not fail the price change.

---

## 4. Out of scope

- No deployment, no SSH. Production stays at `b0d8bd4`.
- No change to how prices are verified against PayPal — that behaviour from `c1f9ea2` is correct and stays.
- No retroactive back-filling of historic changes. There is no data to back-fill from; inventing rows would be fabrication (**Rule 3**).
- No changes to `config/sites.json`, the crawler, or the extractor.
- No push to the `client` remote. `origin` only.
- No new runtime dependency.

---

## 5. Acceptance criteria

1. `./venv/Scripts/python.exe -m pytest -q` → 286 + new tests, all green, `test_schema_contract.py` included.
2. Changing a price in the admin panel immediately shows a new row in the history table, with the correct date and both values.
3. A refused change leaves the history untouched.
4. `git diff --stat` touches only `db/migrations/008_plan_change_log.sql`, `db/repository.py`, `api/main.py`, `frontend/admin.html`, the test modules, and `docs/ai/tasks.md`.

---

## 6. Report back

- Commit SHA, `git diff --stat`, pytest tail.
- The migration SQL verbatim, and how you verified it runs on both Postgres and SQLite.
- A screenshot of the history table with at least two real rows in it.
- The exact command the user must run on the VPS to apply migration `008`.
