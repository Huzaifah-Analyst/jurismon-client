# ORDER P2-10 — Repository Documentation Hygiene

> **From**: Lead engineer
> **To**: Implementing agent (Antigravity)
> **Repo**: `jurismon-client` · **Branch**: `claude/sweet-babbage-fz7sbz`
> **Read first**: `docs/ai/rules.md`
> **Type**: Housekeeping. No application code changes. No deployment.

---

## 1. Why this order exists

`docs/` is a flat dump. 18 loose files sit at the top level — client PDFs, raw audit JSON, chat logs, prompt scratch files, a stray `source of truth.txt`, an `update.txt` — mixed in with two parallel, partly overlapping context systems (`docs/ai/` and `docs/context/`). Nobody opening this repo cold can tell what is canonical, what is a client deliverable, and what is dead scratch. Every new agent session pays that cost.

Fix the shelving. Do not rewrite the contents.

---

## 2. Current inventory (scanned, as of `c1f9ea2`)

```
docs/
  ANTIGRAVITY_FIX_PROMPTS.md      SYSTEM_AUDIT_PROMPT.md      CHAT_LOG.md
  DRAFTED_MESSAGES.md             COMMUNICATION_GUIDELINES.md CLIENT_REQUIREMENTS.md
  PROJECT_SPEC.md                 HANDOVER.md / .pdf          SOURCE_COVERAGE.md / .pdf
  JurisMon_Client_Action_Guide.md / .pdf
  JurisMon_Supabase_Resend_Setup.md / .pdf
  JurisMon - About Us Document.pdf          JurisMon_18_Additional_Sources.txt
  AUDIT_51_SITES_REPORT.md        audit_results.json          audit_18_new_sources.json
  live_reverification_19_sites.json
  source of truth.txt             update.txt / update.pdf
  ai/{prd,architecture,rules,design,tasks,memory}.md + orders/
  context/00..07*.md + linkedin_drafts.md + posters/ + review_card_clean.png
  screenshots_p2_1/*.png
  deliverable/ + deliverable.zip   (untracked)
```

Also untracked at repo root: `delivery_screenshots.zip`.

---

## 3. Target structure

```
docs/
  README.md                 <- index: what each folder is, who it is for
  ai/                       <- agent context (canonical, unchanged in content)
    README.md
    prd.md architecture.md rules.md design.md tasks.md memory.md
    orders/
      README.md
      ORDER-P2-02.md ORDER-P2-11.md ...
  context/                  <- human project history (canonical, unchanged in content)
    README.md
    00_START_HERE.md .. 07_SESSION_HANDOFF.md
  client/                   <- things written for or received from the client
    README.md
    handover.md handover.pdf
    client-action-guide.md  client-action-guide.pdf
    supabase-resend-setup.md supabase-resend-setup.pdf
    client-requirements.md  project-spec.md
    about-us-source.pdf           <- "JurisMon - About Us Document.pdf"
    source-coverage.md source-coverage.pdf
  reports/                  <- audits and crawl verification output
    README.md
    audit-51-sites.md
    data/audit-results.json data/audit-18-new-sources.json data/live-reverification-19-sites.json
    sources-18-additional.txt
  assets/
    screenshots/p2-01/*.png        <- from docs/screenshots_p2_1/
    posters/                       <- from docs/context/posters/
    review-card.png
  archive/                  <- superseded, kept for provenance, read by nobody
    README.md
    chat-log.md drafted-messages.md communication-guidelines.md
    antigravity-fix-prompts.md system-audit-prompt.md
    source-of-truth.txt update.txt update.pdf
```

---

## 4. Rules for the move

1. **`git mv` for every file.** Never delete-and-recreate — history must follow the file.
2. **Lowercase kebab-case filenames** everywhere except `docs/ai/`, `docs/context/` (their numbered/named files are referenced by name in prompts and commit messages — leave those filenames alone) and `ORDER-*.md`.
3. **Do not edit the body of any document** except to repair links (rule 5). No rewording, no "improving", no merging two documents into one. Content changes are a separate order.
4. **Do not merge `docs/ai/` and `docs/context/`.** They overlap on purpose: `ai/` is structured context for agents, `context/` is the human narrative and decision log. Each gets a README stating that distinction and pointing at the other.
5. **Repair every internal link.** `docs/ai/*.md` contain `file:///d:/fiverr%20client/...` absolute links and relative links into `docs/context/`. After the move:
   - Replace every `file:///d:/fiverr%20client/malok%20mading/...` link with a repo-relative path. Those absolute Windows paths are broken for everyone but one machine.
   - `grep -rn "file:///" docs/` must return nothing when you are done.
   - Every `](...)` target inside `docs/` must resolve to a file that exists. Verify it, do not assume it.
6. **Check outside `docs/` too.** `README.md` at repo root, `CLAUDE.md` if present, and any script referencing a docs path. `grep -rn "docs/" --include=*.md --include=*.py --include=*.sh .` and fix what moved.
7. **Each README.md is a real index**, not a placeholder: one line per file saying what it is and when it was written. The `docs/README.md` additionally answers, in four lines, "I am new here, what do I read first?"
8. **`.gitignore`**: add `docs/deliverable/`, `docs/deliverable.zip`, `delivery_screenshots.zip`. Build outputs and zipped bundles do not belong in git. Do not `git rm` them — they are already untracked; just stop them being added by accident.
9. **Nothing is deleted.** Dead scratch goes to `docs/archive/`, not to the bin. If you think a file is genuinely worthless, list it in your report and leave it in `archive/` for a human to decide.

---

## 5. Out of scope

- No changes to `api/`, `crawler/`, `frontend/`, `db/`, `tests/`, `config/`.
- No new documents written. (`docs/ai/orders/ORDER-P2-11.md` is a separate order; leave it where it is.)
- No deployment. No push to the `client` remote.
- Do not touch `config/sites.json` or `credentials/`.

---

## 6. Acceptance criteria

1. `./venv/Scripts/python.exe -m pytest -q` still passes at its current count (281). This order should not be able to break a test; if it does, you moved something that was not documentation.
2. `git log --follow` on three moved files shows their full pre-move history.
3. `grep -rn "file:///" docs/` → no output.
4. Every markdown link inside `docs/` resolves. State in your report how you verified this, not that you believe it.
5. `git diff --stat` shows renames (`R`), not mass add/delete pairs.
6. A person who opens `docs/README.md` cold can name, in under a minute, where the agent context lives, where the client deliverables live, and what they should read first.

---

## 7. Report back

- Commit SHA and `git diff --stat`.
- The link-verification method and its output.
- Any file you could not confidently place, and why — do not guess at a home for something you do not understand.
