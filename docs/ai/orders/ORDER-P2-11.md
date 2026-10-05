# ORDER P2-11 — Public "About Us" Page (`/about`)

> **From**: Lead engineer
> **To**: Implementing agent (Antigravity)
> **Repo**: `jurismon-client` · **Branch**: `claude/sweet-babbage-fz7sbz`
> **Read first**: `docs/ai/rules.md`, `docs/ai/design.md`
> **Source content**: `docs/JurisMon - About Us Document.pdf` (client-supplied, Oct 5 2026; will be `docs/client/about-us-source.pdf` after ORDER P2-10)
> **Type**: New public page. No deployment.

---

## 1. Objective

The client supplied a two-page "About Us Page Architecture" document. Build it as a real page at `/about`, in the existing design system, wired to the live source counts — not as a static marketing dump.

---

## 2. Source content (from the client PDF — build all five sections, in order)

| # | Section | Content |
| :-: | :--- | :--- |
| — | Lede | JurisMon eliminates the risk of unmonitored local regulatory change. Code publishers show today's law; aggregators alert on file upload; JurisMon is a **complete version-control system for municipal law**. |
| 1 | **Where the Data Begins: Continuous Multi-Portal Tracking** | Three cards — Platform Networks (Municode, Granicus Legistar, CivicPlus, XML/Atom, custom REST), Official Primary Sources (meeting notices, zoning agendas, board minutes, updated codes), Jurisdictional Scope (county commissioners, city councils, zoning boards of adjustment). |
| 2 | **How the Data Is Processed: Extraction & Normalization** | Four numbered cards — Automated Ingestion, Layout Stripping, OCR Fallback (Tesseract), Database Indexing (Postgres). |
| 3 | **The Core Backbone: Historical Retention & Legal Precedent** | Highlight panel "Why Immutable Version Control is Our Competitive Moat", then three cards — Point-in-Time Reconstruction, Immutable Snapshot Vault, Complete Statutory Lineage. |
| 4 | **Who Is Affected & What It Costs: Risk & Impact Analysis** | Three-column table: Real Estate Developers ($50K–$500K+ in delayed projects), Land Use & Zoning Attorneys (malpractice & missed appeals, 14-to-30-day appeal windows), Corporate Expansion Teams (wasted permitting & lease fees) — each with "How JurisMon Protects You". |
| 5 | **What Changes: Section-Level (§) Statutory Delta Analysis** | Three cards — Added Clauses (§), Removed Language, Modified Parameters (e.g. setback 20 ft → 15 ft). |
| — | CTA band | "Never Miss a Statutory Delta Again" + two buttons: **Start Searching Municipal Updates** → `/`, **Request Custom Jurisdiction Coverage** → `mailto:support@jurismon.com` with a prefilled subject. |

---

## 3. The claim problem — resolve it exactly this way

The client's PDF says **"65+ municipal sources"** twice (section 2 card 1, and the SEO meta description). On Oct 5 the client decided the public-facing wording is **"41 live jurisdictions, 65 tracked"** — shipped in `45f139d` across `frontend/index.html`. Only 41 of 65 portals actually ingest documents; 7 are Cloudflare-blocked, 12 are dead municipal links, the rest need logins.

Therefore:

- **Do not write "65+" anywhere on this page or in its meta tags.** It is the claim we just removed from the homepage, and shipping it on `/about` reinstates the refund exposure the client signed off on fixing.
- Section 2's ingestion card and the meta description use the live numbers. Fetch `GET /api/sources` on page load and render "N live jurisdictions, M tracked", exactly as `frontend/index.html:1405-1420` does. `live_count` is already exposed to unauthenticated callers (`api/main.py:402`).
- Keep a hardcoded "41 live jurisdictions, 65 tracked" in the markup as the pre-fetch and failure state, same pattern as the homepage pricing cards.
- The meta description is static HTML and cannot be live-updated usefully for crawlers — write it with the current figures and no "+".
- **"Sub-second search" (section 2, card 4) is an unverified performance claim.** Either measure it and keep it, or write "full-text search across every indexed document". Do not ship a latency number nobody has measured. Say in your report which you did.
- Everything else in the PDF is factually true of the system as built (7 adapters, Tesseract OCR fallback, SHA-256 dedup, section-level § diffing, point-in-time snapshots). Ship it as written.

---

## 4. Implementation

### 4.1 Route
- `frontend/about.html`, served at `GET /about` by a handler in `api/main.py` mirroring `/terms` (`api/main.py:228`) and `/privacy` (`:236`) exactly — same `FileResponse` pattern, same 404 fallback.
- Add `https://jurismon.com/about` to the sitemap alongside the existing `/terms` and `/privacy` entries (`api/main.py:291-296`).

### 4.2 Design
- Reuse the token set, Inter stack, spacing and radius scales documented in `docs/ai/design.md`. The page must be visually indistinguishable in chrome from `index.html` — same header, same brand lockup, same footer, same light/dark behaviour.
- Add an "About" link to the site header, present on `index.html`, `terms.html`, `privacy.html` and `about.html` so navigation is symmetric. Keep it out of the admin page.
- The three- and four-card rows are plain CSS grid, collapsing to one column at the existing mobile breakpoint. Verify at **375px** — Rule 10.
- Section 4's risk table must be readable on mobile: either a horizontal scroll container or a stacked card layout below the breakpoint. Do not let it overflow the viewport.

### 4.3 SEO
- `<title>`: `About JurisMon | Municipal Zoning Tracker, Historical Audit & Statutory Diffs` (from the client's PDF).
- Meta description per §3 — the client's wording with the count corrected.
- JSON-LD `AboutPage` / `Organization` block consistent with the existing block at `frontend/index.html:35`.
- Primary keywords to work into headings naturally, not stuff: municipal zoning monitor, historical municipal code archive, statutory diff engine, land use ordinance tracking, municipal version control.

### 4.4 Rules that will bite here
- **Rule 3**: every number on this page comes from the API or from a verified fact. No invented customer counts, no fake testimonials, no "trusted by" logos.
- **Rule 4**: no DOM element referenced before it exists; no `if (!el) return` guards bolted on to hide ordering mistakes.
- **Rule 10**: verify at 375px before you call it done.

### 4.5 Tests
Add to the existing API test module covering static routes:
- `GET /about` returns 200 and `text/html`.
- The sitemap response contains `/about`.
- `about.html` contains no literal `65+`.

---

## 5. Out of scope

- No changes to pricing, plans, auth, the crawler or the diff engine.
- No new runtime dependency, no CSS framework, no icon library — the existing pages use none.
- No deployment, no SSH, no push to the `client` remote.
- Do not alter the homepage jurisdiction wording settled in `45f139d`.

---

## 6. Acceptance criteria

1. `./venv/Scripts/python.exe -m pytest -q` → 281 + new tests, all green.
2. `grep -rn "65+" frontend/` → no output.
3. `/about` renders all five sections plus lede and CTA band, with live counts, and matches `index.html` chrome in both light and dark.
4. Readable at 375px with no horizontal page scroll, including the section-4 table.
5. `git diff --stat` touches only `frontend/about.html`, `frontend/index.html`, `frontend/terms.html`, `frontend/privacy.html` (nav link), `api/main.py`, the test module, and `docs/ai/tasks.md`.
6. Screenshots: desktop and 375px mobile, saved under `docs/assets/screenshots/p2-11/`.

---

## 7. Report back

- Commit SHA, `git diff --stat`, pytest tail.
- Which option you took on the "sub-second search" claim, and if you kept it, the measurement.
- Screenshot paths.
- Anything in the client's PDF you could not support with the system as built — quote it rather than quietly softening it. The client wrote that document; if a claim has to change, they need to be told which one and why.
