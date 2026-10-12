# JurisMon remaining work

Updated 11 October 2026 after the rigorous v2 test and full client-chat review.
This is the current backlog. Historical task tables may describe older states.
Completed implementation belongs in [implemented-work.md](implemented-work.md).
Commercial evidence belongs in [client-context.md](client-context.md).
Fresh evidence: [rigorous v2 report](../reports/2026-10-11-rigorous-testing-v2.md).

## Current product repairs and verification

| ID | Remaining work | State / next acceptance check |
| --- | --- | --- |
| R-01 | Release the verified accessibility fixes in development commit b67560f | Released 0c8d0a4. Live axe found zero violations across six public pages in light/dark modes and authenticated admin. Incomplete checks still require manual review (R-11). |
| R-02 | Correct signup/resend delivery failures | Implemented and locally verified 11 October: failed signup/resend returns 503; failed delivery preserves previous usable code. Reset API and UI use identical neutral messaging for known/unknown accounts. Released 0c8d0a4; controlled real-mailbox acceptance remains (R-11). See implementation ledger. |
| R-03 | Keep closed dialogs out of keyboard navigation | Implemented locally: closed dialogs are inert and hidden from assistive technology; background is inert while open; Tab/Shift+Tab wrap; Escape and focus return verified in Chromium, Firefox and WebKit. Released 0c8d0a4; live keyboard lifecycle passed Chromium, Firefox and WebKit. |
| R-04 | Correct admin ingestion metrics and timestamps | Implemented locally: actual UTC run counts and latest crawl timestamps/status replace source-health-derived metrics; polling refreshes metrics. SQLite, Supabase and genuine admin browser verified. Released 0c8d0a4; live authenticated overview verified. |
| R-05 | Repair live extraction paths and existing contaminated records | Implemented locally: PDF ingestion, conservative guards, invalid-baseline exclusion, reversible quarantine/restore and consistent search counts in both backends; migration 009 provided. Migration 009 applied; release 0c8d0a4 live. Quarantined 2343/3755 snapshots and 1852 dependent diffs without deletion, with restore manifest backed up. Seven-source backfill added 60 baseline captures; San Diego downloads timed out. Further content review and that endpoint remain. |
| R-06 | Verify ingestion of the eight repaired US sources | Verified production run 83e4a73e completed partial_failure: 7/8 succeeded, 60 new baseline captures, zero new diffs. San Diego: 16 PDF downloads timed out and zero captures. Dispatch/outcome repairs released ea54057; storage-failure follow-up released e2693b7. Eight source status rows synced/read-back; San Diego remains degraded with retries enabled. See source review for per-source counts. |
| R-07 | Resolve/exclude NYC Rules and Santa Clara source gaps | NYC Rules and Santa Clara remain inactive/excluded. Specific names/statuses shown in the live e2693b7 public exclusion list; replacement access remains unresolved. San Diego separately degraded after failed PDF downloads, so 18/21 US sources are marked operational after status sync. No CAPTCHA/login bypass. |
| R-08 | Review the other fourteen non-operational existing sources | Current sixteen-endpoint review recorded in docs/reports/2026-10-11-capture-source-review.md. Some indexes respond but legal extraction is unverified (Germany links XML ZIP files; Canada full XML timed out). Keep exclusions; no activation from HTTP 200 alone. Adapter/replacement work remains. |
| R-09 | Finish measured search-performance investigation | Production repository samples recorded: first empty read 1522.91ms, repeat 148.43/138.06ms; zoning 289.58/202.81/139.66ms; parking 135.02/94.31/83.37ms. Local typing batches at 300ms and aborts stale requests; 7 browser regressions pass. Released 0c8d0a4; measurements are repository reads, not SQL execution plans or universal SLA. |
| R-10 | Investigate Firefox navigation timeout | Latest full isolated regression: 498 passed in 528.38s while read-only audits were ongoing. Former Firefox timeout did not repeat. Original root cause unconfirmed; no retry suppression or unsupported fix claim. |
| R-11 | Complete uncovered QA | Native Safari/physical mobile browsers; actual browser 200% zoom; manual screen-reader review and incomplete axe contrast checks; real mailbox delivery. PayPal agreement/mail delivery require explicit Sandbox credentials and a controlled inbox, never live paid lifecycle calls. |

## Promised client deliverables

| ID | Remaining work | Commitment / dependency |
| --- | --- | --- |
| R-12 | Dedicated honest coverage and exclusions section | Implemented locally: home claims configured/marked-operational sources, links to About coverage/exclusions; capture history and effective-date limits explicit. Removed unsupported alerts and monetary risk claims. Real-count browser check passed. Released 0c8d0a4; explicit inactive-source list released e2693b7 and live-verified: 16 inactive names/statuses, 48 marked operational of 65 configured. |
| R-13 | Written case studies and Case Studies page | Implemented two written source-document cases and /case-studies page. Austin and San Bernardino sections verified in actual production version-1 captures. Publication checks visible evidence and separates legal/capture dates. Released e2693b7; both cases visible and live axe passes in light/dark modes. Customer/vote-based market validation still needs real outcome/voting evidence; no invented claims. |
| R-14 | Page-by-page competitor gap list for Google Sheets | 19-row importable CSV prepared from current official ZoneWire/Bassett pages; matches, gaps, priorities, effort and evidence limits recorded. Google Sheets import/delivery pending; connected Sheets session lookup returned no sessions. |
| R-15 | Scope, deliverables, timeline and budget for selected competitor gaps | Concrete optional scopes/acceptance/effort and budget method drafted in docs/client/competitor-implementation-scope.md. Final selected bundle and agreed rate needed; no invented quote or budget. |
| R-16 | Housekeeping | Completed: unsupported About risk-range removed; documentation index points to current backlog/ledger/context, old task board labelled historical; next-migration guidance corrected. Uncommitted correspondence/settings preserved and excluded from releases. |

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

## Newly confirmed Phase 2 offer gaps (11 October follow-up)

| ID | Remaining work | Evidence |
| --- | --- | --- |
| R-28 | Complete provider-backed developer-free pricing promised by final offer | Catalogue validates an existing PayPal plan; it does not create/update provider plans. |
| R-29 | Preserve historical subscriber plan/price display when current provider ID changes | Real browser pricing update succeeds; resolve_plan_info(old_provider_id) then returns no billing amount. Original subscription ID remains stored. |
| R-30 | Existing-subscriber migration with customer approval | No implemented provider revision/approval flow. |

Browser pricing save/history after refresh and trial settings 34→14 now verified.
See [client agreement audit](client-scope-status-2026-10-11.md). Real Sandbox and
inbox acceptance remain under R-11. These are original-offer gaps, not unordered
alerts/source expansion.

Keep stable R-IDs. After implementing a task, append what/how/evidence/commit/
deployment to implemented-work.md and update the corresponding R-row here.
Record verification gaps and release state separately from implementation.
Do not promote a quote, suggestion or client payment statement into verified
Fiverr acceptance/payment without authoritative transaction evidence.

## 12 October P2-16 follow-up

| ID | Implementation / next acceptance | Release state |
| --- | --- | --- |
| R-31 | Expanded document bound to 70vh with internal scrolling; local authenticated browser passes | Awaiting review/sign-off and live Crimes Act reproduction after deployment. |
| R-32 | Exact bot-check rejection guard and existing quarantine CLI locally verified | Live NZ row identified; reviewed production quarantine still pending. |
| R-33 | Ontario pager exclusion and UK instrument-title recovery; historical title repair CLI preserves original-title manifest | Fresh live metadata validates proposed titles; production corrections still pending. |
| R-34 | Configurable 60-second document timeout; five US sources probed and Clark file-host self-signed certificate diagnosed | Not deployed. NYC 403, Clark document discovery/trusted replacement, and real ingestion follow-up remain. |

P2-16 live measurements confirm crawl-status interval polling already works.
Repeated browser `zoning` fetches were 6939/4445/4686ms (variance 1.56x), not
repository-level samples. Absolute latency remains high; no blind query tuning.
User confirmed no staging environment exists: local acceptance, review/sign-off,
then production deployment/live verification. No client push or deploy yet.
See [P2-16 evidence](../reports/2026-10-12-p2-16-implementation.md).
