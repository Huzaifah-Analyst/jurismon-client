# JurisMon Technical Architecture

> **Audience**: AI coding agents preparing to modify or extend JurisMon.  
> **Source of Truth Reference**: Engineering history in [docs/context/02_DECISIONS.md](file:///d:/fiverr%20client/malok%20mading/docs/context/02_DECISIONS.md) and [docs/HANDOVER.md](file:///d:/fiverr%20client/malok%20mading/docs/HANDOVER.md).

---

## 1. End-to-End Request Path

```
Browser / Client (HTTPS:443)
       │
       ▼
Nginx Reverse Proxy (/etc/nginx/sites-available/jurismon)
       │  • TLS Termination (Let's Encrypt / Certbot)
       │  • Static asset pass-through (/static -> /var/www/jurismon/frontend)
       │  • HTTP-to-HTTPS redirect
       ▼
Uvicorn ASGI Server (127.0.0.1:8000, systemd: jurismon.service)
       │
       ▼
FastAPI Application (api/main.py)
       │
       ├── Middleware: CORS, Request Logging
       │
       ├── Authentication Dependencies (api/auth.py)
       │     • require_admin: verifies admin JWT from Authorization: Bearer <token>
       │     • require_customer: verifies customer JWT (sub=user_id, role="customer")
       │     • get_customer_optional: permits unauthenticated access with gating flags
       │
       ▼
Repository Data Layer (db/repository.py)
       │
       ├── Production Path: db.client.DatabaseClient -> Supabase Client (PostgreSQL)
       └── Local/Test Path: SQLite database (db_path / JURISMON_DB_PATH)
```

---

## 2. Ingestion & Crawler Pipeline

The daily crawl is orchestrated via `crawler/orchestrator.py` and runs end-to-end through six distinct stages:

```
┌─────────┐     ┌───────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│ 1. Fetch │ ──> │ 2. Extract│ ──> │ 3. Clean│ ──> │ 4. OCR  │ ──> │ 5. Diff │ ──> │ 6. Store│
└─────────┘     └───────────┘     └─────────┘     └─────────┘     └─────────┘     └─────────┘
```

1. **Fetch (`crawler/crawler.py`, `crawler/playwright_crawler.py`, `crawler/adapters/`)**:
   - Queries operational sources in `sources` table.
   - Evaluates adapter type; fetches remote HTML pages or downloads PDF binaries via `requests` or headless Chromium (Playwright) if client-side rendering is required.
   - Respects crawl etiquette: polite jitter delays (0.5s–1.5s), timeout limits (30s), custom User-Agent headers.
2. **Extract (`extractor/html_extractor.py`, `extractor/pdf_extractor.py`)**:
   - Parses DOM trees or extracts text streams from PDF pages (`pypdf` / `pdfplumber`).
   - Retains layout structure, section headings, and paragraph boundaries.
3. **Clean (`extractor/cleaner.py`)**:
   - Strips boilerplate: repetitive municipal headers/footers, navigation menus, disclaimer paragraphs, page numbers, and HTML artifacts.
   - Computes SHA-256 content hash of normalized text for snapshot deduplication.
4. **OCR (`extractor/ocr.py`)**:
   - Invoked when PDF extraction yields zero or low-density text (<50 characters per page).
   - Converts raster PDF pages to images via `pdf2image` and runs Tesseract OCR (`pytesseract`).
5. **Diff (`diff_engine/engine.py`, `diff_engine/parser.py`)**:
   - Compares the new snapshot against the most recent prior snapshot for that document ID.
   - Identifies structural units: sections (§, Section X.X), subsections, and paragraphs.
   - Computes added clauses, deleted clauses, and inline word/sentence modifications.
6. **Store (`db/repository.py`)**:
   - Saves new `snapshots` row if content changed.
   - Saves `diffs` row containing structured delta metadata (`added_sections`, `deleted_sections`, `delta_summary`).
   - Updates `documents.last_seen_at` and records run metrics in `crawl_runs`.

---

## 3. Crawler Adapters

Defined in `crawler/adapters/` and registered in `crawler/orchestrator.py`:

| Adapter Key | Module Class | Target Portals & Usage Scenario |
| :--- | :--- | :--- |
| `granicus` | `GranicusAdapter` (`granicus.py`) | Granicus Legistar portals. Queries agenda/calendar feeds, parses legislative detail tables, and retrieves attached ordinance PDF URLs. |
| `civicplus` | `CivicPlusAdapter` (`civicplus.py`) | CivicPlus municipal portals. Scrapes agenda centers, public document trees, and notices folders. |
| `municode` | `MunicodeAdapter` (`municode.py`) | Municode (CivicPlus) statutory code libraries. Navigates code structure trees and extracts recently enacted statutory ordinances. |
| `rest_api` | `RestApiAdapter` (`rest_api.py`) | Municipal open data portals exposing JSON REST endpoints (e.g. Socrata / ArcGIS Hub); extracts records directly from JSON fields without DOM parsing. |
| `xml_feed` | `XmlFeedAdapter` (`xml_feed.py`) | RSS, Atom, or government XML syndication feeds; parses publication dates and direct attachment links. |
| `direct_document` | `DirectDocumentAdapter` (`direct_document.py`) | Monitored static URLs pointing directly to a specific code file, PDF bylaw, or zoning regulation document. |
| `custom` | `CustomAdapter` (`custom.py`) | Unique municipal CMS sites requiring custom CSS/XPath selectors or Playwright DOM interactions to reveal downloadable documents. |

---

## 4. Dual Persistence: Supabase vs. SQLite

JurisMon uses a hybrid database architecture:
- **Production**: PostgreSQL hosted on Supabase (accessed via `supabase-py` client).
- **Local Development / Automated Tests**: Local SQLite file (`jurismon_local.db` or `JURISMON_DB_PATH`).

### ⚠️ THE REPOSITORY TRAP
Every data access method in `db/repository.py` **MUST** implement both execution branches:

```python
if self.supabase:
    # 1. Supabase PostgreSQL branch (PRODUCTION)
    try:
        res = self.supabase.table("table_name").insert(payload).execute()
        return res.data
    except Exception as e:
        logger.error(f"Supabase error: {e}")
        return None

# 2. SQLite branch (LOCAL / TESTS)
with self._connect() as conn:
    cur = conn.cursor()
    cur.execute("INSERT INTO table_name ...", (...))
    conn.commit()
    return ...
```

**Why this breaks agents**:
Unit tests and local CLI scripts typically run against SQLite (where `self.supabase` is `None`). If an agent implements only the SQLite query path, **all local tests pass 100%**. However, in production where Supabase is connected, the code executes the `if self.supabase:` branch. If that branch is missing, incomplete, or uses SQLite syntax, **production fails silently or crashes**.

---

## 5. Database Schema & Migrations

- Migrations are versioned SQL scripts in `db/migrations/`:
  - `001_initial_schema.sql`: Core tables (`sources`, `documents`, `snapshots`, `diffs`, `crawl_runs`).
  - `002_subscriptions.sql`: PayPal subscriptions table (`subscriptions`).
  - `003_subscription_details.sql`: Additional subscriber metadata.
  - `004_webhook_events.sql`: Webhook idempotency audit log (`webhook_events`).
  - `005_users_auth.sql`: Customer authentication and trial fields (`users`).
  - `006_crawl_sources_skipped.sql`: Source skip metrics in `crawl_runs`.
  - `007_subscription_controls.sql`: Subscription lifecycle columns (`paused_at`, `resumed_at`, `cancelled_at`, `access_until`, `cancel_reason`).
- **Next Migration Number**: `008`.
- **The Schema Parity Test**: `tests/test_schema_contract.py` introspects SQLite tables created by `_init_sqlite_schema()` in `db/repository.py` and scans all files in `db/migrations/*.sql`. If any column is added to SQLite without an identical PostgreSQL migration, the test fails immediately.

---

## 6. Authentication & Access Gating

- **Module**: `api/auth.py`.
- **Password Security**: Passwords hashed with `bcrypt` (12 rounds).
- **JWT Tokens**: Signed using `HS256` with `$SECRET_KEY`.
  - **Admin Token**: Payload contains `{"sub": email, "role": "admin"}`. Verified via `require_admin`.
  - **Customer Token**: Payload contains `{"sub": user_id, "email": email, "role": "customer"}`. Verified via `require_customer` or `get_customer_optional`.
- **Search Gating Enforced In**: `api/main.py:search_documents` (`GET /api/documents`).
  - Evaluates user access via `repo.get_user_access_status(email)`.
  - Returns full results (`is_gated: false`) if user has active trial (`trial_ends_at > now()`) or active subscription (`subscription_status == 'active'` or inside paid cycle after pause/cancellation).
  - Returns gated teasers (`is_gated: true`, excerpt truncated, headline only) if unauthenticated or expired.

---

## 7. Payments & Webhooks

- **Provider**: PayPal REST API (`api/payments/paypal_provider.py`).
- **Subscription Creation**: Initiated via PayPal JavaScript SDK Smart Buttons on frontend (`frontend/index.html`). Embeds customer `user_id` into PayPal's `custom_id` field.
- **Webhook Listener**: `POST /api/webhooks/paypal` (and `/api/payments/webhook`).
  - Webhooks are cryptographically verified using PayPal SDK signature validation against `$PAYPAL_WEBHOOK_ID`.
  - Resolution order: Extracts `custom_id` first to look up the customer in `users`. Falls back to payer email only if `custom_id` is absent. This prevents account mismatch if a customer uses a PayPal account with a different email address.
  - Event Handlers:
    - `BILLING.SUBSCRIPTION.ACTIVATED`: Marks subscription active, sets `resumed_at` if previously paused.
    - `PAYMENT.SALE.COMPLETED`: Extends subscription billing cycle.
    - `BILLING.SUBSCRIPTION.SUSPENDED`: Marks subscription paused, sets `access_until` to `next_billing_at`.
    - `BILLING.SUBSCRIPTION.CANCELLED`: Marks subscription cancelled, sets `access_until` to `next_billing_at`.
- **Plan Immutability**: PayPal subscription plans (`config/plans.json`) cannot have their billing amounts altered on the fly; price changes require creating a new PayPal Plan ID.

---

## 8. Production Deployment & Infrastructure

- **Server**: Linux VPS (Ubuntu 22.04 LTS).
- **Process Manager**: Systemd.
  - `jurismon.service`: Uvicorn process running FastAPI app on port 8000.
  - `jurismon-crawl.service`: One-shot crawler execution script (`scripts/run_crawler.py`).
  - `jurismon-crawl.timer`: Daily systemd timer triggering crawl at 04:00 UTC.
- **Web Server & SSL**: Nginx with Certbot Let's Encrypt automated TLS renewal.
- **Deployment Script**: `scripts/deploy.sh`:
  - Pulls code from remote git repository.
  - Installs Python dependencies (`pip install -r requirements.txt`).
  - Installs Playwright Chromium.
  - Executes database migrations (`python scripts/run_migrations.py`).
  - Reloads systemd daemon and restarts `jurismon.service`.
  - Probes `https://jurismon.com/api/health` to confirm deployment health.

---

## 9. Codebase Directory Map

```
jurismon/
├── api/
│   ├── main.py                     # FastAPI application endpoints, routes, search gating, error handlers
│   ├── auth.py                     # JWT token generation, bcrypt verification, FastAPI security dependencies
│   └── payments/
│       └── paypal_provider.py       # PayPal REST API integration, subscription lifecycle, webhook signature verification
├── config/
│   ├── sites.json                  # Source catalogue: 65 municipal/statutory URLs, adapters, and selectors
│   └── plans.json                  # Commercial subscription plans, prices, intervals, and PayPal Plan IDs
├── crawler/
│   ├── orchestrator.py             # Multi-source crawl queue, concurrency control, adapter resolution
│   ├── crawler.py                  # HTTP request-based scraper with retry logic and error logging
│   ├── playwright_crawler.py       # Headless Chromium crawler for JavaScript-rendered dynamic portals
│   └── adapters/                   # Platform-specific scraping adapters (Granicus, CivicPlus, Municode, REST, XML, Custom)
├── db/
│   ├── client.py                   # Singleton connector managing Supabase client initialization
│   ├── repository.py               # Unified data access layer with dual-branch Supabase/SQLite persistence
│   └── migrations/                 # Numbered SQL migration scripts applied in sequence (001 to 007)
├── deploy/
│   ├── jurismon.service            # Systemd service unit for Uvicorn web application
│   ├── jurismon-crawl.service      # Systemd service unit for automated crawler process
│   ├── jurismon-crawl.timer        # Systemd timer unit scheduling daily crawl at 04:00 UTC
│   └── nginx-jurismon.conf         # Nginx reverse proxy configuration and static routing
├── diff_engine/
│   ├── engine.py                   # Core statutory diff calculator computing added, deleted, and modified text
│   ├── parser.py                   # Structural statutory text parser identifying section (§) and paragraph blocks
│   └── formatter.py                # Visual HTML and JSON diff formatter for frontend rendering
├── extractor/
│   ├── cleaner.py                  # Text normalizer removing municipal boilerplates and repeated headers
│   ├── html_extractor.py           # Boilerpipe-style main content extractor from raw HTML DOM
│   ├── pdf_extractor.py            # Layout-aware PDF text extraction using pypdf and pdfplumber
│   └── ocr.py                      # Tesseract OCR fallback for scanned, low-density image PDFs
├── frontend/
│   ├── index.html                  # Main landing page, Google-style search UI, teaser paywall, PayPal modal
│   ├── admin.html                  # Authenticated admin panel with live operational metrics and crawl controls
│   ├── account.html                # Customer subscription management page (pause, resume, cancel)
│   ├── terms.html                  # Terms of Service legal compliance disclosure
│   └── privacy.html                # Privacy Policy legal compliance disclosure
├── notifications/
│   └── mailer.py                   # Resend API transactional email client for OTP codes and alerts
├── scripts/
│   ├── deploy.sh                   # VPS deployment script: pulls git, runs migrations, restarts services
│   ├── vps_setup.sh                # VPS bootstrap script: firewall, users, system packages, nginx, certbot
│   ├── run_crawler.py              # Standalone CLI entrypoint for daily ingestion runs
│   ├── run_migrations.py           # Migration runner applying unapplied SQL migrations in sequence
│   ├── capture_account_screenshots.py # Playwright screenshot capture script generating verified account states
│   └── generate_admin_hash.py      # Utility generating bcrypt hash for $ADMIN_PASSWORD_HASH
├── tests/                          # 269 automated unit, integration, and schema contract tests
└── .github/workflows/
    └── ci.yml                      # GitHub Actions CI pipeline testing code on push/PR
```
