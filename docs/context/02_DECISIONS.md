# Architectural Decision Log

This document records the foundational architectural decisions taken during the build of JurisMon. For every major decision, it articulates what was chosen, the alternatives evaluated, and the technical rationale.

---

## 1. Systemd Timer on VPS vs. GitHub Actions for Automated Daily Crawling

- **Decision**: Daily crawling is scheduled and executed directly on the production host using a Linux systemd timer (`jurismon-crawl.timer` triggering `jurismon-crawl.service`), running daily at 04:00 UTC.
- **Alternatives Considered**: GitHub Actions scheduled workflow (`on: schedule: - cron: '0 4 * * *'`) or an external third-party webhook scheduler (e.g., Cronitor, EasyCron).
- **Rationale**:
  - GitHub Actions has an undocumented operational hazard for client handovers: GitHub automatically disables scheduled workflows if the repository sees no commit activity for 60 consecutive days ([docs/client/client-requirements.md:81-83](../client/client-requirements.md#L81-L83), commit `2bc5ae3`). Once development ceases and the client enters maintenance mode, a GitHub Actions crawl would silently stop running without warning.
  - Third-party cron services introduce an external point of failure and subscription cost.
  - The systemd timer runs natively under the OS init system, starts automatically on server boot, logs directly to the system journal (`journalctl -u jurismon-crawl.service`), and runs indefinitely without external dependencies.

---

## 2. Admin-Only Operational Health Breakdown vs. Public Display

- **Decision**: The public landing page displays only the high-level monitored footprint (e.g., "Monitoring 65 municipal and statutory sources across North America and the UK"). The detailed health breakdown (41 operational, 7 Cloudflare-protected, 12 dead links, 3 timeouts, 1 auth-required, 1 forbidden) is restricted strictly to the authenticated admin console ([frontend/admin.html:700-725](../../frontend/admin.html#L700-L725), commit `b4d7ca3`).
- **Alternatives Considered**: Displaying live operational health counters directly on the public homepage.
- **Rationale**:
  - Publicly advertising that 24 configured jurisdictions are currently unreachable due to external municipality dead links or Cloudflare anti-bot firewalls diminishes customer confidence and lowers subscription conversion rates.
  - The client and platform operators need precise, actionable diagnostic visibility into upstream failures to update URLs or configure new scrapers. Separating public positioning from administrative diagnostics serves both needs.

---

## 3. Manual Controlled Deployment (`scripts/deploy.sh`) vs. Automatic Push-to-Deploy

- **Decision**: Production deployment is an intentional, manual command executed on the VPS (`bash scripts/deploy.sh`), rather than an automated CI/CD pipeline triggered on `git push` to `main` (commit `caf1537`, [docs/client/handover.md:68-89](../client/handover.md#L68-L89)).
- **Alternatives Considered**: GitHub Actions deploying over SSH on every push, or a Webhook listener pulling updates automatically.
- **Rationale**:
  - The production database is a live PostgreSQL instance running on Supabase. Unattended deployments risk executing code changes that are out of sync with database migrations, causing immediate 500 errors for active users.
  - `scripts/deploy.sh` carries out explicit pre-flight checks: verifying git repository status, installing Python dependencies in the virtual environment, applying pending SQL migrations, validating Nginx and TLS configuration, restarting systemd services, and asserting an HTTP 200 health probe before completing. If any step fails, the deployment halts safely.

---

## 4. Admin "Run Crawl Now" Triggers Systemd Service Unit Instead of In-Process Background Task

- **Decision**: When an administrator clicks "Run Crawl Now" in the dashboard, the FastAPI backend (`POST /api/admin/crawl/run`) triggers `sudo /usr/bin/systemctl start jurismon-crawl.service` via a secure, passwordless sudoers wrapper, rather than spawning a background task or thread inside the Uvicorn web process ([api/main.py:1130-1170](../../api/main.py#L1130-L1170), commits `6a22bd1`, `2bc5ae3`).
- **Alternatives Considered**: Spawning `BackgroundTasks` in FastAPI, running `asyncio.create_task()`, or launching `multiprocessing.Process`.
- **Rationale**:
  - Crawling 65 municipal portals, downloading multi-megabyte PDF documents, parsing complex HTML tables, and executing Tesseract OCR takes several minutes and consumes substantial memory.
  - Executing this workflow inside the Uvicorn web process causes thread pool starvation, triggers HTTP gateway timeouts (Nginx 504), and exposes the web server to being killed by the Linux kernel Out-Of-Memory (OOM) killer.
  - Offloading to the systemd unit runs the crawl in an isolated cgroup with its own CPU/memory accounting, while the web process returns an immediate HTTP 200 response.

---

## 5. PayPal `custom_id` Tracking & Prioritized Webhook Resolution

- **Decision**: When creating a PayPal subscription on the frontend, the customer's JurisMon account UUID is passed into the `custom_id` parameter of the PayPal subscription payload. When PayPal webhooks fire (`BILLING.SUBSCRIPTION.ACTIVATED`, `PAYMENT.SALE.COMPLETED`), the backend matches the user by `custom_id` first, falling back to `payer.email_address` only if `custom_id` is absent ([frontend/index.html:1326](../../frontend/index.html#L1326), [api/payments/paypal_provider.py:46-55, 101-135](../../api/payments/paypal_provider.py#L46-L55), commit `315e8c7`).
- **Alternatives Considered**: Resolving user accounts exclusively by matching the PayPal `payer.email_address` against the database `users.email`.
- **Rationale**:
  - In practice, corporate customers and attorneys frequently register with their professional email address (e.g., `user@lawfirm.com`) but authorize subscription payments using a personal PayPal account or central firm accounting PayPal (e.g., `billing@holdingcorp.com`).
  - Relying solely on email matching resulted in orphan subscriptions where payment was successfully collected by PayPal, but the customer account remained locked. `custom_id` establishes a deterministic link.

---

## 6. Removal of the Admin Per-Source "Run Now" Button

- **Decision**: The per-source "Run now" button in the administrative source table was completely removed from the frontend and API ([frontend/admin.html](../../frontend/admin.html), commit `c7c01a0`).
- **Alternatives Considered**: Building a full per-source crawl endpoint (`POST /api/admin/sources/{id}/crawl`) and associated locking mechanism.
- **Rationale**:
  - Prior to commit `c7c01a0`, the "Run now" button in `admin.html` was a simulated mockup leftover from early prototypes: clicking it set the row to "running", waited 1800ms via `setTimeout`, and displayed a toast claiming the source had succeeded, without ever contacting the server.
  - Designing, implementing, testing, and hardening a real individual-source crawl endpoint hours before the final Phase 1 delivery deadline introduced severe regression risk (concurrency race conditions with the global crawl lock and crawler orchestrator).
  - Leaving a simulated button was completely unacceptable because it presented fabricated operational feedback to the client. The only sound engineering choice under the delivery deadline was complete excision.

---

## 7. Credential Invalidation and Git History Retention

- **Decision**: When a credential was inadvertently committed to the repository, the git history was **not** rewritten with `git filter-repo` or BFG Repo Cleaner. Instead, the compromised credential was immediately revoked and rotated at the service provider, replaced in production `.env`, deleted from working trees, and protected via hardened `.gitignore` rules (commit `315e8c7`).
- **Alternatives Considered**: Rewriting git history via `git filter-branch` or force-pushing rewritten branches.
- **Rationale**:
  - Force-pushing rewritten history changes commit SHAs across the entire git tree. This breaks all cloned developer worktrees, invalidates outstanding branch checkouts, and risks severe divergence with the client's repository (`client` remote).
  - Secret exposure cannot be undone by rewriting history after a push to a public or shared remote; the secret must be presumed compromised the moment it reaches the remote. Invalidation and key rotation at the service provider is the only real security mitigation.

---

## 8. "Working Draft" Legal Notice on Terms of Service and Privacy Policy Pages

- **Decision**: Both the Terms of Service (`/terms`) and Privacy Policy (`/privacy`) pages feature a prominent "Working Draft" notification banner at the top of the viewport ([frontend/terms.html:86-93](../../frontend/terms.html#L86-L93), [frontend/privacy.html:86-93](../../frontend/privacy.html#L86-L93), commit `fe81512`).
- **Alternatives Considered**: Presenting the generated legal text as final, binding legal agreements without any disclaimer.
- **Rationale**:
  - The legal pages were drafted as baseline technical agreements to satisfy payment gateway requirements and provide structured data privacy notices. However, they were not reviewed or certified by legal counsel in the client's jurisdiction.
  - Presenting unreviewed terms as final could expose the operator to regulatory liability. The banner explicitly states that the document is a working operational draft subject to legal review, maintaining transparency without halting deployment.
