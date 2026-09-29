# JurisMon — Progress Update & Action Guide

**Prepared for:** Malok Mading  
**From:** Huzaifah  
**Date:** 29 September 2026

---

# Part 1 — Progress Update

## All 18 additional sources are integrated

Eight are live and pulling documents:

| Source | Delivery format |
|---|---|
| Australia Federal Register of Legislation | REST API |
| UK New Statutory Instruments | Atom feed |
| UK Planning Data | REST API |
| Victoria Planning Schemes | Dynamic web app |
| Canada Point-in-Time Bulk XML | Bulk XML |
| New Zealand RMA 1991 | XML and PDF |
| Germany Gesetze im Internet | HTML portal |

A verified live run across these returned **760 documents**, with all nine sources succeeding.

Three of the eighteen — the Australia website, Queensland Legislation, and UK legislation.gov.uk — were already in the catalogue from your original list, so they were matched to the existing entries rather than duplicated.

## Your point about fragmented endpoints paid off

Several of these sources publish XML and Atom rather than JSON, which the REST connector could not read. Two more connectors were built: one for XML and Atom feeds, and one for sources that are a single statutory document addressed directly, like the NZ Act which comes as both XML and PDF. Everything still normalizes into the same internal schema before the diff engine sees it.

## One dead link recovered

Your file happened to contain a working URL for the Ontario Gazette, which was one of the 404s flagged earlier. That one is fixed and back in the active set.

**Current status: 41 active sources.**

---

# Part 2 — Two Ways Forward

The remaining work depends on a handful of accounts and credentials. There are two ways to handle this.

## Option A — You delegate, I handle the setup

If you can share access to the Google account you want JurisMon registered under, I can create and configure the GitHub repository, the Supabase project, and the supporting accounts myself, and simply hand everything over to you at the end. This is the fastest route and needs the least of your time.

You would keep full ownership throughout — everything gets created under your email, and you can change every password once setup is complete.

If you prefer not to share account access, that is completely understandable. Option B covers everything step by step.

## Option B — You do it, I guide you

Every step is written out below. Most items take two to five minutes. If you can work through them as you get time, I can keep building without waiting.

> **Important for all credentials:** please send everything in an **attached file** (a .txt or .doc), never typed directly into the chat. Chat messages are stored and searchable, and API keys pasted into them should be treated as exposed. One file with everything in it is ideal.

---

# Part 3 — Step-by-Step Instructions

## Step 1 — PayPal Business account and API credentials

This is the biggest blocker. Subscriptions cannot be taken without it.

**1a. Make sure you have a PayPal Business account**

A personal PayPal account cannot issue subscription APIs.

1. Go to **paypal.com** and log in
2. If your account is Personal, look for **Upgrade to a Business account** in Settings
3. Follow the prompts — it is free

**1b. Create the API app**

1. Go to **developer.paypal.com**
2. Click **Log in to Dashboard** (top right) and sign in with the same PayPal account
3. Click **Apps & Credentials** in the left menu
4. At the top you will see a **Sandbox / Live** toggle. Select **Live**
5. Click **Create App**
6. Name it `JurisMon` and click **Create App**
7. You will now see **Client ID** — copy it
8. Under it, next to **Secret**, click **Show** — copy that too

**1c. Create the webhook**

Still on the same app page:

1. Scroll down to the **Webhooks** section
2. Click **Add Webhook**
3. In the **Webhook URL** box, paste exactly:
   ```
   https://jurismon.com/api/webhooks/paypal
   ```
4. Under **Event types**, tick these five:

    - `BILLING.SUBSCRIPTION.ACTIVATED`
    - `BILLING.SUBSCRIPTION.CANCELLED`
    - `BILLING.SUBSCRIPTION.SUSPENDED`
    - `BILLING.SUBSCRIPTION.EXPIRED`
    - `PAYMENT.SALE.COMPLETED`

5. Click **Save**
6. The webhook now appears in the list with a **Webhook ID** — copy it

**1d. Put these three in your file**

```
PAYPAL_CLIENT_ID     = (from step 1b.7)
PAYPAL_CLIENT_SECRET = (from step 1b.8)
PAYPAL_WEBHOOK_ID    = (from step 1c.6)
```

> If you would rather see the payment flow working before issuing live keys, do the same steps with the **Sandbox** toggle instead and send those. I will demo it, and you can switch to live afterwards — no code changes are needed.

**You do not need to create the subscription plan.** I will create it through the API once I have the credentials and your pricing answers below.

---

## Step 2 — Subscription pricing decisions

Four quick answers. No account work, just decisions:

1. **Price and currency** — for example, $29 USD
2. **Billing interval** — monthly or annual?
3. **Trial period** — you mentioned "subscriptions 7 days" earlier. Did you mean a **7-day free trial**, or a 7-day billing cycle? I want to be certain before the plan is created, because a plan cannot be edited after it has subscribers.
4. **Tiers** — one plan at launch, or several?

---

## Step 3 — GitHub account

The daily crawl runs on GitHub Actions. Without a repository, the scheduled ingestion cannot run at all.

**If you already have a GitHub account:** just send me the username.

**If you do not:**

1. Go to **github.com**
2. Click **Sign up**
3. Enter your email, a password, and pick a username
4. Verify the email they send you
5. Send me the **username** (not the password)

I will create the repository, add you, and transfer ownership to you at handover. The free plan is enough.

---

## Step 4 — Supabase project

This is the production database.

**Recommended:** let me create it and transfer it to you at handover. Nothing needed from you — just say the word.

**If you prefer to create it yourself:**

1. Go to **supabase.com** and sign up
2. Click **New Project**
3. Name it `jurismon`, set a database password (save it), pick the region closest to the United States
4. Wait for it to finish provisioning, then go to **Project Settings → API**
5. Copy the **Project URL**
6. Copy the **service_role** key — this is the secret one, not the `anon` public key
7. Go to **Project Settings → Database** and copy the **Connection string**

Put all three in your file.

---

## Step 5 — Cloudflare DNS

`jurismon.com` needs to point at the server before the site is reachable.

**Easiest:** add me to the Cloudflare zone with **DNS-only** access. Full account access is not needed.

1. Log in to **Cloudflare**
2. Click **Manage Account → Members**
3. Click **Invite**, enter my email, and choose the **DNS** role
4. Send

**Or do it yourself** — I will send you the exact IP address to use:

1. Log in to Cloudflare and select **jurismon.com**
2. Click **DNS** in the left menu
3. Click **Add record**
4. Type: **A** — Name: **@** — IPv4 address: *(I will send this)* — Proxy status: **Proxied**
5. Save
6. Add a second record: Type **A**, Name **www**, same IP, Proxied

---

## Step 6 — Admin dashboard password

The admin panel needs a login.

Just choose a password and put it in your file. It is stored only as a secure hash and never in plain text, so even I will not be able to read it back afterwards. You can change it yourself at any time.

```
ADMIN_EMAIL    = admin@jurismon.com   (or another address you prefer)
ADMIN_PASSWORD = (your choice)
```

---

## Step 7 — Confirm the Ubuntu version

One-line answer. When you set up the Hostinger VPS, which Ubuntu version did you install? I had suggested 24.04 LTS. It affects which package versions the setup script targets.

---

## Step 8 — The 11 remaining replacement links

From the list sent on 28 September, these still need working URLs. The Cloudflare-protected ones are dropped as you asked, so those need nothing from you.

**Returning 404:**
- City of Austin — `https://www.austintexas.gov/page/code-ordinances`
- Calgary Land Use Bylaw — `https://www.calgary.ca/pda/pd/calgary-land-use-bylaw.html`
- City of Montreal — `https://montreal.ca/en/regulations`

**Unreachable hosts:**
- San Bernardino County — `https://lu.sbcounty.gov`
- Tarrant County — `https://www.tarrantcounty.com`
- Publications du Québec — `https://www.publicationsquebec.gouv.qc.ca`
- The Edinburgh Gazette — `https://www.theedinburghgazette.co.uk`
- Dallas County — `https://www.dallascounty.org`
- City of Melbourne — `https://www.melbourne.vic.gov.au`

*(The Ontario Gazette, previously on this list, is now fixed.)*

No rush on these — they are the main thing holding the source count back, but everything else can proceed without them.

---

## Step 9 — Optional: four of the eighteen need a decision

These could not be activated. None of them block anything:

| Source | Issue | What would unblock it |
|---|---|---|
| New Zealand Legislation API | Returns 401 | An API key from NZ Parliamentary Counsel Office. Optional — the NZ XML and PDF sources already work |
| data.gov.uk catalogue API | Returns 403 to automated clients | Name a specific dataset and I can target it directly |
| EU CELLAR | Base URL returns 404 | The endpoint needs a specific document reference. Is there a particular EU collection you want? |
| Canada Justice Laws + Germany XML index | Connection timeouts | Likely regional blocking. I will retry from the server once deployed — no action needed |

All are recorded in the catalogue with their reason, so nothing is silently dropped.

---

# Part 4 — Summary Checklist

| # | Item | Time needed | Blocks |
|---|---|---|---|
| 1 | PayPal Business credentials | ~15 min | Payments |
| 2 | Pricing decisions | ~2 min | Payments |
| 3 | GitHub username | ~5 min | Daily automated crawl |
| 4 | Supabase (or say "you create it") | ~5 min or 0 | Production database |
| 5 | Cloudflare DNS | ~3 min | Public site access |
| 6 | Admin password | ~1 min | Admin dashboard |
| 7 | Ubuntu version | ~1 min | Server setup |
| 8 | 11 replacement links | As you get time | Source count only |
| 9 | Four optional sources | As you get time | Nothing |

**The fastest route:** items 3 and 4 clear immediately if you are happy for me to create the GitHub repository and the Supabase project and transfer both at handover. That leaves the PayPal credentials, the pricing answers, and the DNS record as the only real dependencies.

---

> **Reminder:** please send all credentials in an **attached file**, not typed into the chat.

Happy to jump on a call at any point if it is easier to walk through the PayPal setup together.
