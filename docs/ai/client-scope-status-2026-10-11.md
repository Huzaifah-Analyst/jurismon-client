# Client agreement versus implementation — 11 October 2026

Read against the client correspondence: original brief; 4 October broad request,
subsequent quote and final $101 offer; 7 October free frontend commitment; and
10 October competitor-list promise and client priorities. The final offer, rather
than the superseded broad proposal, defines Parts 1 and 2. User instructions
prioritize existing repairs and promised deliverables before unplaced orders.

## Agreed work status

| Work | Current result | Still required |
|---|---|---|
| Original monitoring/search/admin/payment setup | Existing implementation; earlier release evidence recorded in implemented-work.md. | Existing-source coverage remains incomplete; real billing acceptance is not proven by isolated tests. |
| Free frontend completion, caching and search improvements | Implemented/released; genuine browser regression evidence exists. | Native-device, screen-reader and other manual QA listed under R-11. |
| Part 1 customer pause/resume/cancel, screens and access | Real local browser actions and backend access checks pass with mocked external services. | Real PayPal Sandbox lifecycle, agreement and actual confirmation inbox delivery. Cancelled subscriptions require a new subscription; paused ones resume the same ID. |
| Part 2 admin-controlled pricing | Existing provider-plan validation, catalogue editing and public price refresh verified. | App does not create/update PayPal plans, so changing display price alone cannot satisfy developer-free pricing promised in the final offer. |
| Part 2 old subscriber price preservation | Original provider ID remains stored. | Replacing catalogue provider ID causes old account price lookup to return unavailable. Preserve historical billing information and verify old 49/new 59 displays and billing. Provider billing was not exercised. |
| Part 2 optional migration with customer approval | Not implemented. | Provider revision/approval flow and authorized acceptance tests. |
| Part 2 dated price history | Browser successful price/provider-ID edit creates two history rows; old/new values, actor and date visible after refresh. Rejected change records no history. | No remaining gap in the exercised local scenario; production provider validation remains separate. |
| Global configurable trial | Browser admin saves 34 then 14; settings persist and public pricing/signup/verification/account wording update. Backend trial grant tests already pass. | Real local configuration preserved at the user's 10; production was not changed by these tests. |
| Honest coverage and exclusions | Released evidence: 65 configured, 48 marked operational, sixteen inactive exclusions, separately degraded San Diego. Counts are historical release evidence, not a fresh live ingestion audit in this session. | Repair/replacement of excluded endpoints and San Diego PDF timeouts; confirm genuine document ingestion before activation. |
| Written real-data case studies | Two source-document cases and page implemented/released according to the ledger. | Real customer/voting/market-outcome validation is not established by those cases. |
| Retention and capture history | Snapshot storage and reversible quarantine implemented; legal dates separated from capture dates. | Fuller source/extraction audit and coverage remain. No complete market history claimed. |
| Competitor gap list | 19-row CSV and proposed implementation scopes prepared. | Google Sheets delivery and selected implementation budget/rate remain. |

## Outside the currently authorized implementation sequence

- Alerts/watchlists $100 and 88 new sources $150: unplaced order; user explicitly
  requested existing fixes/promised deliverables first.
- First-month support $25 belongs to that unplaced Order 2 (total $275).
- Analytics/consent, broader account/profile/billing-history tools, manual comp
  overrides, new tiers, exports, team seats and health alerts require their final
  scope/order; the broad 4 October request was narrowed by the final offer.
- Coolify explicitly shelved; Envato migration not selected; no active paid
  recurring retainer established by repository records.
- $101 offer acceptance/payment cannot be established from this correspondence;
  Fiverr is the authority. User reports original $200 received.

Conclusion: all currently discussed work is **not** complete. Parts 1 and 2 must
not be presented as fully accepted end-to-end, and the pricing implementation
gaps above are distinct from missing external test access.

Verification: test-results/phase2-pricing-history.xml, three browser tests passed.
Tests use temporary catalogue storage and genuine local HTTP/database state;
PayPal remains mocked. One test explicitly measures the missing old-plan price
lookup; its passing assertion documents a defect, not feature completion.
