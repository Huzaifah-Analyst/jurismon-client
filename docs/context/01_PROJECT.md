# Project Scope, Commercial Architecture & Client Context

## Product Definition & Target Audience
JurisMon is an automated regulatory intelligence platform tailored for municipal attorneys, urban planners, land developers, and municipal research teams. Local governments in North America and statutory bodies in the UK frequently enact amendments to zoning ordinances, building codes, and land-use bylaws without issuing centralized alerts. JurisMon monitors these portals, captures statutory texts, detects changes via automated text differencing, and makes historical regulatory deltas searchable.

---

## Original Contract Brief: The 8 Deliverables
The project contract established eight core technical milestones documented in [docs/client/project-spec.md](../client/project-spec.md):

1. **50 Municipal URLs Monitored**: Crawling across municipal and county planning and zoning portals.
2. **Document & Text Extraction Pipeline**: Ingestion of PDF and HTML documents with OCR fallback (via Tesseract) for scanned documents.
3. **Database Architecture & Schema Migrations**: Relational persistence using PostgreSQL (hosted on Supabase) with automated versioned SQL migrations.
4. **Regulatory Diff Engine**: Section- and paragraph-level diffing calculating additions, deletions, and modifications between statutory snapshots.
5. **Search Interface**: A Google-style responsive web interface providing full-text search with highlight snippets across documents and diffs.
6. **Administrative Dashboard & Subscriptions**: An authenticated admin dashboard for source monitoring and subscription processing (pluggable architecture supporting PayPal and Stripe).
7. **Daily Automated Crawl Scheduling**: Automatic daily crawl triggers to fetch, parse, and diff updated ordinances.
8. **Production Deployment**: Deployment and configuration on the client's Linux VPS with TLS encryption.

---

## Additions Delivered Beyond the Brief
During development, the core platform was expanded significantly beyond the original eight deliverables. These additions were not decorative scope creep; each was strictly necessary to make the product functionally viable and commercially operable in a live environment:

1. **Customer Accounts & JWT Authentication** (`api/auth.py`, commit `e58817c`):
   - *Why necessary*: The original brief specified paywalling content, but without persistent user identity, access cannot be attached to a specific person or license. Email/password authentication using bcrypt hashing and JWT bearer tokens was implemented to enable individual access management.
2. **Email Verification via 6-Digit Code** (`notifications/mailer.py`, `api/main.py:270-345`, commits `e58817c`, `74172a1`):
   - *Why necessary*: An open registration form allowing immediate trial access would be trivially exhausted by automated bots or disposable email spam. Integrating transactional email dispatch via the Resend API with a 6-digit confirmation code ensures that every created trial corresponds to a reachable email address.
3. **14-Day Free Trial & Search Gating** (`frontend/index.html:700-850`, `api/main.py:180-260`, commit `e58817c`):
   - *Why necessary*: Pure public search would give away the entire database for free, while an immediate hard paywall prevents prospective users from evaluating search quality. Search results provide gated teasers (headline match visible, full text locked behind an upgrade banner) until an account enters an active trial or paid subscription.
4. **Automated PayPal Subscription Webhook Integration** (`api/payments/paypal_provider.py:46-135`, commit `315e8c7`):
   - *Why necessary*: The client chose PayPal as the exclusive payment processor for launch. Without automated webhook processing (`BILLING.SUBSCRIPTION.ACTIVATED`, `PAYMENT.SALE.COMPLETED`, `BILLING.SUBSCRIPTION.CANCELLED`), the client would have had to manually inspect PayPal emails and manually edit the database to activate each customer.
5. **Self-Service Password Reset** (`api/main.py:350-410`, commit `74172a1`):
   - *Why necessary*: Once customer accounts exist, users inevitably forget credentials. Without an automated reset flow (utilizing timed 6-digit reset codes sent via email), every forgotten password would become an administrative support ticket requiring manual database modification.
6. **Legal Compliance Pages (`/terms` and `/privacy`)** (`frontend/terms.html`, `frontend/privacy.html`, commits `fe81512`, `9b8d1ae`):
   - *Why necessary*: Payment gateways (PayPal) and data privacy regulations (GDPR/CCPA) legally prohibit operating a subscription service and collecting user emails without accessible Terms of Service and Privacy Policy disclosures.
7. **Catalog Expansion from 51 to 65 Sources** (`config/sites.json`, commit `49a599b`):
   - *Why necessary*: Auditing the initial list revealed dead municipal links and Cloudflare blocks. Adding 14 additional municipal targets ensured the contracted delivery threshold was met and delivered broader regional coverage across major US metro areas and UK planning authorities.
8. **Production Hardening & Systemd Crawl Lock Recovery** (`api/main.py:1130-1170`, `db/repository.py:650-700`, commit `6a22bd1`):
   - *Why necessary*: In production, crawls can stall due to unresponsive municipal servers. If a crawl stalled without automatic cleanup, the entire crawler would lock forever. Automatic detection of stale runs (>2 hours), automated lock release, and offloading execution to systemd service units ensured high availability.

---

## Commercial Model & Access Lifecycle

### Subscription Tiers
Defined in [config/plans.json](../../config/plans.json):
- **14-Day Free Trial**: Automatically attached to every new account upon email verification.
- **Professional Monthly**: $49.00 / month (PayPal Plan ID: `P-09H67919864276135NHBHYUI`).
- **Professional Annual**: $468.00 / year (equivalent to $39/mo, 20% discount; PayPal Plan ID: `P-5G6438883W139580UNHBHY7A`).

### Access State Machine
Customer authorization (`api/auth.py:require_customer` and `api/main.py:search_documents`) resolves access through four distinct states:
1. **Active Trial**: `trial_ends_at > now()`. Full search queries, snippet inspection, and diff viewing are unlocked.
2. **Expired Trial**: `trial_ends_at <= now()` and `subscription_status != 'active'`. Search results return truncated snippets with an upgrade modal prompt. Access to diff details is gated with HTTP 403 / upgrade payload.
3. **Active Subscriber**: `subscription_status == 'active'` (activated via PayPal webhook). Full platform access is unlocked.
4. **Cancelled / Suspended**: Webhook receives `BILLING.SUBSCRIPTION.CANCELLED` or `SUSPENDED`. `subscription_status` is updated to `'cancelled'`; access terminates at the conclusion of the paid billing cycle.

---

## Client Profile & Core Objectives
- **Client**: Malok Mading.
- **Commercial Focus**: Regulatory diligence and legal compliance tracking for local government statutory amendments.
- **Stated Client Priorities**:
  - Uncompromising operational accuracy: The client places high value on real metrics over fabricated vanity numbers. Discrepancies between advertised source health and actual crawler logs are treated as critical issues.
  - Source coverage integrity: Tracking major North American metropolitan counties (e.g., Cook County, Maricopa County, LA County) and UK statutory instruments.
  - Zero manual operational overhead: Automated daily crawls, automatic subscription lifecycle processing, and self-service customer registration.
