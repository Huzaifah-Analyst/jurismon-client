# JurisMon — Outstanding Items Required From Client

**Status date:** 28 Sep 2026
**Purpose:** Consolidated list of everything still needed from Malok to move JurisMon from a working local build to a live, deployed, revenue-collecting system.

> **Note on sequencing:** Nothing in this document blocks current backend work. All core engine fixes and hardening proceed independently. These items are required for **deployment and go-live only**.

---

## ✅ Already Received — No Action Needed

| Item | Detail | Received |
|---|---|---|
| Target URLs (Batch 1) | 51 municipal / county sources | 26 Sep |
| Target URLs (Batch 2) | 18 structured API / Atom / OpenData portals | 28 Sep |
| VPS access | Hostinger VPS, root SSH | 26 Sep |
| Domain | `jurismon.com` (registered via Cloudflare) | 26 Sep |
| Brand asset | Official JurisMon logo | 26 Sep |
| Payment provider decision | PayPal (Stripe deferred — not available in South Sudan) | 26 Sep |
| UI direction | Google-style clean single search box | 28 Sep |

---

## 🔴 BLOCKING GO-LIVE — Required

### 1. PayPal Business Account + Live API Credentials

A **PayPal Business** account with Developer API access is required. Personal accounts cannot issue subscription APIs.

Please provide, **in an attached file (not typed in chat):**

| Variable | Where to find it |
|---|---|
| `PAYPAL_CLIENT_ID` | developer.paypal.com → Apps & Credentials → **Live** tab → your app |
| `PAYPAL_CLIENT_SECRET` | Same screen, "Secret" → Show |
| `PAYPAL_WEBHOOK_ID` | Same app → Webhooks → Add webhook (see URL below) → copy the Webhook ID |
| `PAYPAL_PLAN_ID` | Created once pricing is confirmed (item 2) |

**Webhook URL to register:** `https://jurismon.com/api/webhooks/paypal`

**Events to subscribe to** (select exactly these):
- `BILLING.SUBSCRIPTION.ACTIVATED`
- `BILLING.SUBSCRIPTION.CANCELLED`
- `BILLING.SUBSCRIPTION.SUSPENDED`
- `BILLING.SUBSCRIPTION.EXPIRED`
- `PAYMENT.SALE.COMPLETED`

> If preferred, sandbox credentials can be sent first so the full payment flow is demonstrated and approved before live keys are issued.

---

### 2. Subscription Pricing Decisions

The PayPal subscription plan cannot be created until these are confirmed:

- [ ] **Price per billing cycle** (e.g. $29)
- [ ] **Currency** (e.g. USD)
- [ ] **Billing interval** — monthly or annual?
- [ ] **Trial period** — earlier message mentioned "subscriptions 7 days." Please confirm whether this means a **7-day free trial**, or a **7-day billing cycle**.
- [ ] **Tiers** — single plan, or multiple tiers at launch?

---

### 3. Supabase Project

Earlier agreement: *"Supabase project access (or I can create a fresh one)."* Please confirm which:

**Option A — You provide an existing project.** Then send:
- `SUPABASE_URL`
- `SUPABASE_KEY` (service role key — **not** the anon/public key)
- `DATABASE_URL` (Postgres connection string)

**Option B — We create it** under a project account and transfer ownership to you at handover. *(Recommended — faster, and avoids key-sharing back and forth.)*

---

### 4. GitHub Repository

Earlier agreement: *"GitHub repo access (or I can create one and transfer it)."*

Required because the **daily automated crawl runs on GitHub Actions** — without a repository, the scheduled ingestion cannot run at all.

**Option A — Your repo.** Provide the repo URL and grant collaborator access to the delivery account.
**Option B — We create it** and transfer ownership to you at handover. *(Recommended.)*

Either way, please confirm the **GitHub username or organization** that should own the final repository.

---

### 5. Cloudflare DNS Access

The domain is registered but must point to the VPS before the site is reachable.

**Either:**
- Add an `A` record yourself: `jurismon.com` → *(VPS IP already on file)*, proxy enabled — **or**
- Invite the delivery account to the Cloudflare zone as a **DNS-only member**

Full account access is not required.

---

### 6. Admin Panel Credentials

The admin dashboard needs an owner login.

- [ ] **Admin email** — confirm `admin@jurismon.com`, or specify another
- [ ] **Password** — either send a chosen password in the credentials file, **or** we generate a strong one, deploy with it, and you change it on first login *(recommended)*

---

## 🟠 SECURITY — Action Required

### 7. VPS Root Password Rotation

The VPS root password was shared in plain text over Fiverr chat. As a standard hardening step before the server is exposed publicly, this **must be rotated**.

Planned approach (no action needed from you unless you object):
1. Rotate the root password on the VPS
2. Install SSH key-based authentication
3. Disable password-based SSH login entirely
4. New credentials delivered to you via a secure channel

Please confirm you are happy for this to proceed.

---

### 8. Confirm VPS Operating System

Setup guidance specified **Ubuntu 24.04 LTS**. Please confirm which Ubuntu version was actually installed, so the provisioning script targets the correct package versions.

---

## 🟡 MINOR — Needed Before Launch

### 9. Contact Email for Crawler Identification

The crawler identifies itself politely to municipal servers with a contact address (current placeholder: `research@jurismon.com`). This is standard practice and reduces the chance of being blocked.

- [ ] Confirm this mailbox will exist, **or** provide an alternative monitored address.

---

## Summary Checklist

| # | Item | Priority | Blocks |
|---|---|---|---|
| 1 | PayPal live API credentials | 🔴 | Payments |
| 2 | Subscription pricing decisions | 🔴 | Payments |
| 3 | Supabase project decision | 🔴 | Production database |
| 4 | GitHub repo decision | 🔴 | Automated daily crawl |
| 5 | Cloudflare DNS record | 🔴 | Public site access |
| 6 | Admin login credentials | 🔴 | Admin panel |
| 7 | Approve root password rotation | 🟠 | Server security |
| 8 | Confirm Ubuntu version | 🟠 | Provisioning |
| 9 | Crawler contact email | 🟡 | Polite crawling |

**Fastest path:** Items 3, 4 and 6 can be unblocked immediately by choosing the "we create it and transfer" option. That leaves only PayPal credentials, pricing, and the DNS record as genuine dependencies on your side.

---

> ⚠️ **Handling note:** Please send all credentials as an **attached file**, never typed directly into chat.
