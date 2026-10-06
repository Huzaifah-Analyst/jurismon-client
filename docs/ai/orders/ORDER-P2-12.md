# ORDER P2-12 — `/api/health` Endpoint

> **From**: Lead engineer
> **To**: Implementing agent (Antigravity)
> **Repo**: `jurismon-client` · **Branch**: `claude/sweet-babbage-fz7sbz`
> **Read first**: `docs/ai/rules.md`
> **Type**: Small backend addition. No deployment.

---

## 1. Why

`.github/workflows/ci.yml:66` probes `https://jurismon.com/api/health` as its post-deploy liveness gate. That endpoint does not exist — verified against production on Oct 6 2026, it returns **404**. The deploy job is currently disabled behind `workflow_dispatch` + `enable_deploy`, so nothing is broken today, but the moment anyone enables it every deploy fails on a green deploy.

The probe is right; the endpoint is missing. Add it.

---

## 2. Current state (scanned, do not re-derive)

| Fact | Location |
| :--- | :--- |
| CI liveness probe | `.github/workflows/ci.yml:66` |
| Deploy job gate | `.github/workflows/ci.yml:50` — `workflow_dispatch` + `enable_deploy == true` |
| No health route exists | `grep -n "/api/health" api/main.py` → no hits |
| Nearest route pattern to copy | `api/main.py:464` `GET /api/sources` |
| Production commit | `b0d8bd4`, service active, migrations through `007` applied |

---

## 3. Required work

### 3.1 The endpoint

`GET /api/health` in `api/main.py`, unauthenticated, no rate limit.

Return `200` with:

```json
{
  "status": "ok",
  "version": "<short git sha or app version>",
  "database": "ok",
  "uptime_seconds": 1234
}
```

Rules for it:

- **It must actually check the database.** A handler that returns `{"status": "ok"}` unconditionally is worse than no endpoint — it makes CI go green while the API is serving 500s on every real request. Do one cheap read through `repo` (a `SELECT 1`, or the lightest existing repository call) and report the real result.
- When the database check fails, return **503** with `"status": "degraded"` and `"database": "error"`. Do not leak the exception text, the connection string, or the host — log the detail server-side at ERROR and return a generic message. **Rule 7 applies**: this endpoint is public and unauthenticated.
- Do not expose anything an attacker can use: no env values, no table counts, no Supabase URL, no library versions beyond the app's own.
- Keep it fast. It will be polled. No crawl state, no source health scan, no PayPal call.
- Version string: derive it from a cheap source (an `APP_VERSION` env var, or a module constant). **Do not shell out to `git` on every request.**

### 3.2 Tests

Add to the existing API test module:

- `GET /api/health` returns 200 and `status == "ok"` when the database is reachable.
- Returns 503 and `status == "degraded"` when the repository call raises (mock it).
- The response body contains no connection string, host, or exception text in the failure case — assert on that explicitly.
- Requires no authentication.

### 3.3 Do not touch the workflow

`.github/workflows/ci.yml` is already correct. The probe URL stays as it is. Do not enable the deploy job, do not change its gate, do not add secrets.

---

## 4. Out of scope

- No deployment, no SSH, no `scripts/deploy.sh`. Production is at `b0d8bd4`; leave it there.
- No migration.
- No changes to `config/`, `crawler/`, `frontend/`, `db/`.
- No push to the `client` remote. `origin` only.
- No new runtime dependency.

---

## 5. Acceptance criteria

1. `./venv/Scripts/python.exe -m pytest -q` → 283 + new tests, all green.
2. Running the API locally, `curl -s localhost:8000/api/health` returns 200 with a real database check.
3. Simulated database failure returns 503 and leaks nothing.
4. `git diff --stat` touches only `api/main.py`, the test module, and `docs/ai/tasks.md`.

---

## 6. Report back

- Commit SHA, `git diff --stat`, pytest tail.
- The exact repository call used for the database check and why it is the cheapest honest one.
- The failure-case response body, verbatim, so I can confirm it leaks nothing.
