# JurisMon - Project Specification & Architecture

**Domain:** `jurismon.com`  
**Target Delivery:** 7 Days (Deadline: approx. 4 Oct 2026)  
**Order Scope:** 50 municipal URLs monitor, PDF/HTML text extraction + OCR fallback, Supabase schema + migrations, Section/Paragraph diff engine, Google-style Search frontend, Admin panel for payments/subscriptions (PayPal first, pluggable for Stripe), GitHub Actions workflow.

---

## 1. Directory Structure

```
jurismon/
├── .github/
│   └── workflows/
│       └── daily_crawl.yml          # GitHub Actions scheduled workflow
├── config/
│   ├── sites.yaml                   # 50 target site configs (URL, adapter, selectors)
│   └── default_selectors.yaml       # Platform defaults (Municode, Granicus, CivicPlus, etc.)
├── crawler/
│   ├── __init__.py
│   ├── base.py                      # BaseCrawler abstract class with polite delays & retries
│   ├── requests_crawler.py          # Fast HTTP/BS4 crawler for static portals
│   ├── playwright_crawler.py        # Headless browser crawler for dynamic JS portals
│   └── adapters/                    # Platform adapters
│       ├── __init__.py
│       ├── municode.py              # Municode portal adapter
│       ├── granicus.py              # Granicus Legistar adapter
│       ├── civicplus.py             # CivicPlus agenda adapter
│       └── custom.py                # Generic custom HTML/PDF link scraper
├── extractor/
│   ├── __init__.py
│   ├── pdf_extractor.py             # PyMuPDF / pdfplumber layout-aware extractor
│   ├── html_extractor.py            # Clean text from HTML notices
│   ├── cleaner.py                   # Strips repeating headers/footers, page numbers, disclaimers
│   └── ocr.py                       # Tesseract OCR fallback for scanned PDFs
├── diff_engine/
│   ├── __init__.py
│   ├── section_splitter.py          # Breaks text into § and Section X.X hierarchy
│   ├── engine.py                    # Section diffing with paragraph fallback
│   └── models.py                    # Structured JSON diff models (added/removed/modified)
├── db/
│   ├── migrations/
│   │   ├── 001_initial_schema.sql   # Sources, documents, snapshots, diffs, crawl_runs
│   │   └── 002_subscriptions.sql   # Subscriptions, users, payments, webhook events
│   ├── __init__.py
│   ├── client.py                    # Supabase / Postgres connection pool
│   └── repository.py                # Data access layer
├── api/
│   ├── __init__.py
│   ├── main.py                      # FastAPI app serving Search API & Admin endpoints
│   ├── auth.py                      # Admin JWT authentication
│   ├── search.py                    # Postgres tsvector full-text search router
│   ├── admin.py                     # Subscriptions and system status router
│   └── payments/
│       ├── base.py                  # Pluggable PaymentProvider interface
│       ├── paypal_provider.py       # PayPal Subscriptions API & Webhook handler
│       └── stripe_provider.py       # Pluggable Stripe skeleton for future activation
├── frontend/
│   ├── index.html                   # Minimalist Google-style Search Page
│   ├── admin.html                   # Clean Admin Panel for Subscriptions & Payments
│   ├── css/
│   │   └── style.css
│   └── js/
│       ├── search.js
│       └── admin.js
├── scripts/
│   ├── run_crawler.py               # Main CLI orchestrator for daily crawl & diffing
│   ├── vps_setup.sh                 # VPS provisioning & hardening script
│   └── test_site.py                 # Single site tester utility
├── tests/
│   ├── test_diff_engine.py          # Section & paragraph diff unit tests
│   ├── test_extractor.py            # Text cleaning & boilerplate removal tests
│   ├── test_crawler.py              # Mocked adapter tests
│   └── fixtures/                    # Sample PDFs and HTML fixtures
├── docs/
│   ├── CHAT_LOG.md
│   ├── DRAFTED_MESSAGES.md
│   ├── COMMUNICATION_GUIDELINES.md
│   └── PROJECT_SPEC.md
├── .env.example
├── requirements.txt
└── README.md
```

---

## 2. Database Schema (PostgreSQL / Supabase)

1. **`sources`**: 50 monitored municipal entities (name, state, base_url, adapter_type, selector_config).
2. **`documents`**: Tracked documents (title, source_id, document_type, pdf_url, content_hash, last_crawled_at).
3. **`snapshots`**: Versioned snapshots (document_id, raw_text, cleaned_text, hash, crawled_at, version).
4. **`diffs`**: JSON deltas (previous_snapshot_id, current_snapshot_id, added_clauses, removed_clauses, modified_clauses, generated_at).
5. **`crawl_runs`**: Crawl execution logs (run_id, started_at, finished_at, sites_succeeded, sites_failed, error_logs).
6. **`users` / `subscriptions` / `payments`**: User auth, subscription status (`active`, `cancelled`, `past_due`), and PayPal transaction logs.
