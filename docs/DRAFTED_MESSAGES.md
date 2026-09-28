# JurisMon - Drafted Client Messages

This file stores drafted messages for Huzaifah to review and send on Fiverr.
*Note: Once a message is sent on Fiverr, move it to `docs/CHAT_LOG.md`.*

---

## Active Draft - Progress Update + Everything Needed From Client

> Hi Malok,
>
> Quick progress update, plus everything I need from your side to get JurisMon live.
>
> **Where the build is**
>
> The core engine is complete and the full pipeline runs end to end: modular ingestion (REST API connector, Playwright headless browser, and fast HTTP scraper) across all 51 sources plus the 18 structured portals you sent, PDF and HTML extraction with OCR fallback and boilerplate stripping, the section-aware diff engine, full-text search, the PayPal subscription layer, and both the search page and admin dashboard.
>
> I have just finished a full security and code audit pass before packaging for delivery. That caught and fixed several issues that would have caused problems in production — including a bug that would have made PayPal reject every live subscription webhook, and an authentication weakness in the admin panel. The automated test suite now covers those paths specifically and has grown from 30 to 42 tests, all passing. I would rather find these now than after you go live.
>
> ---
>
> **1. VPS root password — please change it**
>
> Please log into your Hostinger VPS and change the root password. The one you sent came through Fiverr chat in plain text, which is not a secure channel, so it should be treated as exposed. This is standard practice before a server goes public.
>
> I have deliberately not changed it myself — your server, your credentials. Once you have set a new one, please send it as an attached file rather than typing it in chat.
>
> I will also set up SSH key authentication during deployment so password logins can be disabled entirely.
>
> **2. GitHub account**
>
> I need a GitHub account to deliver the repository to. The automated daily crawl runs on GitHub Actions, so without a repository the scheduled ingestion cannot run at all.
>
> Please either:
> - Send me your GitHub username and I will create the repository and transfer ownership to you, or
> - Create a private repository yourself and add me as a collaborator
>
> Either works — just let me know which you prefer.
>
> **3. PayPal API credentials**
>
> You will need a PayPal **Business** account with API access (personal accounts cannot issue subscriptions). From developer.paypal.com → Apps & Credentials, I need:
>
> - Client ID
> - Client Secret
> - Webhook ID
>
> To create the Webhook ID, add a webhook pointing to `https://jurismon.com/api/webhooks/paypal` and subscribe it to these five events:
> `BILLING.SUBSCRIPTION.ACTIVATED`, `BILLING.SUBSCRIPTION.CANCELLED`, `BILLING.SUBSCRIPTION.SUSPENDED`, `BILLING.SUBSCRIPTION.EXPIRED`, `PAYMENT.SALE.COMPLETED`
>
> If you would rather see the payment flow working before issuing live keys, send sandbox credentials first and I will demo it for you.
>
> **4. Subscription pricing**
>
> I cannot create the PayPal plan until these are confirmed:
> - Price per cycle and currency (e.g. $29 USD)
> - Billing interval — monthly or annual?
> - You mentioned "subscriptions 7 days" earlier — did you mean a **7-day free trial**, or a 7-day billing cycle? Just want to be certain before the plan is created.
> - One plan at launch, or multiple tiers?
>
> **5. Supabase**
>
> Do you want to provide a Supabase project, or should I create one and transfer it to you at handover? If you provide it, I need the project URL, the service role key, and the connection string.
>
> Creating it myself is usually faster — your call.
>
> **6. Cloudflare DNS**
>
> `jurismon.com` needs to point at the VPS. You can either add an A record yourself (I will send the exact value), or add me to the Cloudflare zone with DNS-only access. Full account access is not needed.
>
> **7. Admin panel password**
>
> The admin dashboard needs a login. The password is stored only as a secure hash, never in plain text — so please choose one and send it in the same attached file, and I will configure it. You can change it yourself at any time afterwards.
>
> **8. Ubuntu version**
>
> Could you confirm which Ubuntu version you installed on the VPS? I had suggested 24.04 LTS. It affects which package versions the setup script targets.
>
> ---
>
> **Fastest path:** if you are happy for me to create the GitHub repository and the Supabase project and transfer both to you at handover, that clears items 2 and 5 immediately. That would leave only the PayPal credentials, pricing, and the DNS record as genuine blockers.
>
> Please send all credentials as an **attached file** rather than typing them into chat.
>
> Happy to jump on a call if it is easier to walk through the PayPal setup together.
>
> Thanks,
> Huzaifah

---

## Sent Messages

*(Move drafts here with the date once sent, then mirror into `docs/CHAT_LOG.md`.)*
