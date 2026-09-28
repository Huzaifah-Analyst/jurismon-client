# JurisMon - Municipal Zoning & Statutory Delta Monitor

JurisMon is a production-grade statutory monitoring pipeline that tracks municipal and county zoning board websites daily, pulls PDF notices and meeting minutes, extracts and cleans text, detects added/removed statutory clauses (§ sections and paragraphs), and provides instant full-text search and subscription management.

---

## 🏛️ Architecture Overview

```
jurismon/
├── config/              # Per-site YAML configs (50 municipal sources) & default selectors
├── crawler/             # Requests & Playwright crawlers with modular platform adapters
│   └── adapters/        # Municode, Granicus Legistar, CivicPlus, Custom adapters
├── extractor/           # Layout-aware PDF/HTML extraction, boilerplate cleaner & Tesseract OCR
├── diff_engine/         # Section (§ / Section X.X) & paragraph-level diffing engine
├── db/                  # PostgreSQL / Supabase schema migrations and data access layer
├── api/                 # FastAPI search endpoint & Admin PayPal subscription manager
├── frontend/            # Google-style search UI & Admin dashboard
├── scripts/             # Daily crawl orchestrator & VPS hardening scripts
├── tests/               # Automated unit tests for diff engine and text cleaning
└── .github/workflows/   # Scheduled GitHub Actions daily ingestion workflow
```

---

## 🚀 Quickstart (Local Development)

### 1. Prerequisites
- Python 3.10+
- PostgreSQL or Supabase account
- (Optional for scanned PDFs) Tesseract OCR

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
Copy `.env.example` to `.env` and fill in your Supabase credentials:
```bash
cp .env.example .env
```

### 4. Run Migrations
Execute the SQL migration scripts in your Supabase SQL editor or Postgres CLI:
1. `db/migrations/001_initial_schema.sql`
2. `db/migrations/002_subscriptions.sql`

### 5. Run Unit Tests
```bash
python -m unittest discover -s tests -p "test_*.py"
```

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
1. **Discovery:** Iterates over configured sources in `config/sites.yaml`.
2. **Hash Check:** Computes SHA-256 hash of each document; skips unchanged files.
3. **Extraction & Cleaning:** Strips repeating headers/footers and boilerplate disclaimers. Scanned documents trigger OCR fallback.
4. **Diffing:** Compares the new snapshot against the previous version by § sections (or paragraphs), producing structured JSON deltas (`added`, `removed`, `modified`).
5. **Indexing:** Updates PostgreSQL `tsvector` full-text search indexes.

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
