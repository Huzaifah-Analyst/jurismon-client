# JurisMon Live Engineering Board

> **Audience**: AI coding agents planning current and upcoming engineering tasks.  
> **Format**: Live Kanban status board. Status, files, and deliverables only — not narrative.

---

## 1. Phase 1 Deliverables Board

| Task ID | Component / Milestone | Delivered Commit | Status | Completed Date |
| :--- | :--- | :--- | :---: | :---: |
| **P1-01** | **Source Crawlers & Orchestration**: 65 cataloged sources, 7 adapter types | `49a599b` | **SHIPPED** | Oct 1, 2026 |
| **P1-02** | **Document Extraction & OCR Pipeline**: PDF, HTML, Tesseract OCR | `6a22bd1` | **SHIPPED** | Oct 2, 2026 |
| **P1-03** | **Database Persistence & Migrations**: Supabase PostgreSQL + SQLite (`001`-`006`) | `9df6dbc` | **SHIPPED** | Oct 3, 2026 |
| **P1-04** | **Regulatory Diff Engine**: Paragraph and section (§) diffing with deduplication | `e58817c` | **SHIPPED** | Oct 2, 2026 |
| **P1-05** | **Google-Style Full-Text Search**: PostgreSQL `tsquery` search with teaser paywall | `2bc5ae3` | **SHIPPED** | Oct 2, 2026 |
| **P1-06** | **Customer Auth & 14-Day Free Trial**: Bcrypt, JWT tokens, Resend OTP email verification | `74172a1` | **SHIPPED** | Oct 3, 2026 |
| **P1-07** | **PayPal Subscription Checkout & Webhooks**: Smart Buttons, `custom_id`, webhook events | `315e8c7` | **SHIPPED** | Oct 2, 2026 |
| **P1-08** | **Admin Operations Portal**: Live metrics, systemd crawl trigger, lock recovery | `c7c01a0` | **SHIPPED** | Oct 3, 2026 |
| **P1-09** | **Legal Pages & Compliance**: Terms of Service (`/terms`) and Privacy Policy (`/privacy`) | `9b8d1ae` | **SHIPPED** | Oct 3, 2026 |
| **P1-10** | **Production VPS Hardening & Deployment**: Hostinger Ubuntu 22.04 LTS, Nginx, Certbot TLS | `caf1537` | **SHIPPED** | Oct 3, 2026 |

---

## 2. Phase 2 Current & Backlog Board

| Task ID | Item Name | Scope & Engineering Touchpoints | Status | Code Commit |
| :--- | :--- | :--- | :---: | :---: |
| **P2-01** | **Customer Subscription Controls** | Pause, resume, cancel endpoints; customer account UI (`frontend/account.html`); dynamic plan resolution; migration `007`; Playwright authenticated screenshots. | **CODE COMPLETE** *(Not Deployed)* | [`c3f4466`](https://github.com/Huzaifah-Analyst/jurismon-client/commit/c3f4466) |
| **P2-02** | **Admin Pricing Controls & Dynamic Catalogue** | Admin API and UI to modify subscription pricing in `config/plans.json`. Fix module-level caching in `api/main.py:92` so price updates take effect immediately without server restart. | **NOT STARTED** | — |
| **P2-03** | **Catalog Expansion (88 Net-New Sources)** | Ingest 88 net-new sources from client's 142-source list. Build new `RestApiAdapter` (JSON open data) and `SparqlAdapter` (RDF linked data). | **NOT STARTED** | — |
| **P2-04** | **Automated Email Alerts on Amendments** | Database table `user_alert_subscriptions`. Post-crawl notification hook scanning new diffs against watchlists and dispatching email digests via Resend. | **NOT STARTED** | — |
| **P2-05** | **Saved Searches & User Watchlists** | Database table `saved_searches`. Customer CRUD endpoints (`/api/customer/saved-searches`) and frontend saved search recall dropdown. | **NOT STARTED** | — |
| **P2-06** | **Export to CSV & Redline PDF** | Endpoints for search CSV export (`GET /api/documents/export/csv`) and legal redline comparison PDF generation (`GET /api/diffs/{id}/export/pdf`). | **NOT STARTED** | — |
| **P2-07** | **Multi-User Organization Seats** | Corporate tiers in `config/plans.json`. Tables `organizations`, `organization_members`. Multi-seat license management. | **NOT STARTED** | — |
| **P2-08** | **Source Health Outbound Webhooks** | Outbound alerts to Slack / `$ADMIN_EMAIL` when operational sources degrade or crawl error rates exceed 10%. | **NOT STARTED** | — |
| **P2-09** | **Cookie Consent Banner & Analytics** | GDPR/ePrivacy compliant cookie banner with Google Consent Mode v2 and Google Analytics tag. | **NOT STARTED** | — |

---

## 3. Known Issues & Technical Debt Board

| Issue ID | File & Line | Description & Severity | Remediation Plan |
| :--- | :--- | :--- | :--- |
| **DEBT-01** | [`api/main.py:92`](file:///d:/fiverr%20client/malok%20mading/api/main.py#L92) | **Static Plan Catalogue In-Memory Caching**: `PLAN_CATALOGUE = _load_plan_catalogue()` loads once at module import. If `config/plans.json` is modified via admin API, running API does not observe changes until restart. | Replace module-level global with dynamic getter function `get_plan_catalogue()` or provide an atomic catalogue cache invalidation function in Phase 2 Part 2. |
| **DEBT-02** | [`frontend/admin.html:698`](file:///d:/fiverr%20client/malok%20mading/frontend/admin.html#L698) | **Static "MM" Avatar Initials**: Admin header avatar hardcodes "MM" chip matching Malok Mading. | Derive avatar initials dynamically when multi-user role-based admin profiles are introduced. |
| **DEBT-03** | [`api/auth.py:60-95`](file:///d:/fiverr%20client/malok%20mading/api/auth.py#L60-L95) | **Process-Local In-Memory Rate Limiting**: Password reset and login attempt limits are tracked in a process-local Python dictionary. | Sufficient for single Uvicorn worker; migrate to Redis if horizontally scaled across workers or instances. |
| **DEBT-04** | [`config/sites.json`](file:///d:/fiverr%20client/malok%20mading/config/sites.json) | **7 Cloudflare-Blocked Sources**: Portals like NYC Rules use Cloudflare Turnstile and fail ingestion with 403. | Remain cataloged as non-operational; require third-party residential proxies if contracted. |
| **DEBT-05** | Production VPS | **Phase 2 Part 1 Not Deployed**: Branch `claude/sweet-babbage-fz7sbz` contains customer subscription controls, but VPS runs commit `c7c01a0`. | SSH to VPS and execute `scripts/deploy.sh` after deployment approval. |
