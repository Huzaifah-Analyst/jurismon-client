# JurisMon AI Agent Context

> **Audience**: AI coding agents modifying this repository.  
> **Purpose**: Machine-actionable system contracts, architecture rules, schemas, and live task states.  
> **Status**: Canonical

---

## Relationship to `docs/context/`

- **[`docs/ai/`](.)** is structured specifically for **autonomous agents** about to modify code. It contains binding engineering rules, architectural contracts, schema definitions, and actionable task boards.
- **[`docs/context/`](../context/)** is written for **human developers, engineering leads, and reviewers**. It provides narrative history, 22 detailed architectural decision records (ADRs), forensic post-mortems of past failures, and client relationship history.
- **Rule**: Do not merge these folders. If an agent needs background on *why* a decision was made, refer to [`docs/context/02_DECISIONS.md`](../context/02_DECISIONS.md) or [`docs/context/03_FAILURE_LOG.md`](../context/03_FAILURE_LOG.md).

---

## File Index

| File | Date Written | Description |
| :--- | :---: | :--- |
| [`prd.md`](prd.md) | 2026-10-05 | Product requirements, user personas, problem definition, and operational workflows. |
| [`architecture.md`](architecture.md) | 2026-10-05 | Technical architecture contracts, data flow pipeline, dual SQLite/PostgreSQL schemas, and external integrations. |
| [`rules.md`](rules.md) | 2026-10-05 | Eleven binding, non-negotiable operational engineering rules for coding agents. |
| [`design.md`](design.md) | 2026-10-05 | Architectural design rationale, subsystem boundaries, UI principles, and failure handling philosophy. |
| [`tasks.md`](tasks.md) | 2026-10-05 | Live Phase 1 / Phase 2 Kanban task board, technical debt catalog, and completed milestones. |
| [`memory.md`](memory.md) | 2026-10-05 | Persistent agent memory: hard-learned forensic lessons, production gotchas, and recurring traps. |
| [`orders/`](orders/) | — | Formal engineering work orders and task packets issued to implementing agents (see [`orders/README.md`](orders/README.md)). |
