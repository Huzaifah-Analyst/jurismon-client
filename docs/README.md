# JurisMon Documentation Index

> **I am new here, what do I read first?**
> 1. If you are an **AI coding agent**: read [`docs/ai/rules.md`](ai/rules.md) and [`docs/ai/prd.md`](ai/prd.md) first.
> 2. If you are a **human developer or manager**: read [`docs/context/00_START_HERE.md`](context/00_START_HERE.md) first.
> 3. If you are the **client or operator**: read [`docs/client/handover.md`](client/handover.md) first.
> 4. To check current development tasks: see the live board at [`docs/ai/tasks.md`](ai/tasks.md).

---

## Directory Overview

| Directory | Audience | Purpose | Status |
| :--- | :--- | :--- | :---: |
| [`docs/ai/`](ai/) | AI Coding Agents | Structured operational specifications, architecture contracts, rules, tasks, and memory. | **Canonical** |
| [`docs/context/`](context/) | Human Engineers | Narrative build history, decision logs, failure forensics, and milestone trajectory. | **Canonical** |
| [`docs/client/`](client/) | Client / End Operator | Deliverables, handover runbooks, action guides, and setup instructions. | **Canonical** |
| [`docs/reports/`](reports/) | Engineering Team | Data audit reports, crawler verification findings, and source analysis dumps. | **Canonical** |
| [`docs/assets/`](assets/) | Marketing / Reviewers | Verified screenshots, architecture diagrams, posters, and review media. | Supporting |
| [`docs/archive/`](archive/) | Provenance Reference | Superseded chat logs, legacy drafts, and interim working documents. | Deprecated |

---

## Detailed Shelving Index

### 1. [`docs/ai/`](ai/) — Agent Engineering System
Targeted context designed specifically for AI coding agents modifying this codebase.
- [`ai/prd.md`](ai/prd.md) — Product requirements, user personas, system workflows.
- [`ai/architecture.md`](ai/architecture.md) — Technical contracts, system pipeline, database schemas.
- [`ai/rules.md`](ai/rules.md) — Eleven binding operational engineering rules.
- [`ai/design.md`](ai/design.md) — Architectural rationale, component boundaries, error philosophy.
- [`ai/tasks.md`](ai/tasks.md) — Live Phase 1 / Phase 2 Kanban board.
- [`ai/memory.md`](ai/memory.md) — Forensic post-mortem lessons from production incidents.
- [`ai/orders/`](ai/orders/) — Individual task packets and implementation orders.

### 2. [`docs/context/`](context/) — Human Project History
Narrative history, decision rationales, and background for human engineers and leads.
- [`context/00_START_HERE.md`](context/00_START_HERE.md) — High-level orientation and quick index.
- [`context/01_PROJECT.md`](context/01_PROJECT.md) — Problem statement, business model, and client background.
- [`context/02_DECISIONS.md`](context/02_DECISIONS.md) — 22 architectural decisions with rationale.
- [`context/03_FAILURE_LOG.md`](context/03_FAILURE_LOG.md) — Detailed failure forensics and lessons.
- [`context/04_CURRENT_STATE.md`](context/04_CURRENT_STATE.md) — Component-by-component operational status.
- [`context/05_PHASE_2_BACKLOG.md`](context/05_PHASE_2_BACKLOG.md) — Phase 2 feature backlog and estimates.
- [`context/06_WORKING_RULES.md`](context/06_WORKING_RULES.md) — Working principles, verification rules, and git hygiene.
- [`context/07_SESSION_HANDOFF.md`](context/07_SESSION_HANDOFF.md) — Session-to-session handoff state.
- [`context/linkedin_drafts.md`](context/linkedin_drafts.md) — Social proof drafts backed by repo truth.

### 3. [`docs/client/`](client/) — Client Deliverables & Guides
Client-facing documentation and operational guides.
- [`client/handover.md`](client/handover.md) / [`.pdf`](client/handover.pdf) — Production system handover manual.
- [`client/client-action-guide.md`](client/client-action-guide.md) / [`.pdf`](client/client-action-guide.pdf) — Immediate action checklist.
- [`client/supabase-resend-setup.md`](client/supabase-resend-setup.md) / [`.pdf`](client/supabase-resend-setup.pdf) — Supabase and Resend credential setup.
- [`client/source-coverage.md`](client/source-coverage.md) / [`.pdf`](client/source-coverage.pdf) — Status report across all 65 sources.
- [`client/client-requirements.md`](client/client-requirements.md) — Original client requirements.
- [`client/project-spec.md`](client/project-spec.md) — Initial project specification.
- [`client/about-us-source.pdf`](client/about-us-source.pdf) — Client-provided background material.

### 4. [`docs/reports/`](reports/) — Audits & Data Dumps
Crawler site audits and verification dumps.
- [`reports/audit-51-sites.md`](reports/audit-51-sites.md) — Initial crawler viability evaluation across 51 sites.
- [`reports/sources-18-additional.txt`](reports/sources-18-additional.txt) — Raw notes for 18 additional sources.
- [`reports/data/audit-results.json`](reports/data/audit-results.json) — 51-site audit raw output.
- [`reports/data/audit-18-new-sources.json`](reports/data/audit-18-new-sources.json) — 18-source evaluation raw output.
- [`reports/data/live-reverification-19-sites.json`](reports/data/live-reverification-19-sites.json) — 19 edge-case sources live output.

### 5. [`docs/assets/`](assets/) — Visual Media & Artifacts
- [`assets/screenshots/p2-01/`](assets/screenshots/p2-01/) — Authenticated account page verification screenshots.
- [`assets/posters/`](assets/posters/) — High-resolution system architecture posters.
- [`assets/review-card.png`](assets/review-card.png) — Five-star client review visual card.

### 6. [`docs/archive/`](archive/) — Deprecated Scratch
Superseded scratchpads and interim notes kept strictly for provenance. See [`docs/archive/README.md`](archive/README.md).
