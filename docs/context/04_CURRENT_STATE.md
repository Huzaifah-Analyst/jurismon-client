# Current Production State & System Baseline

**Snapshot Date**: October 4, 2026  
**Live Production Host**: [https://jurismon.com](https://jurismon.com)  
**Deployed Commit SHA**: `c7c01a0` (branch `claude/sweet-babbage-fz7sbz`)  
**Automated Test Suite**: 255 passed (`pytest tests/ -q`)

---

## 1. What Works End-to-End

The following subsystems are verified, active, and operating in production:

1. **Daily Automated Crawl Scheduling**:
   - Systemd timer `jurismon-crawl.timer` runs daily at 04:00 UTC, triggering `jurismon-crawl.service`.
   - Ingests planning, zoning, and statutory portals across 41 operational jurisdictions.
   - Deduplicates content using SHA-256 hashes, parses text from HTML and PDF documents, and executes Tesseract OCR on scanned documents.
2. **Snapshot Versioning & Regulatory Diff Engine**:
   - Compares successive document snapshots at the paragraph and section level.
   - Computes added, modified, and deleted statutory clauses, storing diff records in PostgreSQL.
3. **PostgreSQL Full-Text Search**:
   - `GET /api/documents` utilizes `websearch_to_tsquery` and headline extraction on PostgreSQL (Supabase).
   - Supports search by jurisdiction, document title, date range, and keyword queries.
4. **Customer Accounts, Authentication & Trial Gating**:
   - Customer signup via `POST /api/auth/register` with bcrypt password hashing.
   - Transactional email verification using 6-digit OTP codes via the Resend API (`POST /api/auth/verify-code`).
   - 14-day free trial activated upon verification.
   - Gated search results for unauthenticated or expired users (headline match visible; full text locked behind paywall).
   - Self-service password reset flow (`POST /api/auth/forgot-password` and `POST /api/auth/reset-password`).
5. **PayPal Subscription Payments & Webhook Automation**:
   - Client-side PayPal Smart Buttons embedding user account UUID in `custom_id` ([frontend/index.html:1326](file:///d:/fiverr%20client/malok%20mading/frontend/index.html)).
   - Webhook processor (`POST /api/payments/webhook`) handling `BILLING.SUBSCRIPTION.ACTIVATED`, `PAYMENT.SALE.COMPLETED`, and `BILLING.SUBSCRIPTION.CANCELLED`.
   - Automatic account activation and cancellation.
6. **Administrative Console**:
   - Protected by JWT Bearer authentication (`POST /api/admin/login`).
   - Live metrics calculated dynamically from the database (operational source counts, daily crawl logs, active customer subscriptions).
   - Manual crawl trigger button initiating `jurismon-crawl.service` via systemd wrapper with self-healing crawl lock recovery.
7. **Legal Compliance Pages**:
   - Dedicated Terms of Service (`/terms`) and Privacy Policy (`/privacy`) pages featuring working contact routes (`support@jurismon.com`) and unified brand lockups.

---

## 2. What Is Deliberately Absent

The following capabilities were intentionally excluded from Phase 1 scope:

- **Customer Self-Service Account Management**:
  - There is currently no `/account` profile page for customers to change their email, update personal details, or view invoice history. Customers manage password recovery via the reset flow, and manage their subscription directly within their PayPal account.
  - *Why omitted*: Contracted scope focused on customer search gating, trial activation, and payment collection. Self-service account administration is scheduled for Phase 2.
- **Analytics & Tracking Pixels**:
  - Google Analytics, Meta Pixel, and third-party tracking scripts are completely absent from all frontend templates.
  - *Why omitted*: Deploying tracking scripts requires an interactive GDPR/CCPA cookie consent management banner. Integrating analytics without consent violates European and UK privacy laws. Deferred to Phase 2.
- **Automated Email Alerts on New Statutory Amendments**:
  - While the system extracts diffs and records regulatory amendments, it does not send automated outbound notification emails to users when new diffs are created.
  - *Why omitted*: Phase 1 contracted search and historical delta inspection. Push notification alerting is part of the Phase 2 roadmap.

---

## 3. Known Limitations

Technical boundaries, external upstream constraints, and hardware capacity limits are documented in detail in [docs/HANDOVER.md Section 8 (Known Limitations)](file:///d:/fiverr%20client/malok%20mading/docs/HANDOVER.md#8-known-limitations). Summary of core limitations:
- **Cloudflare-Protected Sources (7 jurisdictions)**: Portals using Cloudflare Turnstile or aggressive bot challenges (e.g., NYC Rules) cannot be bypassed without third-party residential proxies or CAPTCHA solving services, which are out of scope.
- **Single-Host Crawl Concurrency**: The crawler operates serially per host with polite delays (0.5s–1.5s jitter) to avoid IP blacklisting by municipal servers.
- **Tesseract OCR Throughput**: OCR processing on scanned PDFs is CPU-bound on the 2-vCPU VPS instance; large documents (100+ pages) take several minutes to process.

---

## 4. Consciously Accepted Quirks

The following implementation quirks were identified during development and deliberately preserved for Phase 1 stability:

1. **Hardcoded "MM" Avatar Initials in Admin Header** ([frontend/admin.html:698](file:///d:/fiverr%20client/malok%20mading/frontend/admin.html)):
   - *Status*: The admin header renders an avatar chip with the static initials "MM", matching the client's name (Malok Mading).
   - *Why left*: Admin authentication uses a shared administrative password verified against `$ADMIN_PASSWORD_HASH`. There is no administrative user profile entity in the database to dynamically derive initials from.
   - *When to fix*: When multi-user role-based administrative accounts are implemented in Phase 2.
2. **Fallback Catalog Counters in Frontend Markup** ([frontend/admin.html:706](file:///d:/fiverr%20client/malok%20mading/frontend/admin.html), [frontend/index.html:123](file:///d:/fiverr%20client/malok%20mading/frontend/index.html)):
   - *Status*: The HTML templates contain fallback text referencing 65 sources if the live statistics API (`/api/stats` or `/api/admin/metrics`) fails to respond.
   - *Why left*: Provides a graceful fallback if the client loses network connectivity.
   - *When to fix*: When the catalog expands in Phase 2 (e.g., ingesting the 88 new sources), the fallback strings should be updated or replaced with generic loading skeletons.
3. **In-Memory Rate Limiting in `api/auth.py`** ([api/auth.py:60-95](file:///d:/fiverr%20client/malok%20mading/api/auth.py)):
   - *Status*: Password reset and login attempt rate limits are tracked in a process-local Python dictionary with timestamps.
   - *Why left*: The production environment runs a single Uvicorn process managed by systemd. An in-memory dict avoids adding Redis as an infrastructure dependency.
   - *When to fix*: If Uvicorn worker count is scaled horizontally across multiple processes or containers, rate limiting must be migrated to Redis.
