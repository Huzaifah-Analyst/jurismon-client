# Phase 2 Engineering Backlog & Technical Touchpoints

This document outlines the agreed feature backlog for Phase 2. For each item, it details the existing foundations, required additions, and codebase touchpoints.

> [!IMPORTANT]
> The client's source review data and additional jurisdiction links are parked unmodified in [docs/archive/source-of-truth.txt](../archive/source-of-truth.txt) and [docs/reports/sources-18-additional.txt](../reports/sources-18-additional.txt).
> The active source configuration file at [config/sites.json](../../config/sites.json) must remain completely untouched until Phase 2 source expansion is formally commissioned.

---

## 1. Customer Self-Service Account Area

- **What already exists**:
  - Customer JWT token authentication (`api/auth.py`), user records in `users` table, and password reset endpoints (`api/main.py`).
- **What needs to be new**:
  - Frontend customer dashboard page (e.g., `frontend/account.html` or modal dialog).
  - Backend endpoints: `GET /api/customer/me` (profile info, subscription status, expiration date), `POST /api/customer/change-password`, and `POST /api/customer/cancel-subscription` (calling PayPal Subscriptions API to cancel via server-to-server REST call).
- **Existing code touched**:
  - `api/main.py`: Add customer account management routes.
  - `api/payments/paypal_provider.py`: Implement PayPal subscription cancellation API call (`POST /v1/billing/subscriptions/{id}/cancel`).
  - `frontend/index.html`: Add link to Account settings in the authenticated customer navigation bar.

---

## 2. Google Analytics with EU/UK Consent Layer

- **What already exists**:
  - Static HTML structure and styling framework across `frontend/index.html`, `frontend/terms.html`, and `frontend/privacy.html`.
- **What needs to be new**:
  - GDPR/ePrivacy compliant cookie consent banner with explicit "Accept All", "Reject Non-Essential", and "Customize" choices.
  - Integration with Google tag (`gtag.js`) utilizing Google Consent Mode v2 (`analytics_storage: 'denied'` by default until consent is granted).
  - Storage of consent preferences in `localStorage` with a persistent link in the footer allowing users to revise consent.
- **Existing code touched**:
  - `frontend/index.html`, `frontend/terms.html`, `frontend/privacy.html`: Add consent banner markup, consent management script, and Google Analytics tag.

---

## 3. Catalog Expansion: 88 New Sources (142 Supplied by Client)

- **What already exists**:
  - 65 sources currently cataloged in `config/sites.json` (54 of which overlap with the client's 142-item list).
  - Modular crawler adapter architecture in `crawler/adapters/` (`GranicusAdapter`, `CivicPlusAdapter`, `MunicodeAdapter`, `CustomAdapter`).
- **What needs to be new**:
  - Ingesting the 88 net-new sources from the client's list.
  - **New Adapter Types**: Several targets are not traditional HTML/PDF document portals:
    - Several sources are structured **REST APIs** returning JSON payloads (e.g., municipal open data portals like Socrata / ArcGIS Hub), requiring a dedicated `RestApiAdapter`.
    - One target is a **SPARQL endpoint** (UK legislation linked data), requiring a dedicated `SparqlAdapter` that queries RDF triples rather than scraping HTML DOM elements.
- **Existing code touched**:
  - `crawler/adapters/`: Implement `RestApiAdapter` and `SparqlAdapter`.
  - `crawler/orchestrator.py`: Register new adapter factories.
  - `config/sites.json`: Append 88 validated source definitions with appropriate selectors and adapter configurations.
  - `tests/test_new_adapters.py`: Add unit tests for REST and SPARQL adapter pipelines.

---

## 4. Email Alerts on New Amendments

- **What already exists**:
  - Diff generation engine (`diff_engine/engine.py`), snapshot recording (`db/repository.py`), and transactional email client using Resend (`notifications/mailer.py`).
- **What needs to be new**:
  - Database table `user_alert_subscriptions` tracking user email, source ID or keyword criteria, and notification frequency (immediate vs. daily digest).
  - Notification scheduler running after the daily crawl completes, querying newly created diffs, formatting HTML amendment summaries, and dispatching batch emails via `Mailer`.
- **Existing code touched**:
  - `db/migrations/`: Create migration for user alerts and subscription preferences.
  - `db/repository.py`: Methods to register alerts and query users matching updated sources.
  - `crawler/orchestrator.py` or `scripts/run_daily_crawl.py`: Hook to trigger alert dispatch post-crawl.
  - `notifications/mailer.py`: Add `send_amendment_alert()` template and batch delivery method.

---

## 5. Saved Searches and Watchlists

- **What already exists**:
  - Full-text search API (`GET /api/documents`) supporting query terms, jurisdiction filtering, and date parameters.
- **What needs to be new**:
  - Database table `saved_searches` (UUID, user_id, search_query, filters_json, created_at).
  - API endpoints: `POST /api/customer/saved-searches`, `GET /api/customer/saved-searches`, `DELETE /api/customer/saved-searches/{id}`.
  - UI interface on `frontend/index.html` allowing users to click a "Save Search" button and view a "My Watchlists" dropdown.
- **Existing code touched**:
  - `db/migrations/`: Add `saved_searches` table migration.
  - `db/repository.py`: CRUD methods for saved searches.
  - `api/main.py`: Endpoints for managing saved searches.
  - `frontend/index.html`: Watchlist UI elements and search recall logic.

---

## 6. Export to CSV / PDF

- **What already exists**:
  - Search result serialization in `api/main.py` and PDF rendering infrastructure in `scripts/md_to_pdf.py` (using ReportLab/WeasyPrint).
- **What needs to be new**:
  - CSV streaming endpoint: `GET /api/documents/export/csv` streaming search result metadata (jurisdiction, title, date, excerpt, source URL).
  - PDF export endpoint: `GET /api/diffs/{id}/export/pdf` generating a formatted legal redline comparison document for client download.
- **Existing code touched**:
  - `api/main.py`: Add export endpoints with streaming responses.
  - `diff_engine/`: Utility to format diff objects into printable HTML or ReportLab flowables.

---

## 7. Multi-User Team Seats & Organization Billing

- **What already exists**:
  - User records and PayPal subscription linking on a single-user basis.
- **What needs to be new**:
  - Database tables: `organizations` (id, name, owner_id, max_seats) and `organization_members` (org_id, user_id, role).
  - Corporate subscription tier in `config/plans.json` (e.g., Firm Plan with 5 or 10 seats).
  - Organization invitation flow: team owners can invite colleagues by email; invitees register without requiring separate payment.
- **Existing code touched**:
  - `db/migrations/`: Add organization and membership tables.
  - `db/repository.py`: Organization permission checks.
  - `api/auth.py`: Extend token claims to include `org_id` and role permissions.
  - `frontend/index.html`: Team member management view for team owners.

---

## 8. Source Health Alerts for Administrators

- **What already exists**:
  - Source health tracking (`health_status`, `status_detail` in `sources` table) and crawl execution metrics (`crawl_runs` table).
- **What needs to be new**:
  - Outbound webhook or email notification (via Slack incoming webhook or Resend email to `$ADMIN_EMAIL`) whenever an operational source transitions to `failing` or when crawl failure rate exceeds a threshold (e.g., >10% of sources fail).
- **Existing code touched**:
  - `crawler/orchestrator.py`: Add health status transition event triggers.
  - `notifications/mailer.py`: Add administrative alert template for degraded source warnings.
  - `api/main.py`: Configuration endpoint to manage administrative alert destinations.
