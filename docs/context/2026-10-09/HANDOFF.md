# Handoff, 9 October 2026

Written at the end of a Claude Code session for whoever picks this project up next, human or AI. Read this before touching anything.

---

## 1. What this project is

JurisMon is a daily crawler that tracks changes to US municipal zoning codes and statutory law, sold as a subscription product to land use lawyers, real estate developers and zoning consultants. Client is Malok Mading. Developer is Huzaifah (Fiverr).

Repository: `Huzaifah-Analyst/jurismon-client` on `origin`. Client's own copy is `curtiskelton88/jurismon` on the `client` remote, which is also what the production VPS pulls from.

Live site: `https://jurismon.com`

---

## 2. Repository and branch state, as of this handoff

- Working branch: `claude/sweet-babbage-fz7sbz`. All real work lives here. Pushed to `origin`.
- Production (`client/main`, what the VPS runs): commit `b5f53bb`.
- `origin/main`: stale, many commits behind. Leave it alone, it is not used for anything.

Do not trust `git log client/main..claude/sweet-babbage-fz7sbz` to tell you what is deployed. The release process squashes each batch into one commit on `client/main` (see section 5), so the commit graph makes almost everything on the dev branch look "ahead" even when its content already shipped. The reliable check is a content diff:

```
git fetch client
git diff --stat client/main claude/sweet-babbage-fz7sbz
```

As of this handoff, that diff shows exactly one thing pending: the Live Feed frontend batch (commits `c413888` and `38ea641`), covered in section 4. Everything else on the dev branch is already live.

---

## 3. Read these documents first, in this order

1. `docs/ai/rules.md`, the non negotiable engineering rules for this project. Eleven of them. Read all eleven before writing a line of code.
2. `docs/ai/architecture.md`, how the system fits together.
3. `docs/ai/frontend-standard.md`, what a good frontend looks like for this project. Written 7 October 2026.
4. `docs/ai/frontend-audit.md`, the live frontend measured against that standard, with evidence for every finding.
5. `docs/ai/frontend-fix-plan.md`, the plan built from a 25 finding live QA report, batched 5 then 10 then 10, with each item's status.
6. `docs/ai/rigorous-testing-prompt.md`, a full testing brief for a future complete QA pass.
7. `docs/ai/tasks.md`, the live Kanban board. Check this first for what is shipped versus not.
8. `docs/ai/memory.md`, a forensic record of real failures on this project and the rules that came out of them. Read it so you do not repeat them.

---

## 4. What is built, tested, and sitting ready to deploy right now

Commits `c413888` and `38ea641` on `claude/sweet-babbage-fz7sbz`, not yet on production.

- A loading skeleton on the homepage search results, shown on first load and every search, instead of a blank list.
- A light animation when switching filter tabs or changing sort, reusing the page's existing motion pattern.
- A stale "65 jurisdictions" banner corrected to read the live count.
- A cap on the homepage result preview text (240 characters), fixing a real bug where a single long document could render a 14,198 pixel tall card. The full text expand button is untouched and still shows everything.
- Every em dash and en dash removed from the touched files, per the global style rule below.

306 backend tests passing. Verified live in a browser, no console errors. Not yet pushed to `client/main` or deployed. Deploy process is section 5.

---

## 5. How a release actually ships

This is not a normal git workflow. Read it carefully before deploying anything.

The client's production remote (`client`, `curtiskelton88/jurismon`) must never receive the full development history, because an early commit in that history (`d8df085`) contains a file with the raw client correspondence transcript (VPS root IP, commercial negotiation). It has since been untracked but the blob is still in history. So releases are squashed:

```bash
git fetch client
git checkout -b deploy/main-<date> client/main
git read-tree -u --reset claude/sweet-babbage-fz7sbz
git diff --cached client/main --stat | grep -iE "credential|secret|\.env|source-of-truth"   # must be empty
git commit -m "release: <summary>"
git diff client/main HEAD --stat   # should be empty after the commit if you check tree equality properly; see below
git push client deploy/main-<date>:main
```

Then verify the new commit's tree is identical to the dev branch's tree before pushing:

```bash
git rev-parse HEAD^{tree}
git rev-parse claude/sweet-babbage-fz7sbz^{tree}
# must match
```

After pushing, deploy and verify:

```bash
ssh -i credentials/ssh/jurismon_deploy root@2.25.250.77 "bash /var/www/jurismon/scripts/deploy.sh"
```

If the release carries a new migration file under `db/migrations/`, also run:

```bash
ssh -i credentials/ssh/jurismon_deploy root@2.25.250.77 "cd /var/www/jurismon && sudo -u jurismon ./venv/bin/python scripts/run_migrations.py"
```

Then clean up: switch back to `claude/sweet-babbage-fz7sbz`, delete the local `deploy/main-<date>` branch. If you had uncommitted work on the dev branch before starting this, `git stash` it first and `git stash pop` after, since building the release tree requires a clean checkout.

Verify a deploy landed with:

```bash
curl -s https://jurismon.com/api/health
```

The version field in that response is the deployed commit SHA.

---

## 6. Global style rule that applies to everything you write

No em dash (—) and no en dash (–) anywhere. Not in code, not in comments, not in commit messages, not in documentation, not in chat. Use a comma, a period, a colon, a semicolon, or brackets. This has no exceptions. A full cleanup pass was done on 8 October 2026 across the frontend and the docs/ai files; check any new file you write before committing it.

```bash
grep -rn "—\|–" <path>
```

One known remaining instance outside this cleanup's scope: `frontend/about.html` line 692 (`$50K–$500K+`), already live in production since commit `c133cb3`. Not fixed yet, flagged here as a follow up.

---

## 7. Credentials and access

Everything lives in `credentials/`, gitignored, never committed. See `credentials/README.md`.

- `credentials/production.env`: the live `.env` values (Supabase, PayPal, Resend, admin hash).
- `credentials/ssh/jurismon_deploy`: the SSH key for the VPS (`root@2.25.250.77`).
- `credentials/admin_password_rotated.txt`: the admin login for `/admin` (plaintext, for the human operator, not for entering into any form by an agent without the user's own request).
- `credentials/supabase.txt`, `credentials/Resend API.txt`: provider dashboards.

Running the backend test suite locally never needs live credentials, it runs against an isolated SQLite fallback. Only live verification (curl against `jurismon.com`, or a preview server pointed at production data) touches real credentials, and that only ever happens for GET requests.

---

## 8. The QA findings not yet acted on

Full detail in `docs/ai/frontend-fix-plan.md`. Short version of what is still open:

- **Item 2**: the About page's claims do not fully match what currently crawls (national foreign legislation is dominating "Newest" results over US municipal content, because 10 of 21 US county and city sources are currently broken). This needs a decision from the client: fix the broken sources, or soften the About page copy in the meantime, or both. Do not pick one unilaterally.
- **Batch 2** (10 items): cache headers, response compression, admin crawl status polling, a 375px layout overflow, no dark mode, the broken sources themselves, and a few more. Each one has its root cause and a planned fix already written out.
- **Batch 3** (10 items): mostly polish, a handful of confirmed-working checks that need no action, and three testing gaps (paid subscription states, true cross-browser testing, a full automated accessibility audit) that were never completed because they needed resources this session did not have (a real PayPal charge, multiple browser engines, Lighthouse).

Work through them one at a time. Explain the problem, the planned fix, and how it can be verified, to the user before touching code. Fix, test locally, verify in a browser, then ask before deploying.

---

## 9. House rules worth repeating

- Never fabricate UI data. This project has been burned by it twice before (see `docs/ai/memory.md`). Every number on screen comes from a real API call.
- Run the actual test suite and paste the actual output before claiming something works. "Should work" is not a result.
- Before claiming a deploy happened, verify it with `/api/health` or an equivalent live check. Before claiming a bug is fixed, reproduce the original symptom, apply the fix, reproduce again, and show both results.
- If you find you were wrong about something you reported earlier in a session, say so plainly in one line and move on. Do not over apologize, do not re-litigate it.
- Client-facing messages are drafted, never sent directly, and never mention internal implementation details like code structure, dashes, or process. They lead with what changed and why it matters to the client, not with technical mechanics.
