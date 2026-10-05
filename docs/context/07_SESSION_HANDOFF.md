# 07 — Session Handoff

**Written:** 5 October 2026, end of Claude Code session `23ffe65b`
**For:** the next Claude Code session picking this project up
**Read first:** `00_START_HERE.md`, then this file, then `06_WORKING_RULES.md`

---

## 1. Who does what

There are three parties. Do not confuse them.

| Party | Role |
|---|---|
| **Huzaifah** (the user) | Fiverr seller. Owns the client relationship. Pastes task packets into Antigravity. |
| **Claude Code** (you) | CEO / architect / QA. You write task packets, audit what comes back, write every client-facing message. **You do not write feature code yourself** unless Huzaifah explicitly asks. |
| **Antigravity** | A separate AI agent on Huzaifah's Windows machine. It executes packets and pushes to GitHub. It is capable but it fabricates UI data and over-claims in reports. Verify everything. |

### The loop

```
You write a task packet
  → Huzaifah pastes it into Antigravity
    → Antigravity codes, tests, pushes to Huzaifah-Analyst/jurismon-client
      → Huzaifah pastes Antigravity's report back to you
        → YOU AUDIT THE ACTUAL COMMIT, not the report
          → PASS → next packet / deploy
          → FAIL → fix packet, repeat
```

**Never approve on the strength of a report.** Fetch the commit, read the diff,
run the tests yourself. Every single time. See §4.

---

## 2. Repository facts

- Working repo: `Huzaifah-Analyst/jurismon-client`
- **Working branch: `claude/sweet-babbage-fz7sbz`** — all real work lives here
- `origin/main` is **8+ commits behind** and has been for weeks. This is fine. Do not
  "fix" it without asking.
- Client repo: `curtiskelton88/jurismon` — Antigravity pushes there only after your approval
- Live site: `jurismon.com`

### Auditing a new commit

```bash
git fetch -q origin claude/sweet-babbage-fz7sbz
git checkout -q -B audit origin/claude/sweet-babbage-fz7sbz
git diff --stat <previous-sha> HEAD
```

### Running the tests (fresh cloud container)

```bash
pip install -q --ignore-installed PyYAML -r requirements.txt
python -m pytest -q
```

The `--ignore-installed PyYAML` is required — the Debian-packaged PyYAML has no
RECORD file and pip refuses to uninstall it. Without that flag the install fails.
Install takes ~2 min, the suite ~35 s.

**Current baseline: 269 tests passing at `c3f4466`.**

---

## 3. Where the project stands

### Phase 1 — delivered, paid ($200), 5-star review
8 contracted items plus a long list of unbilled additions. Live on jurismon.com.

### Phase 2 — in progress
Five parts. Pricing agreed with the client on 4 Oct:

| Part | Scope | Price | Status |
|---|---|---|---|
| 1 | Customer subscription pause / resume / cancel | — | ✅ **Code complete at `c3f4466`, NOT deployed** |
| 2 | Admin-controlled pricing | — | ⬜ Next |
| 1+2 together | | **$100** | Order placed, 7-day deadline |
| 3 | Email alerts + watchlists | $100 | ⬜ |
| 4 | 88 new sources | $150 | ⬜ |
| 5 | Case studies | **Free** (goodwill) | ⬜ |
| 3+4+5 together | | **$250** + $25 first-month support = **$275** | Not yet ordered |
| Retainer | Monthly support, on Fiverr | **$50/mo** after first month | Agreed in principle |

Huzaifah told the client Parts 1+2 in 3–4 days, with 7 on the order as a margin.

### Immediately outstanding
1. **Deploy Part 1** — code is approved but the live site still runs the old build
2. **Part 2 packet** — admin pricing (see the trap in §5)
3. **`docs/ai/` folder + CI pipeline** — packet written 5 Oct, awaiting Antigravity
4. **Homepage jurisdiction count** — client asked about it 5 Oct, three options put to
   him, awaiting his answer. See §5.

---

## 4. How to audit Antigravity — this is the job

Antigravity has produced a correct-sounding report alongside broken code **more than
once**. Its backend work is usually genuinely good. Its frontend work and its reports
are where the problems are.

### The checks that have actually caught things

```bash
# Fabricated data in a page
grep -rn "preview_state\|example.com\|PREVIEW\|sample\|demo" frontend/<page>.html

# Hardcoded values that should come from the server
grep -n '\$[0-9]\|[0-9]\{2\}\.00' frontend/<page>.html

# Fallbacks that invent plausible data
grep -nE '\|\| *"[A-Za-z0-9]' frontend/<page>.html

# Element ordering — last id= must be ABOVE the <script> line
grep -n 'id="' frontend/<page>.html | tail -3
grep -n "<script" frontend/<page>.html | tail -2

# Schema drift — the bug that broke production three times
grep -n "ALTER TABLE\|CREATE TABLE" db/migrations/0*.sql
python -m pytest tests/test_schema_contract.py -v
```

Then **open the screenshots with the Read tool and actually look at them.** Twice now
the fabricated value was plainly visible in an image nobody examined.

Also read the screenshot capture script. If it reaches a state via a query parameter,
a mock, or anything other than a real login against a real server, the screenshots are
worthless and the answer is FAIL.

### Report language to distrust

- A heading claiming a test ran, over a table of what *should* happen
- "Verified" with no command output
- "All X tests pass" — run them yourself
- A claim that both a Supabase and a SQLite branch exist — grep and count them

---

## 5. Traps that will bite the next session

**Schema drift.** `_init_sqlite_schema()` creates columns on the fly. Tests pass,
Postgres never hears about them, production breaks. Happened three times. Every new
column needs a numbered migration **and** the parity test must pass. Next migration
number: **008**.

**Single-branch repository methods.** A method with only a SQLite branch writes to a
file production never reads. `set_verification_code()` had this; live signup was broken
for weeks and nobody knew. Every write method needs both branches.

**`PLAN_CATALOGUE` is loaded once at import** (`api/main.py:92`). Part 2 is
admin-controlled pricing — a price change will not take effect until restart unless
Part 2 handles reload explicitly. **Flag this in the Part 2 packet.**

**PayPal plans are immutable.** "Change the price from admin" means creating a new plan
and migrating subscribers, who must approve the change. It is not a config field.
Existing subscribers keep their price unless they consent.

**Pushing is not deploying.** Five commits once sat pushed and undeployed while
everyone assumed the fix was live. Deployment is a separate manual step
(`scripts/deploy.sh`). Verify on the live site, not in the repo.

**Live PayPal credentials.** `.env` has `PAYPAL_MODE=live`. Never run subscription
lifecycle calls against it in testing. Antigravity was right to refuse this.

**The homepage shows a different number to admins and to the public.** This is
deliberate, not a bug, and not a caching problem. `frontend/index.html:1394` sets
`isAdminView = ("operational_count" in data)`. Admins see "41 active jurisdictions"
plus the Cloudflare/dead-link breakdown; everyone else sees "65 U.S. jurisdictions"
and "Monitoring 65 municipal and county portals daily". It came from Huzaifah's own
requirement that visitors not be shown "41 / 65".

On 5 Oct the client asked whether the 65 was correct, having seen 65 while Huzaifah
saw 41 in the same session. **If this comes up again: it is not cache, do not tell
anyone to hard-refresh.** The honest concern is that 65 oversells — 24 of those
portals bring in nothing, so a subscriber who paid on the strength of "65" has a
legitimate refund argument. Three options were put to the client: leave 65, change to
41, or "41 live jurisdictions, 65 tracked" (recommended — true, doesn't undersell, and
still reads correctly once Part 4 raises both numbers). **Awaiting his decision.**

Related: `index.html:1407` has `data.count ?? data.total_configured ?? 65` — a
hardcoded 65 fallback. It happens to be the real configured count today, but it will
be wrong the moment Part 4 lands. Fix it then.

---

## 6. Deployment (unchanged, bare metal)

- `systemd` service `jurismon` + timer `jurismon-crawl.timer` for the nightly crawl
- nginx + certbot (Let's Encrypt)
- Python venv, Playwright Chromium, Tesseract OCR — all host-installed
- No Dockerfile
- `scripts/deploy.sh` does git pull → pip install → migrations → nginx → restart
- Scoped sudoers rule lets the app trigger a crawl without full root

**Coolify** was proposed by the client on 5 Oct and **shelved by the client himself**.
Do not raise it again unless he does. If it comes back: it is a real migration
(containerising Chromium + Tesseract, moving the systemd timer to a scheduled task,
replacing certbot with Coolify's proxy), ~1.5–2 days, and the VPS RAM needs checking
first. Estimated at $60.

---

## 7. Client relationship — read before writing any message

**Client:** Malok Mading (`@whizcoder`, `curtiskelton88@gmail.com`)

He is a good client: fair, communicative, pays, and left an exceptional review. On
5 Oct he said he wants Huzaifah **"around into the foreseeable, not just a few
months"** and that he **"can't be everything"** — he wants a team, and he'd rather not
be handling backends or code at all. That is the single most valuable thing he has
said. Everything should be written with it in mind.

### Message rules

- Warm, plain English. Short paragraphs. No corporate register, no exclamation marks.
- Honest about limits **before** they become disappointments. This is what earned the
  review, and it is the whole strategy.
- Never promise what the data cannot support.
- Scope creep is handled by pricing it, not by refusing it.

### Hard boundaries

- **Never** put credentials in Fiverr chat. Separate attached file only.
- **No off-platform work.** Huzaifah once asked for a message declining off-Fiverr work
  while arranging it by email anyway, "so the algorithm doesn't detect it". That was
  declined and the refusal stands. The retainer stays a Fiverr custom offer.
- The client's 142-link file stays parked until Part 4.
- `docs/context/` is internal. It candidly documents our own mistakes. **Never push it
  to the client repo.**

### Retainer positioning

The client currently thinks of the retainer as "Huzaifah does the server stuff". It
isn't. Reframe it, warmly, whenever it comes up: Coolify-style tooling can tell him the
app is running; it cannot tell him the data stopped being right. The retainer covers
portals changing their HTML, Cloudflare challenges, sources going quietly empty, PayPal
webhook changes. 24 of 65 sources were already non-ingestible at the start and that
list moves in both directions.

---

## 8. Verified numbers — safe to use, do not inflate

- 65 sources configured, **41 operational**
- 24 non-ingestible: 7 Cloudflare, 12 dead 404s, 3 timeouts, 1 auth-required, 1 403
- **269 tests passing** (255 before Part 1)
- 1,100+ statutory records indexed
- 7 platform adapter types
- Migrations 001–007

Anything not on this list gets verified before it goes in a client message, a LinkedIn
post, or a report.

---

## 9. If you are the next session and unsure where to start

1. Read `00_START_HERE.md` and `06_WORKING_RULES.md`
2. `git fetch` and check whether anything landed past `c3f4466`
3. Ask Huzaifah: did Part 1 get deployed, and did the `docs/ai/` packet run?
4. Then pick up from §3 "Immediately outstanding"
