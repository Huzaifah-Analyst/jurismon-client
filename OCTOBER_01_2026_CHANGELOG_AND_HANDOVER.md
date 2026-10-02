# JurisMon — October 01, 2026 Changelog & Architecture Handover

**Work Completed Date**: October 1, 2026  
**Repository**: JurisMon (`d:\fiverr client\malok mading` / `curtiskelton88/jurismon`)  
**Purpose**: Complete record of all codebase changes, new architectural features, bug fixes, and handover notes for Claude Code / Cloud environment migration.

---

## 1. Executive Summary

On **October 1, 2026**, JurisMon was transformed from a proof-of-concept crawler with open public search into a commercialized, gated SaaS platform with complete customer authentication, email verification code flows, 14-day free trial access control, PayPal webhook auto-activation, crawl execution auditing, and crawler resilience upgrades.

All changes were implemented under strict zero-drift rules, with zero external dependency bloat, backwards-compatible SQLite fallback migrations, and 216 passing automated tests.

---

## 2. Customer Authentication, Email Verification & Access Control (Option A)

### 2.1 The Problem It Solved
Previously, JurisMon had no customer account system or search protection. Anyone visiting `jurismon.com` could perform unlimited searches without paying or signing up. While PayPal subscriptions existed, paying customers received no login credentials or exclusive access.

### 2.2 Complete Flow Architecture
1. **Customer Registration (`POST /api/auth/register`)**:
   - Customer submits Name, Work Email, and Password (min 8 characters).
   - Backend checks that the email is not already registered and verified.
   - Password is salted and hashed using `bcrypt`.
   - A cryptographically random **6-digit confirmation code** is generated.
   - Code expiration is set to 15 minutes (`verification_code_expires_at`).
   - The user is created in the `users` table with `is_active=1` and `is_verified=0`.
   - Transactional email is dispatched to the user's inbox via `Mailer` (`notifications/mailer.py` backed by Resend API).
   - **Privacy & Security**: The API response **never** returns the confirmation code (`dev_code` was removed). The code is exclusively delivered via email.

2. **Email Confirmation Code Screen (`frontend/index.html`)**:
   - As soon as registration succeeds, the modal switches to the `#form-verify` screen.
   - The confirmation code input field (`#verify-code`) is completely blank and focused.
   - The user must open their email inbox, retrieve the 6-digit code, and type/paste it into the input box.
   - A **Resend Code** button (`POST /api/auth/resend-code`) allows dispatching a fresh code if the previous one expired or was lost.

3. **Code Verification & Trial Activation (`POST /api/auth/verify-code`)**:
   - Validates that the submitted 6-digit code matches and has not expired.
   - Sets `is_verified=1`, `verification_code=NULL`, and `verification_code_expires_at=NULL`.
   - Automatically activates a **14-day free trial**:
     - `trial_started_at = now()`
     - `trial_ends_at = now() + 14 days`
   - Issues a JWT Bearer token with 30-day validity containing `{sub: user_id, email, type: "customer"}`.
   - Frontend stores token in `localStorage`, updates the top navigation bar with user email and "Trial" status badge, and refreshes the search.

4. **Direct Login Protection (`POST /api/auth/login`)**:
   - If an unverified user attempts to log in with their password, the backend blocks the request with **HTTP 403 Forbidden**:
     ```json
     {"detail": "Email not confirmed. Please verify your email first.", "status": "verification_required"}
     ```
   - The frontend intercepts this response and immediately redirects the user to the 6-digit verification code form.

5. **Search Gating (`GET /api/search`)**:
   - **Unauthenticated / Unverified visitors**:
     - Receive a maximum of 2 teaser search results.
     - Full clauses and redlines are masked with placeholder text:
       `"[Full statutory diff locked. Start your 14-day free trial to view complete regulatory changes.]"`
     - Response flags `is_gated=true, gate_reason="unauthenticated"`.
     - Frontend displays a green "Start 14-Day Free Trial" banner above results.
   - **Active Trial Customers & Paid Subscribers**:
     - Receive full unmasked search results, clause diffs, and snapshots.
     - Response flags `is_gated=false`.
   - **Expired Trial Users**:
     - Blocked with `is_gated=true, gate_reason="trial_expired"`.
     - Frontend prompts the user with the JurisMon Professional subscription modal ($49/month or $468/year).

6. **PayPal Subscription Auto-Verification (`POST /api/webhooks/paypal`)**:
   - When a PayPal `BILLING.SUBSCRIPTION.ACTIVATED` or `PAYMENT.SALE.COMPLETED` webhook fires:
     - Matches subscriber by email in the `users` table.
     - Extends user access by 30 days (monthly) or 365 days (annual) without manual intervention.

---

## 3. Bug Fix: Verification Code Field Auto-fill

### Bug Description:
During initial local testing, a developer convenience property (`dev_code`) was returning the 6-digit code in the JSON payload, which the frontend script was automatically populating into the `#verify-code` input field upon signup.

### Fix Implemented on Oct 1, 2026:
- **`api/main.py`**: Completely stripped `dev_code` from `customer_register` and `customer_resend_code` responses. The code is only sent to the user's actual email address.
- **`frontend/index.html`**:
  - `showVerifyScreen(email)` now strictly sets `codeInput.value = ""` (always empty).
  - Removed `dev_code` argument and references from register submission and resend callbacks.
- **`tests/test_customer_auth_and_gating.py`**:
  - Updated all test assertions to verify that `dev_code` is NOT returned in API responses (`self.assertNotIn("dev_code", data)`).
  - Tests verify the database-generated code directly via `repo.get_user_by_email()`.

---

## 4. Detailed Breakdown of Files Touched & Changes Made

### 1. `db/repository.py`
- **Added `users` Table Migration**:
  - Columns: `id`, `email`, `password_hash`, `full_name`, `trial_started_at`, `trial_ends_at`, `is_active`, `is_verified`, `verification_code`, `verification_code_expires_at`, `created_at`, `updated_at`.
  - Added safe column migration in SQLite fallback (`_init_sqlite_schema`) to automatically alter existing tables without data loss.
- **Added User Methods**:
  - `create_user()`
  - `set_verification_code()`
  - `verify_user_email()`
  - `get_user_by_email()`
  - `get_user_by_id()`
  - `get_user_access_status()` (evaluates active trial and active subscription status).
- **Added Crawl Execution Tracking**:
  - `start_crawl_run()`: Inserts run with status `running` and `started_at`.
  - `finish_crawl_run()`: Updates status (`completed`, `partial_failure`, `failed`), counts, and error logs.
- **Added Error Logging**:
  - Enhanced error capture to persist failed source details and stack traces.

### 2. `api/auth.py`
- Added customer JWT utilities:
  - `create_customer_token()`: Signs HS256 tokens with customer claims.
  - `get_current_customer_optional()`: Extracts customer identity from Bearer token if present, returns `None` for anonymous callers without throwing 401.
  - `require_customer()`: Strict dependency enforcing authenticated customer identity.

### 3. `api/main.py`
- Added customer authentication endpoints:
  - `POST /api/auth/register`: Creates unverified customer, generates 6-digit code, emails code via `Mailer`.
  - `POST /api/auth/verify-code`: Verifies 6-digit code, activates 14-day trial, issues JWT token.
  - `POST /api/auth/resend-code`: Dispatches fresh 6-digit code.
  - `POST /api/auth/login`: Authenticates customer; blocks unverified accounts with 403.
  - `GET /api/auth/me`: Returns customer profile and access status.
- Added Favicon endpoint:
  - `GET /favicon.ico`: Serves `frontend/assets/favicon.ico` with `image/x-icon` media type.
- Updated `GET /api/search`:
  - Evaluates `customer` via `get_current_customer_optional`.
  - Teaser restriction (2 results, masked clauses) for unauthenticated or expired visitors.
  - Full search access for active trial or paid subscribers.
- Updated `POST /api/webhooks/paypal`:
  - Automatically matches subscriber email and grants access in `users` table.

### 4. `frontend/index.html`
- **Favicon Links**: Added `/static/assets/favicon.ico` and `/favicon.ico` in `<head>`.
- **Top Navigation**:
  - Unauthenticated view: "Log In" button and "Start 14-Day Free Trial" button.
  - Authenticated view: User email, status badge ("Trial" or "Active"), and "Sign Out" button.
- **Gate Banner**:
  - Informs visitors when search is in preview mode with 1-click trial starter.
- **Authentication Modal (`#auth-modal`)**:
  - Tab 1: Start 14-Day Free Trial (Name, Email, Password).
  - Tab 2: Log In (Email, Password).
  - Verification Screen (`#form-verify`): 6-digit code entry with Resend Code link. Input is always blank.
- **Paywall Modal (`#paywall-modal`)**:
  - Displays JurisMon Professional plans:
    - Monthly: $49/mo
    - Annual: $468/yr ($39/mo, Save 20%)
  - PayPal subscription checkout triggers.

### 5. `crawler/` and `scripts/` (Tasks 1b, 2, 3, 4, 5)
- **`crawler/adapters/rest_api.py` & `crawler/adapters/xml_feed.py`**: Added support for structured municipal endpoints (Task 1b).
- **`crawler/session.py` & `crawler/orchestrator.py`**: Integrated configurable user-agents, concurrency, and polite crawl delays from environment variables (Task 2).
- **`scripts/run_crawler.py`**: Integrated `start_crawl_run()` and `finish_crawl_run()` to audit every scheduled crawl (Task 4).
- **`crawler/base.py` & `diff_engine/models.py`**: Cleaned dead functions (`compute_hash`, unused `to_dict`) (Task 5).
- **`.env.example`**: Cleaned unused settings and clarified PayPal plan configuration references.

### 6. `tests/`
- Added `tests/test_customer_auth_and_gating.py`:
  - Comprehensive coverage for registration, code dispatch, trial activation, unverified login blocking, expired trial gating, PayPal webhook unblocking, profile endpoint, and favicon serving.
- All 216 test cases in the suite pass cleanly (`pytest tests/ -q`).

---

## 5. Deployment Instructions for Claude Code / VPS

When running on VPS (`jurismon.com`):
1. **Supabase Migration**: Run the equivalent SQL in Supabase SQL Editor if connecting to Supabase:
   ```sql
   CREATE TABLE IF NOT EXISTS users (
       id TEXT PRIMARY KEY,
       email TEXT UNIQUE NOT NULL,
       password_hash TEXT NOT NULL,
       full_name TEXT,
       trial_started_at TIMESTAMPTZ,
       trial_ends_at TIMESTAMPTZ,
       is_active INTEGER DEFAULT 1,
       is_verified INTEGER DEFAULT 0,
       verification_code TEXT,
       verification_code_expires_at TIMESTAMPTZ,
       created_at TIMESTAMPTZ DEFAULT NOW(),
       updated_at TIMESTAMPTZ DEFAULT NOW()
   );
   ```
2. **Environment Variables**: Ensure `RESEND_API_KEY` is present in `/etc/jurismon/jurismon.env` (or project `.env`) so transactional emails deliver to real inboxes.
3. **Restart Service**:
   ```bash
   sudo systemctl restart jurismon-api
   ```
