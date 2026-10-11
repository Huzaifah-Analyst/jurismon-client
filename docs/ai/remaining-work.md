# JurisMon remaining work

Updated 11 October 2026 after the rigorous v2 test and full client-chat review.
This is the current backlog. Historical task tables may describe older states.
Completed implementation belongs in [implemented-work.md](implemented-work.md).
Commercial evidence belongs in [client-context.md](client-context.md).
Fresh evidence: [rigorous v2 report](../reports/2026-10-11-rigorous-testing-v2.md).

## Current product repairs and verification

| ID | Remaining work | State / next acceptance check |
| --- | --- | --- |
| R-01 | Release the verified accessibility fixes in development commit b67560f | Not live. Production e33ef18 still has missing auth-dialog name, admin input label/chart semantics and account h1. Deploy only within user-authorized release scope, then rerun live axe. |
| R-02 | Correct signup/resend delivery failures | Reproduced locally with provider returning false: both endpoints report mail sent; failed resend changes the code and rejects the old code. Show accurate feedback and preserve a usable previous code. Password-reset failure handling also needs investigation. |
| R-03 | Keep closed dialogs out of keyboard navigation | Reproduced live: Tab reaches invisible #auth-modal-close while #auth-modal opacity is zero. Check all closed dialogs, open focus trap, Escape and focus return using actual keyboard input. |
| R-04 | Correct admin ingestion metrics and timestamps | Live "Ingestion runs today" shows operational sources 49/65. Overview says last daily run was 11 days ago while crawl status shows a completed run earlier today. Use actual crawl records for run claims; verify source freshness separately. |
| R-05 | Repair live extraction paths and existing contaminated records | First eight newest captured results: seven navigation/catalogue wrappers and one empty NZ snapshot. Germany RSS, Canada metadata/resource wrappers and Australian title pages remain visible. Check all adapter paths, distinguish post-release ingestion from historical records, then define a reversible cleanup/backfill preserving valid history. |
| R-06 | Verify ingestion of the eight repaired US sources | Configuration and legal-document extraction verified; configs synced live. Do not equate operational metadata with completed ingestion. Manual crawl started during this audit and remained running at the final check. Verify actual stored legal documents/diffs and final run outcome. |
| R-07 | Resolve/exclude NYC Rules and Santa Clara source gaps | 19/21 US sources marked operational; two remain Cloudflare blocked. Use accessible official replacements or state exclusions; no CAPTCHA/login bypass is in scope. |
| R-08 | Review the other fourteen non-operational existing sources | Total is 49/65 marked operational, sixteen unresolved overall. Source-by-source verification/replacement or documented exclusion; separate from the unordered 88-source expansion. |
| R-09 | Finish measured search-performance investigation | Worker-pool fix is live. Three fresh anonymous requests: 637.69, 420.25, 391.84ms. Variance remains; obtain server/query evidence before proposing more tuning. |
| R-10 | Investigate Firefox navigation timeout | Full regression: 450 passed, one 30s /account navigation timeout. The exact case passed three isolated reruns. Cause unconfirmed; retain evidence and test under comparable concurrent browser load. |
| R-11 | Complete uncovered QA | Native Safari/physical mobile browsers; actual browser 200% zoom; manual screen-reader review and incomplete axe contrast checks; real mailbox delivery. PayPal agreement/mail delivery require explicit Sandbox credentials and a controlled inbox, never live paid lifecycle calls. |

## Promised client deliverables

| ID | Remaining work | Commitment / dependency |
| --- | --- | --- |
| R-12 | Dedicated honest coverage and exclusions section | Client's 10 October priority. About intro improved, but homepage still calls the mixed local/international catalogue municipal/county. Review all claims, distinguish configured/operational/ingested, and explain capture-time history limits. |
| R-13 | Written case studies and Case Studies page | Promised free/included, reiterated by client on 10 October. Not delivered. Use real source documents, dates and verified legal changes; current noisy records cannot substantiate market validation. No invented cases or claimed volume. |
| R-14 | Page-by-page competitor gap list for Google Sheets | Promised 10 October. List missing features, existing matches, useful versus unnecessary ideas, effort and priorities. Reverify competitor pages when doing this work; past chat comparisons are historical observations. |
| R-15 | Scope, deliverables, timeline and budget for selected competitor gaps | After R-14 and client selection. Analysis does not authorize new feature implementation. |
| R-16 | Housekeeping | About risk-range punctuation; index/status consistency. Preserve uncommitted client correspondence and settings. Do not publish raw chat or credentials as documentation cleanup. |

The previously approved sequence after repairs/QA remains case studies,
housekeeping, source/extraction completion, honest coverage, competitor sheet,
then implementation scope/budget. Case-study evidence depends on data quality.

## Quoted work whose order has not been placed

These are the final 4 October commercial parts, not engineering board IDs.

| ID | Work | Quoted amount | Order state |
| --- | --- | --- | --- |
| R-17 | Amendment email alerts, saved searches/watchlists, matching and unsubscribe | $100 | Commercial Part 3; not ordered, not implemented. |
| R-18 | 88 net-new sources from the 142-link list, real ingestion audit and exclusions | $150 | Commercial Part 4; not ordered, not implemented. |
| R-19 | First-month support arrangement | $25 one-off | Part of revised Order 2; not ordered. |

Case studies are included/free in that quote. Revised Order 2 total is **$275**,
not $250. The $250 figure is the feature subtotal. Retainer thereafter was
discussed at $50/month, not an already active or paid service.

## Requested or proposed future work without a final order/scope

| ID | Work | Evidence / scope state |
| --- | --- | --- |
| R-20 | Google Analytics plus cookie consent | Client requested 3 October; explicitly deferred until after launch. No final quote/order. |
| R-21 | Broader self-service account features: profile editing, authenticated password change, billing history and upgrades | Raised 3-4 October; early broad quote included them, final $101 custom offer narrowed to subscription controls/pricing. Remaining additions need scope confirmation. Forgot/reset password is already implemented. |
| R-22 | Manual admin tier/comp overrides and adding/managing new tiers | Client's 4 October request. Existing catalogue edits/trial setting are implemented; no current override or tier-creation API. Scope separately, do not mark all pricing work unfinished. |
| R-23 | CSV result export and redline PDF export | Proposed 4 October; no final quoted/placed order. |
| R-24 | Multi-user firm/team seats and roles | Proposed 4 October; no final quoted/placed order. |
| R-25 | Outbound source-health notifications | Proposed 4 October; no final quoted/placed order. Distinct from amendment alerts. |
| R-26 | Proper SEO beyond the shipped metadata/canonical/sitemap basics | Client and developer deferred on 1 October; no final quote/order. |
| R-27 | Formal ongoing maintenance offer | $50/month agreed in principle; no accepted recurring offer/payment evidenced. Define current terms before starting a retainer. |

## Explicitly deferred / client-side decisions

- Coolify migration: client shelved it on 5 October; no price/order. Do not start.
- Envato dashboard: discussed as an alternative; no template selected/purchased
  or migration authorized. Client accepted finishing the existing frontend free.
- Optional Stripe support: future possibility from the original discussion,
  not an ordered integration.
- Phase 2 Parts 1+2 $101 offer acceptance/payment: verify in Fiverr. Repository
  evidence cannot settle it; do not put shipped code back in the implementation queue.
- Marketing for 4-6 months and funding approval: client business plans, not a
  developer deliverable or authorization to charge for marketing.

## Updating this backlog

Keep stable R-IDs. After implementing a task, append what/how/evidence/commit/
deployment to implemented-work.md and update the corresponding R-row here.
Record verification gaps and release state separately from implementation.
Do not promote a quote, suggestion or client payment statement into verified
Fiverr acceptance/payment without authoritative transaction evidence.
