# JurisMon - Drafted Client Messages

This file stores drafted messages for Huzaifah to review and send on Fiverr.
*Note: Once a message is sent on Fiverr, move it to `docs/CHAT_LOG.md`.*

---

## Active Draft - Ingestion Milestone + Everything Needed To Go Live

> Hi Malok,
>
> Good progress to report. All 18 additional sources you sent are now processed and wired into the pipeline.
>
> **What went in**
>
> Eight are live and pulling documents:
>
> | Source | Delivery format |
> |---|---|
> | Australia Federal Register of Legislation | REST API |
> | UK New Statutory Instruments | Atom feed |
> | UK Planning Data | REST API |
> | Victoria Planning Schemes | Dynamic web app |
> | Canada Point-in-Time Bulk XML | Bulk XML |
> | New Zealand RMA 1991 | XML and PDF |
> | Germany Gesetze im Internet | HTML portal |
>
> A verified live run across these returned **760 documents**, with all nine sources succeeding.
>
> Three of the eighteen (the Australia website, Queensland Legislation, and UK legislation.gov.uk) were already in our catalogue from your original list, so they were matched to the existing entries rather than duplicated.
>
> Your point about fragmented delivery endpoints was well made, and building for it paid off immediately. Several of these sources publish XML and Atom rather than JSON, which the REST connector could not read, so I added two more connectors: one for XML and Atom feeds, and one for sources that are a single statutory document addressed directly, like the NZ Act which comes as both XML and PDF. Everything still normalizes into the same internal schema before the diff engine sees it.
>
> **One dead link recovered**
>
> Your file happened to contain a working URL for the Ontario Gazette, which was one of the 404s I flagged. That one is fixed and back in the active set. We are now at **41 active sources**.
>
> ---
>
> **1. Replacement links, gentle nudge**
>
> The other **11 dead links** from the list I sent on the 28th are still outstanding. No rush at all, but they are the main thing holding the source count back. The Cloudflare-protected ones are dropped as you asked, so those need nothing from you.
>
> **2. Six of the eighteen need something from you**
>
> These could not be activated:
>
> - **New Zealand Legislation API** returns 401 and needs an API key, which you would request from the NZ Parliamentary Counsel Office. The NZ XML and PDF sources are already working, so this is optional unless you want the full versioned API.
> - **data.gov.uk catalogue API** returns 403 to automated clients. If you have a specific dataset in mind I can target it directly instead.
> - **EU CELLAR** returns 404 on the base URL; that endpoint needs a specific document reference rather than the root. Is there a particular EU collection you want?
> - **Canada Justice Laws** (website and XML index) and the **Germany XML index** time out from here. These may simply be blocking my region, so I will retry from the VPS once it is deployed. No action needed yet.
>
> All six are recorded in the catalogue with the reason, so nothing is silently dropped.
>
> ---
>
> **What I need to take this live**
>
> **3. VPS root password, please change it**
> Please log into Hostinger and set a new root password. The one you sent came through Fiverr chat in plain text, so it should be treated as exposed. I have deliberately not changed it myself since it is your server and your credentials. I will set up SSH key authentication during deployment so password logins can be switched off entirely.
>
> **4. GitHub account**
> The daily crawl runs on GitHub Actions, so the repository has to exist before scheduled ingestion can run. Send me your GitHub username and I will create the repo and transfer ownership to you, or create a private repo yourself and add me as a collaborator, whichever you prefer.
>
> **5. PayPal Business API credentials**
> From developer.paypal.com, under Apps and Credentials, I need the Client ID, Client Secret and Webhook ID. For the Webhook ID, add a webhook pointing to `https://jurismon.com/api/webhooks/paypal` subscribed to these five events:
> `BILLING.SUBSCRIPTION.ACTIVATED`, `BILLING.SUBSCRIPTION.CANCELLED`, `BILLING.SUBSCRIPTION.SUSPENDED`, `BILLING.SUBSCRIPTION.EXPIRED`, `PAYMENT.SALE.COMPLETED`
>
> If you would rather see the payment flow demonstrated first, send sandbox credentials and I will walk you through it before you issue live keys.
>
> **6. Subscription pricing**
> I cannot create the plan without the price and currency, the billing interval (monthly or annual), and one clarification: when you mentioned "subscriptions 7 days" earlier, did you mean a **7-day free trial** or a 7-day billing cycle? Also, one plan at launch or multiple tiers?
>
> **7. Supabase**
> Would you like to provide a project, or should I create one and transfer it to you at handover? Creating it myself is usually faster. If you provide it, I need the project URL, the service role key and the connection string.
>
> **8. Cloudflare DNS**
> `jurismon.com` needs to point at the VPS. Either add an A record yourself, and I will send the exact value, or add me to the zone with DNS-only access. Full account access is not needed.
>
> **9. Admin password**
> The dashboard needs a login. It is stored only as a secure hash and never in plain text, so just choose one and send it in the same file. You can change it yourself afterwards.
>
> **10. Ubuntu version**
> Could you confirm which Ubuntu version you installed? I suggested 24.04 LTS, and it affects which package versions the setup script targets.
>
> ---
>
> **Fastest path:** if you are happy for me to create the GitHub repo and the Supabase project and transfer both at handover, items 4 and 7 clear immediately. That leaves the PayPal credentials, the pricing, and the DNS record as the real dependencies.
>
> Please send all credentials as an **attached file** rather than typing them into chat.
>
> On the UI, noted on keeping it distraction-free. The backend is nearly buttoned up and that is next.
>
> Thanks,
> Huzaifah

---

## Sent Messages

*(Move drafts here with the date once sent, then mirror into `docs/CHAT_LOG.md`.)*
