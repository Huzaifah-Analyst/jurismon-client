# JurisMon Product Requirements Document (PRD)

> **Audience**: AI coding agents preparing to modify or extend JurisMon.  
> **Source of Truth Reference**: Human history and commercial brief are documented in [docs/context/01_PROJECT.md](../context/01_PROJECT.md) and [docs/context/04_CURRENT_STATE.md](../context/04_CURRENT_STATE.md).

---

## 1. The Problem

Municipalities, county boards, and planning authorities across North America and statutory bodies in the United Kingdom enact regulatory amendments to zoning ordinances, land-use bylaws, building codes, and municipal legislation on irregular schedules. 

These changes are published across hundreds of disconnected, proprietary government portals (Granicus Legistar, CivicPlus, Municode, custom municipal CMSs, and open data endpoints) in inconsistent, unstructured formats (scanned PDF notices, multi-hundred-page agenda packets, HTML minutes). Local governments rarely issue centralized push alerts, RSS feeds, or machine-readable changelogs when a clause is amended.

Legal professionals (land-use attorneys), real estate developers, urban planners, and municipal policy researchers who need to track these statutory shifts are forced into manual, error-prone portal monitoring or risk discovering amendments only after permits, client filings, or transactions are blocked.

---

## 2. What JurisMon Does

JurisMon provides an automated regulatory intelligence and statutory delta monitoring platform:
1. **Automated Ingestion**: Crawls 65 cataloged municipal and statutory portals daily using dedicated platform adapters.
2. **Text Normalization & OCR**: Extracts structured text from PDFs and HTML, running layout-aware text extraction with Tesseract OCR fallback for scanned images.
3. **Automated Statutory Diffing**: Normalizes legal text and computes section-level (§ / Section X.X) and paragraph-level diffs, recording clauses added, modified, or repealed between successive snapshots.
4. **Full-Text Search Engine**: Provides a Google-style search interface across thousands of municipal statutory documents and amendments with matched headline snippets.
5. **Customer Access Control**: Gates full text and diff details behind email-verified user accounts, 14-day free trials, and PayPal subscription billing.
6. **Administrative Operations**: Delivers a live operational console for source health inspection, manual crawl execution, and subscriber tracking.

---

## 3. User Personas

| Persona | Role & Capabilities | Authentication & Billing State |
| :--- | :--- | :--- |
| **Admin** | System operator (Malok Mading). Monitors source health status (41 operational / 24 non-operational), inspects crawl execution logs, triggers manual crawl jobs via systemd, and tracks subscriber counts. | Authenticated via shared bcrypt hash (`$ADMIN_PASSWORD_HASH`) via `/api/admin/login`; receives admin JWT (`role="admin"`). |
| **Subscriber** | Paying legal/real-estate customer. Has unrestricted full-text search access, views complete statutory texts, inspects historical diff deltas, and manages self-service subscription lifecycle (pause, resume, cancel). | Authenticated via customer JWT (`role="customer"`); active PayPal subscription recorded in database (`status="active"`). |
| **Trial User** | Prospect evaluating JurisMon. Receives unrestricted search and diff access during a 14-day window starting upon email OTP verification. Once expired without an active subscription, search returns teaser headlines with paywall upgrade modals. | Authenticated via customer JWT (`role="customer"`); verified email with `trial_ends_at > now()`. |

---

## 4. Current Feature Inventory

### [Shipped] Core Platform & Production Features (Deployed on VPS)
*All features below are verified, tested, and running in production at `https://jurismon.com` as of commit `c7c01a0`.*

- **[Shipped] Daily Automated Crawler**: Runs daily at 04:00 UTC via systemd timer (`jurismon-crawl.timer`), orchestrating multi-source ingestion across 65 configured jurisdictions ([`crawler/orchestrator.py`](../../crawler/orchestrator.py)).
- **[Shipped] Seven Crawler Adapters**: Specialized scrapers for Granicus, CivicPlus, Municode, REST APIs, XML/Atom feeds, direct documents, and custom HTML portals ([`crawler/adapters/`](../../crawler/adapters/)).
- **[Shipped] Document Extraction & OCR Pipeline**: Text extraction for PDF and HTML with Tesseract OCR for scanned PDF files ([`extractor/`](../../extractor/)).
- **[Shipped] Paragraph & Section Diff Engine**: Computes additions, deletions, and modifications between statutory snapshots with SHA-256 content deduplication ([`diff_engine/`](../../diff_engine/)).
- **[Shipped] Dual-Persistence Architecture**: Production PostgreSQL hosted on Supabase with SQLite fallback for offline execution and unit testing ([`db/repository.py`](../../db/repository.py)).
- **[Shipped] Numbered SQL Migrations**: Versioned database migrations (`001` through `007`) guarded by an automated SQLite/Postgres schema parity test ([`db/migrations/`](../../db/migrations/)).
- **[Shipped] Google-Style Full-Text Search**: Keyword, date-range, and jurisdiction search powered by PostgreSQL full-text search (`websearch_to_tsquery`) ([`api/main.py`](../../api/main.py)).
- **[Shipped] Customer Authentication & JWT**: Registration, bcrypt password hashing, and JWT bearer sessions (`api/auth.py`).
- **[Shipped] Transactional Email Verification**: 6-digit OTP codes sent via Resend API (`POST /api/auth/verify-code`).
- **[Shipped] 14-Day Free Trial & Search Gating**: Search teaser paywalling for unauthenticated or expired accounts (`api/main.py`, `frontend/index.html`).
- **[Shipped] Self-Service Password Reset**: Email-delivered 6-digit reset codes (`POST /api/auth/forgot-password`, `POST /api/auth/reset-password`).
- **[Shipped] PayPal Checkout Integration**: Client-side Smart Buttons embedding customer account ID into `custom_id` (`frontend/index.html`).
- **[Shipped] PayPal Webhook Automation**: Webhook endpoint processing `BILLING.SUBSCRIPTION.ACTIVATED`, `PAYMENT.SALE.COMPLETED`, and `BILLING.SUBSCRIPTION.CANCELLED` (`api/payments/paypal_provider.py`).
- **[Shipped] Admin Dashboard**: Authenticated metrics dashboard displaying real-time operational status, daily run logs, and manual crawl trigger with self-healing lock recovery (`frontend/admin.html`).
- **[Shipped] Legal Compliance Pages**: Static legal notices at `/terms` and `/privacy` with working contact links (`support@jurismon.com`).

### [Half-Built] Code-Complete but Not Deployed
- **[Half-Built] Customer Self-Service Subscription Controls & Account Page**:
  - *Status*: Backend repository methods, endpoints (`GET /api/account/subscription`, `POST /api/account/subscription/pause`, `/resume`, `/cancel`), webhook handler extensions, dynamic plan resolution, and `frontend/account.html` are fully implemented and verified by 269 passing tests as of commit `c3f4466`.
  - *Why half-built*: Code is committed to branch `claude/sweet-babbage-fz7sbz` but has **NOT** been deployed to the live production VPS.
- **[Half-Built] Dynamic Plan Catalog Reloading**:
  - *Status*: Plans are read from `config/plans.json` via `PLAN_CATALOGUE = _load_plan_catalogue()` at module import in `api/main.py:92`.
  - *Why half-built*: Resolves prices and plan names for existing plans dynamically, but changes made to `config/plans.json` at runtime require a server restart to take effect. Admin API to edit pricing is part of Phase 2 Part 2.

---

## 5. Planned Roadmap (Phase 2)

| Phase & Part | Scope Description | Prerequisites |
| :--- | :--- | :--- |
| **Phase 2, Part 2** | **Admin Pricing Management**: Admin API and UI controls to update plan prices in `config/plans.json` dynamically without server restart. | Part 1 (`c3f4466`) deployed. |
| **Phase 2, Part 3** | **Catalog Expansion (88 New Sources)**: Expand monitored sources from 65 to 153 using the client's provided list. Implement new `RestApiAdapter` and `SparqlAdapter` classes. | Source URL verification and parser tests. |
| **Phase 2, Part 4** | **Automated Email Alerts on New Amendments**: Post-crawl event scheduler checking newly recorded diffs against user watchlist criteria, formatting HTML summaries, and emailing subscribers via Resend. | Database table `user_alert_subscriptions`. |
| **Phase 2, Part 5** | **Saved Searches & User Watchlists**: Customer endpoints (`/api/customer/saved-searches`) and frontend UI in `index.html` allowing users to save search filters and recall them. | Database table `saved_searches`. |
| **Phase 2 (Future)** | **Export to CSV & Redline PDF**: Streaming search results to CSV and generating formatted legal comparison PDF redlines. | ReportLab / WeasyPrint pipeline. |
| **Phase 2 (Future)** | **Multi-User Organization Seats**: Corporate subscriptions with team seat allocation, invite links, and centralized billing. | Database tables `organizations`, `organization_members`. |
| **Phase 2 (Future)** | **Admin Source Health Outbound Alerts**: Slack webhook or email alerts sent to `$ADMIN_EMAIL` when operational sources degrade or crawl failure rate spikes. | Orchestrator health transition hooks. |
| **Phase 2 (Future)** | **Cookie Consent Banner & Analytics**: GDPR/ePrivacy compliant cookie banner with Google Analytics Consent Mode v2. | Consent UI and storage in `localStorage`. |

---

## 6. Deliberately Out of Scope

The following items are explicitly excluded from JurisMon's scope:
1. **Bypassing Advanced Bot Challenges (Cloudflare Turnstile, PerimeterX)**: 7 cataloged sources (e.g. NYC Rules) use enterprise bot challenges. Bypassing them requires residential proxy rotators or CAPTCHA-solving farms, which are out of scope.
2. **Automated Legal Advice or Statutory Interpretation**: JurisMon produces pure text diffs (verbatim additions and deletions). It does not generate legal opinions, predict litigation outcomes, or interpret compliance obligations.
3. **Multi-Tenant White-Labeling**: JurisMon is a single-tenant SaaS platform. Custom agency branding and white-labeled portals are not supported.
4. **Instant Push Webhooks to External Third-Party APIs**: Outbound webhooks to customer endpoints are deferred; notifications will operate via email alerts.
