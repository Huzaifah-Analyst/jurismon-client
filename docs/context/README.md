# JurisMon Engineering Context & History

> **Audience**: Human developers, engineering leads, and reviewers.  
> **Purpose**: Narrative build history, architectural decision records (ADRs), failure forensics, and client context.  
> **Status**: Canonical

---

## Relationship to `docs/ai/`

- **[`docs/context/`](.)** is written for **human engineers** onboarding to or reviewing the system. It captures the narrative story, trade-offs, 22 key architectural decisions, post-mortem incident forensics, and client relationship trajectory.
- **[`docs/ai/`](../ai/)** is structured specifically for **AI coding agents**. It contains formal system contracts, operational engineering rules, live Kanban task boards, and strict machine-executable instructions.
- **Rule**: Do not merge these folders. For current operational rules and technical contracts, refer directly to [`docs/ai/rules.md`](../ai/rules.md) and [`docs/ai/architecture.md`](../ai/architecture.md).

---

## Document Index

| Document | Date Written | Description |
| :--- | :---: | :--- |
| [`00_START_HERE.md`](00_START_HERE.md) | 2026-10-04 | High-level engineering orientation, 5-minute system tour, and context map. |
| [`01_PROJECT.md`](01_PROJECT.md) | 2026-10-04 | Core problem definition, target buyer profiles, business model, and client relationship history. |
| [`02_DECISIONS.md`](02_DECISIONS.md) | 2026-10-04 | Catalog of 22 foundational architectural decisions (ADRs) with rationale and rejected alternatives. |
| [`03_FAILURE_LOG.md`](03_FAILURE_LOG.md) | 2026-10-04 | Forensic post-mortems of 6 major build failures, root causes, and defensive patterns. |
| [`04_CURRENT_STATE.md`](04_CURRENT_STATE.md) | 2026-10-04 | Detailed subsystem-by-subsystem operational health report, verified metrics, and technical debt log. |
| [`05_PHASE_2_BACKLOG.md`](05_PHASE_2_BACKLOG.md) | 2026-10-04 | Prioritized Phase 2 feature backlog, scoping, and implementation roadmaps. |
| [`06_WORKING_RULES.md`](06_WORKING_RULES.md) | 2026-10-04 | Engineering principles, verification requirements, git conventions, and quality gates. |
| [`07_SESSION_HANDOFF.md`](07_SESSION_HANDOFF.md) | 2026-10-05 | Session-to-session continuity log, tracking active state, open decisions, and handoff notes. |
| [`linkedin_drafts.md`](linkedin_drafts.md) | 2026-10-04 | Repository-verified technical retrospective drafts and case study content for LinkedIn. |
