# JurisMon - Municipal Zoning & Statutory Delta Monitor

JurisMon is a production-grade statutory monitoring pipeline that tracks municipal and county zoning board websites daily, pulls PDF notices and meeting minutes, extracts and cleans text, detects added/removed statutory clauses (§ sections and paragraphs), and provides instant full-text search and subscription management.

---

## 🏛️ Architecture Overview

```
jurismon/
├── config/              # sites.json source catalogue (65 sources) & default selectors
├── crawler/             # Requests & Playwright crawlers with modular platform adapters
│   └── adapters/        # REST API, XML/Atom, direct-document, Municode,
│                        # Granicus Legistar, CivicPlus and Custom adapters
├── extractor/           # Layout-aware PDF/HTML extraction, boilerplate cleaner & Tesseract OCR
├── diff_engine/         # Section (§ / Section X.X) & paragraph-level diffing engine
├── db/                  # PostgreSQL / Supabase schema migrations and data access layer
├── api/                 # FastAPI search endpoint & Admin PayPal subscription manager
├── frontend/            # Google-style search UI & Admin dashboard
├── scripts/             # Daily crawl orchestrator & VPS hardening scripts
├── tests/               # 105 automated unit & integration tests across the stack
└── .github/workflows/   # Scheduled GitHub Actions daily ingestion workflow
```

---

## 🚀 Quickstart (Local Development)

### 1. Prerequisites
- Python 3.12 (the pinned dependency set is verified against 3.12)
- A Supabase project (the app falls back to local SQLite without one)
- Tesseract OCR, required for scanned PDFs

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/your-username/jurismon.git
cd jurismon

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
playwright install chromium
```

### 3. Environment Configuration
```bash
cp .env.example .env
```

Then set the following. In production (`APP_ENV=production`) the app refuses to
start unless `SECRET_KEY` and `ADMIN_PASSWORD_HASH` are present - there are no
insecure defaults.

| Variable | Required | Notes |
|---|---|---|
| `APP_ENV` | yes | `development` locally, `production` on the VPS |
| `SECRET_KEY` | production | JWT signing key. `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `ADMIN_PASSWORD_HASH` | production | bcrypt hash, never a plaintext password (see below) |
| `ADMIN_EMAIL` | yes | Admin dashboard login address |
| `CORS_ALLOWED_ORIGINS` | production | Comma-separated origins. Never `*` |
| `SUPABASE_URL` / `SUPABASE_KEY` | yes | Service role key. Without these the app uses local SQLite |
| `PAYPAL_MODE` | yes | `sandbox` or `live` |
| `PAYPAL_CLIENT_ID` / `PAYPAL_CLIENT_SECRET` | yes | From developer.paypal.com |
| `PAYPAL_WEBHOOK_ID` | yes | Signature verification **fails closed** without it - every webhook is rejected |
| `PAYPAL_PLAN_ID` | yes | The subscription plan to sell |

Generate the admin password hash:
```bash
python scripts/generate_admin_hash.py
```
This prints a strong password and its bcrypt hash. Store the password in a
password manager and put only the hash in `.env`.

### 4. Run Migrations
Execute the SQL migration scripts in your Supabase SQL editor or Postgres CLI:
1. `db/migrations/001_initial_schema.sql`
2. `db/migrations/002_subscriptions.sql`

### 5. Run Unit Tests
```bash
python -m pytest tests/ -v
```

All 105 tests run offline - no network, browser or database is required.

### 6. Start the Web App & Search API
```bash
uvicorn api.main:app --reload --port 8000
```
- **Search Page:** `http://localhost:8000/`
- **Admin Dashboard:** `http://localhost:8000/admin`
- **API Documentation:** `http://localhost:8000/docs`

---

## 🤖 Daily Ingestion & Diffing Pipeline

Run the crawler CLI manually or via cron:
```bash
python scripts/run_crawler.py
```

### Pipeline Flow:
1. **Discovery:** Iterates over active sources in `config/sites.json`, routing each
   to its adapter (`rest_api`, `xml`/`atom`, `direct_document`, `municode`,
   `granicus`, `civicplus` or `custom`). The `custom` adapter falls back to the
   Playwright stealth browser when static parsing returns nothing.
2. **Hash Check:** Computes SHA-256 hash of each document; skips unchanged files.
3. **Extraction & Cleaning:** Strips repeating headers/footers and boilerplate disclaimers. Scanned documents trigger OCR fallback.
4. **Diffing:** Compares the new snapshot against the previous version by § sections (or paragraphs), producing structured JSON deltas (`added`, `removed`, `modified`).
5. **Indexing:** Updates PostgreSQL `tsvector` full-text search indexes.

---

## 🗂️ Source Catalogue

`config/sites.json` is the operational source of truth. Each entry carries an
`is_active` flag plus a `health_status` recording why an inactive source is
parked, so nothing is silently dropped.

| health_status | Count | Meaning |
|---|---|---|
| `operational` | 41 | Crawled on every run |
| `dead_link` | 12 | 404 or expired DNS at the municipality; awaiting replacement URLs |
| `cloudflare_blocked` | 7 | Behind CAPTCHA/Turnstile; out of scope per the agreed brief |
| `unreachable` | 3 | Connection timeouts during audit; retry from the VPS |
| `blocked_403` | 1 | Rejects automated clients |
| `auth_required` | 1 | Needs an API key the publisher must issue |

To add a source, append an entry and pick the adapter that matches its delivery
format. No code change is needed for a source on an already-supported platform.

---

## 💳 PayPal & Subscriptions Integration

JurisMon comes with a pluggable subscription management layer (`api/payments/`):
- **PayPal Provider:** Integrated with PayPal Subscriptions API & webhooks.
- **Stripe Provider:** Plug-and-play interface for future activation.

---

## 🔒 VPS Deployment & Security Hardening

To provision a fresh Ubuntu 24.04 LTS server:
```bash
chmod +x scripts/vps_setup.sh
sudo ./scripts/vps_setup.sh
```
This script automatically:
- Configures UFW firewall (allowing only SSH, HTTP, HTTPS)
- Installs and enables `fail2ban`
- Sets up an isolated `jurismon` application user
- Installs Python 3, Tesseract OCR, and Nginx reverse proxy
