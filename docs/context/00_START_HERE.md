# JurisMon Context Index & Orientation

## What JurisMon Is
1. JurisMon is an automated legal and regulatory monitoring platform that crawls municipal, county, and statutory planning portals across North America and the United Kingdom on a daily schedule.
2. It extracts, normalizes, and version-controls municipal ordinances, zoning bylaws, and statutory instruments, running an automated paragraph-level diff engine to identify and record regulatory amendments as they occur.
3. It serves legal professionals, real estate developers, and municipal researchers through a full-text search web application gated by email-verified customer accounts, 14-day free trials, and PayPal subscription billing, accompanied by a dedicated administrative portal for source health monitoring and crawl management.

---

## Current State of the Project (October 4, 2026)
- **Phase Status**: Phase 1 contract deliverables and production hardening items are delivered, verified, accepted, and deployed on the live production environment at [https://jurismon.com](https://jurismon.com).
- **Deployed Commit**: `c7c01a0` on branch `claude/sweet-babbage-fz7sbz`.
- **Automated Test Suite**: 255 unit and integration tests passing (`pytest tests/ -q`).
- **Operational Baseline**: 65 data sources configured, 41 actively ingested and monitored daily, 24 cataloged as non-operational due to external upstream factors (Cloudflare challenges, dead municipal links, or restricted endpoints).

---

## Folder Map: What to Read for What

| File | Content & Purpose |
| :--- | :--- |
| [00_START_HERE.md](00_START_HERE.md) | This orientation index, high-level summary, and reading guide. |
| [01_PROJECT.md](01_PROJECT.md) | Product scope, 8 original contracted items vs. delivered extras, commercial model, and client profile. |
| [02_DECISIONS.md](02_DECISIONS.md) | Architectural decision log documenting why critical technical choices were made and what alternatives were rejected. |
| [03_FAILURE_LOG.md](03_FAILURE_LOG.md) | Forensic record of 9 major bugs that hit production or survived code review, root causes, regression guards, and structural failure patterns. |
| [04_CURRENT_STATE.md](04_CURRENT_STATE.md) | Concrete inventory of what works end-to-end, what is deliberately absent, known limitations, and acknowledged temporary quirks. |
| [05_PHASE_2_BACKLOG.md](05_PHASE_2_BACKLOG.md) | Agreed Phase 2 scope items with engineering touchpoints, prerequisite extensions, and source catalog notes. |
| [06_WORKING_RULES.md](06_WORKING_RULES.md) | 10 non-negotiable development, testing, verification, and deployment rules learned through real project failures. |

---

## Reading Order for an Engineer Starting Cold

If you are joining this project for the first time without prior context, read in this order:

### Read First (Orientation & Safety)
1. **[00_START_HERE.md](00_START_HERE.md)**: Gain the 10,000-foot view of the architecture and project status.
2. **[01_PROJECT.md](01_PROJECT.md)**: Understand the product boundaries, customer tiers, and what was contracted versus added.
3. **[06_WORKING_RULES.md](06_WORKING_RULES.md)**: **Mandatory before touching code**. Adhere to the dual-schema rule, verification standards, and deployment separation.

### Read Before Making Structural or Backend Changes
4. **[03_FAILURE_LOG.md](03_FAILURE_LOG.md)**: Understand the pitfalls (especially SQLite/PostgreSQL drift and frontend auth gate traps) so you do not reintroduce them.
5. **[02_DECISIONS.md](02_DECISIONS.md)**: Learn why specific implementations exist (e.g., systemd timers instead of GitHub Actions, `custom_id` in PayPal webhooks).
6. **[04_CURRENT_STATE.md](04_CURRENT_STATE.md)**: Review known edge cases and baseline behavior.

### Reference When Scoping Future Work
7. **[05_PHASE_2_BACKLOG.md](05_PHASE_2_BACKLOG.md)**: Consult when preparing proposals or beginning work on Phase 2 enhancements.

---

## Pointers to External Operations Documentation
- **Production Operations & Deployment**: Refer to [docs/client/handover.md](../client/handover.md) for system architecture, environment variable declarations, systemd service management, backup procedures, and VPS deployment commands (`scripts/deploy.sh`).
- **Source Catalog Audit**: Refer to [docs/client/source-coverage.md](../client/source-coverage.md) for the complete breakdown of all 65 municipal and statutory sources, including exact URLs and exclusion classifications.
