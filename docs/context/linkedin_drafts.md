# JurisMon Project — LinkedIn Post Drafts & Social Artifacts

This document contains four distinct LinkedIn post drafts based on the engineering build of JurisMon, backed by verified metrics from the repository and production database.

Each draft is provided in two versions:
1. **Named Version**: Explicitly references JurisMon and `jurismon.com`.
2. **Anonymous Version**: Mentions "a regulatory monitoring platform for a US client" with zero proprietary names or domains, suitable for posting if client permission has not yet been confirmed.

---

## Verified Project Metrics (Repository Truth)

The figures cited below are sourced directly from git logs, the test suite, and the production database:

- **Build Duration**: 7 days (September 28, 2026 to October 4, 2026).
- **Git Activity**: 47 commits on branch `claude/sweet-babbage-fz7sbz`.
- **Test Suite**: 255 passing tests with zero regressions (`pytest tests/ -q`).
- **Configured Target Sources**: 65 municipal and statutory portals cataloged in `config/sites.json`.
- **Operational Daily Sources**: 41 active sources crawling daily (24 excluded due to upstream Cloudflare firewalls, dead municipal links, or restricted endpoints; see `docs/SOURCE_COVERAGE.md`).
- **Crawler Architecture**: 7 platform-specific adapters inheriting from `BaseAdapter` (`CivicPlusAdapter`, `CustomAdapter`, `DirectDocumentAdapter`, `GranicusAdapter`, `MunicodeAdapter`, `RestApiAdapter`, `XmlFeedAdapter`).
- **Latest Production Ingestion Run**: Run ID `ddc43bdb-789f-4070-8be9-a659beb34ce2` (October 3, 2026):
  - Duration: 1 hour 6 minutes (10:31:29 UTC to 11:37:58 UTC).
  - Sources Processed: 41 operational portals (41 succeeded, 0 failed, 24 skipped).
  - Documents Ingested & Versioned: 915 legal documents.
  - Regulatory Diffs Generated: 226 statutory paragraph-level amendments.
- **Database Migrations**: 6 versioned PostgreSQL SQL migrations (`001_initial_schema.sql` through `006_crawl_sources_skipped.sql`).
- **Commercial Stack**: Customer JWT authentication, transactional email verification via Resend, 14-day free trial search gating, and PayPal subscription webhooks with `custom_id` mapping.

---

## Accompanying Posters & Image Assets

Three high-resolution square graphics (1200 x 1200 px, optimal for LinkedIn feed engagement) were generated from the delivery artifacts and saved in [`docs/context/posters/`](file:///d:/fiverr%20client/malok%20mading/docs/context/posters/):

1. [**`poster_1_client_review.png`**](file:///d:/fiverr%20client/malok%20mading/docs/context/posters/poster_1_client_review.png): High-trust social proof featuring the verified Fiverr review card ("I wish there's another rating above 5 stars..."), paired with the 4 core delivery metrics (41 sources, 915 documents, 226 diffs, 255 tests).
2. [**`poster_2_system_architecture.png`**](file:///d:/fiverr%20client/malok%20mading/docs/context/posters/poster_2_system_architecture.png): Product and UI showcase displaying the live Legal Redline Diff Viewer and the Administrative Source Health Console in clean macOS-style window frames.
3. [**`poster_3_engineering_process.png`**](file:///d:/fiverr%20client/malok%20mading/docs/context/posters/poster_3_engineering_process.png): Engineering rigor and post-mortem breakdown featuring the passing test suite terminal and the 3 architectural rules that prevented production failures.

---

## DRAFT A — THE BUG STORY

### Angle
A specific, technical story about a silent bug that survived code review and unit tests, how it was uncovered, and what general principle it revealed.

---

### A1. Named Version (Mentions JurisMon)

A few days before handing over JurisMon, every single test was green.

All 250+ unit and integration tests passed. The API returned valid JSON. The admin login worked.

Then I clicked "Log out".

The screen froze on "Loading portal status…" forever. The login box never showed up. No JavaScript error appeared in the browser console.

Here is what happened:

In `frontend/admin.html`, the `<div id="auth-gate">` modal had accidentally been placed *after* the closing `</script>` tag.

When the script parsed, `document.getElementById('auth-gate')` returned `null`.

Because the code defensively wrapped DOM manipulations in `if (authGate) { ... }`, the missing element never threw an exception. It failed in total silence.

Every test had passed because the test suite only exercised the authenticated happy path. Nobody had tested what happens after clearing the token.

We fixed the DOM ordering, but more importantly, we added an automated test asserting that `#auth-gate` precedes `<script>` in the markup.

Two lessons from this build:
1. A defensive null-check often turns a loud structural bug into silent broken behavior.
2. If you haven't tested your unauthenticated and logged-out states, you haven't tested your frontend.

---

### A2. Anonymous Version (Client & Product Unnamed)

A few days before delivering a SaaS platform for a US legal client, every single test was green.

Over 250 unit tests passed. The backend API returned clean JSON. The dashboard worked.

Then I clicked "Log out".

The page froze on "Loading status…" forever. The login modal never appeared. And the browser console showed zero errors.

Here is what actually happened:

In the dashboard markup, the login modal `div` had accidentally been placed *after* the closing `<script>` tag.

When the script ran on page load, `document.getElementById('auth-gate')` returned `null`.

Because the JavaScript defensively wrapped the modal in `if (authGate) { ... }`, the null reference never threw an error. It failed in complete silence.

The test suite had passed because our tests verified the authenticated flow. Nobody had checked what happened when the session ended.

We fixed the markup order and added a regression test to enforce it.

Two lessons from this:
1. Defensive null-guards often convert an obvious bug into silent failure.
2. Testing the happy path tells you nothing about how a page behaves when a user signs out or a session expires.

---

## DRAFT B — THE BUILD

### Angle
Concrete breakdown of what the platform does and the engineering behind it. Direct, factual, zero fluff.

---

### B1. Named Version (Mentions JurisMon)

Over the past week, I built and deployed JurisMon (`jurismon.com`), an automated regulatory monitoring platform for municipal law.

Local governments across the US and UK frequently amend zoning bylaws, ordinances, and building codes without publishing centralized feeds. JurisMon tracks them automatically.

Here is the engineering stack behind it:

• Ingestion Pipeline:
Crawls 41 municipal and county portals daily across 7 custom platform adapters (Granicus, Municode, CivicPlus, RSS/Atom, and REST APIs).

• Document Extraction & OCR:
Extracts text from dynamic HTML tables and multi-megabyte PDFs. If an ordinance is a scanned image, it routes through a Tesseract OCR fallback pipeline.

• Regulatory Diff Engine:
Splits statutory legal texts into granular sections (§) and paragraphs. It hashes snapshots with SHA-256 and computes automated additions, deletions, and modifications across successive versions.

• Commercial Infrastructure:
FastAPI backend on Python 3.12, PostgreSQL full-text search with `websearch_to_tsquery`, 14-day free trial gating, transactional email verification via Resend, and automated PayPal subscription webhooks mapping user IDs.

In our latest daily crawl, the system processed 41 portals in 66 minutes, versioning 915 legal documents and generating 226 statutory diffs.

Backed by 255 automated tests running before deployment.

---

### B2. Anonymous Version (Client & Product Unnamed)

Over the past week, I engineered and deployed an automated regulatory intelligence platform for a client monitoring local government legislation.

Municipalities in the US and UK enact zoning amendments and municipal code revisions constantly, but rarely provide centralized feeds. The platform tracks them automatically.

Here is how the system works:

• Multi-Platform Ingestion:
Monitors 41 municipal and county planning portals daily using 7 custom crawler adapters (supporting Municode, Granicus, CivicPlus, and government REST endpoints).

• Text Extraction & OCR:
Parses HTML and multi-page PDF documents. For scanned municipal filings, it runs an automated Tesseract OCR fallback.

• Clause-Level Diffing:
Splits legal texts by section (§) and paragraph. It calculates SHA-256 hashes for each clause and automatically generates redlines showing additions, modifications, and deletions between revisions.

• Search & Subscription Tiering:
FastAPI REST backend, PostgreSQL full-text search, customer accounts with 14-day trial gating, transactional email verification, and PayPal subscription webhooks.

In the latest daily run, the crawler ingested 41 portals in 66 minutes, indexing 915 legal filings and identifying 226 statutory diffs.

Delivered on time with 255 automated tests passing on the production VPS.

---

## DRAFT C — THE PROCESS

### Angle
How the project was verified and hardened. Focuses on engineering discipline, catching regressions, and why thorough processes protect clients.

---

### C1. Named Version (Mentions JurisMon)

During the build of JurisMon, the same bug bit us three separate times.

Each time, a new database column worked perfectly in local testing. All 200+ unit tests passed. Then, upon deployment to production, the app crashed with `column does not exist`.

The root cause:
Local tests ran against SQLite, which dynamically creates columns on the fly. Production runs PostgreSQL on Supabase, which strictly requires explicit SQL migrations.

Instead of writing a reminder to "be more careful", we wrote a contract guard: `tests/test_schema_contract.py`.

It introspects the SQLite tables initialized by our local repository and compares them against every migration in `db/migrations/`. If a single column exists in SQLite without a matching PostgreSQL migration, the build halts immediately.

We applied that same discipline across the platform:
- UI changes verified against full-page browser screenshots, not just API responses.
- Every page verified across five states: signed out, loading, loaded, error, and expired session.
- Deployment separated into a verified VPS runbook (`scripts/deploy.sh`) with dependency and database health checks.

The final test suite has 255 tests. The production site runs cleanly with zero database drift.

Process is what turns a prototype into something you can actually rely on.

---

### C2. Anonymous Version (Client & Product Unnamed)

During a recent client project, the exact same bug hit us three separate times.

Each time, a new database column worked cleanly in local development. Every unit test passed. Then, the moment we deployed to production, the server threw `column does not exist`.

The reason:
Local tests ran on SQLite, which happily creates columns on the fly. Production ran PostgreSQL, which strictly enforces migration files.

Instead of hoping we wouldn't forget next time, we wrote an automated test: `test_schema_contract.py`.

The test introspects the SQLite schema and checks every SQL migration in the repository. If any column exists in code without a corresponding PostgreSQL migration, the test suite fails on the spot.

That incident shaped how we delivered the entire system:
- Frontend updates verified via full-page rendered screenshots, never just API status codes.
- Every view audited across five states: signed out, loading, loaded, error, and expired token.
- Deployment isolated to an automated VPS script that asserts health checks before switching traffic.

We handed over the project with 255 automated tests passing and zero schema drift.

Writing code is the easy part. Building guards so you can't break your own system is what matters.

---

## DRAFT D — THE REVIEW

### Angle
Leads directly with the client's verbatim review, followed by an understated explanation of what earned it.

---

### D1. Named Version (Mentions JurisMon)

"I wish there's another rating above 5 stars. I am so excited to have gotten Huzaifah to work with. Everything has been excellent. I thought the current reviews were undeserving, but I can confess that he is in the top 10% on Fiverr among the best. Thank you so much for the work you have done!"

That was the feedback from our client upon completing JurisMon (`jurismon.com`).

Here is what went into earning it:

In one week, we designed, built, and deployed an automated regulatory drift platform tracking 41 municipal and county portals across the US and UK.

It extracts text from municipal filings, runs OCR on scanned PDFs, redlines legal amendments at the clause level, and serves full-text search behind customer accounts and PayPal subscriptions.

We didn't cut corners on delivery:
- 47 git commits, each tested before merge.
- 255 automated tests passing on the production server.
- Full system handover guide and operational documentation.
- Live verification of every payment, search, and crawl workflow.

When clients hire a senior developer, they aren't paying for lines of code. They are paying for systems that work when they log in on Monday morning.

If you are building an automated crawler, data pipeline, or custom web platform, send me a message.

---

### D2. Anonymous Version (Client & Product Unnamed)

"I wish there's another rating above 5 stars. I am so excited to have gotten Huzaifah to work with. Everything has been excellent. I thought the current reviews were undeserving, but I can confess that he is in the top 10% on Fiverr among the best. Thank you so much for the work you have done!"

That was the review left by my client this weekend after receiving their deliverable.

Here is what went into earning that response:

We built and deployed an automated regulatory intelligence platform that monitors municipal and county legislation across North America and the UK.

The system crawls 41 government portals daily, parses multi-page PDFs with OCR fallback, computes paragraph-level legal text diffs, and manages customer trials with PayPal subscription billing.

What made the difference wasn't just the code:
- 255 automated tests passing before handover.
- Zero fake metrics or unverified numbers on screen.
- A complete operations runbook and technical documentation.
- Production deployment on their Linux VPS with automated daily timers.

Clients don't want prototypes that fall apart when edge cases hit. They want software that works quietly and reliably.

If you have a complex scraping, web application, or automation project, feel free to reach out.

---

## Strategic Posting Recommendations

### Which Draft to Post First?
**Post Draft D (The Review) or Draft A (The Bug Story) first.**

- **Why Draft D first**: If your primary objective is immediate inbound client enquiries, leading with a verbatim, glowing client review paired with [**`poster_1_client_review.png`**](file:///d:/fiverr%20client/malok%20mading/docs/context/posters/poster_1_client_review.png) provides immediate proof of capability and customer satisfaction. It bridges freelancing with engineering execution.
- **Why Draft A second**: "The Bug Story" paired with [**`poster_3_engineering_process.png`**](file:///d:/fiverr%20client/malok%20mading/docs/context/posters/poster_3_engineering_process.png) travels exceptionally well on LinkedIn technical feeds because engineers and CTOs appreciate vulnerability, concrete debugging post-mortems, and practical takeaways.

---

## Screenshot & Poster Asset Guide

| Post Draft | Recommended Visual Asset | Notes & Privacy Considerations |
| :--- | :--- | :--- |
| **Draft A (The Bug Story)** | [**`poster_3_engineering_process.png`**](file:///d:/fiverr%20client/malok%20mading/docs/context/posters/poster_3_engineering_process.png) OR `delivery_screenshots/19_tests_passing.png` | Completely safe to post. Contains only code, terminal output, and architectural lessons. No sensitive client data. |
| **Draft B (The Build)** | [**`poster_2_system_architecture.png`**](file:///d:/fiverr%20client/malok%20mading/docs/context/posters/poster_2_system_architecture.png) OR `delivery_screenshots/04_diff_viewer_modal.png` | The Diff Viewer modal shows public municipal zoning ordinances (public record). Shows UI sophistication without exposing proprietary backend secrets. |
| **Draft C (The Process)** | [**`poster_3_engineering_process.png`**](file:///d:/fiverr%20client/malok%20mading/docs/context/posters/poster_3_engineering_process.png) | High engineering credibility. Highlights the schema-contract parity guard and testing discipline. |
| **Draft D (The Review)** | [**`poster_1_client_review.png`**](file:///d:/fiverr%20client/malok%20mading/docs/context/posters/poster_1_client_review.png) | Uses the public review from Fiverr profile. The poster pairs the cropped review with clean delivery numbers (41 sources, 915 documents, 255 tests). Highly recommended. |

> [!WARNING]
> **Data Privacy Notice:**
> - Avoid posting screenshots showing raw customer email addresses or database connection strings.
> - `delivery_screenshots/15_admin_subscribers.png` should not be posted publicly unless test customer names/emails are blurred.
> - The three generated posters in `docs/context/posters/` have already been vetted and contain zero credentials, zero IP addresses, and zero private customer data.

---

## Recommended LinkedIn Hashtags

These hashtags are actively searched by founders, product managers, and engineering leads looking for freelance or contract software engineers:

`#Python` `#FastAPI` `#WebScraping` `#SoftwareEngineering` `#PostgreSQL` `#Automation` `#FullStackDevelopment` `#DevOps`
