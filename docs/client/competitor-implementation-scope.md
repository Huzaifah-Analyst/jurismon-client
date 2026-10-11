# Competitor implementation options, 11 October 2026

The [19-row CSV](competitor-gap-list-2026-10-11.csv) imports into Google Sheets
using File > Import > Upload. It compares publicly reviewed pages, not authenticated
paid features. No sheet was created in a connected Google account in this session.
Effort is an engineering estimate in working days, not an agreed quote or delivery
date. Research, provider spend and ongoing content production are separate.

## Recommended sequence

1. Release accurate coverage/exclusions already implemented (G01/R-12).
2. Finish extraction/history repairs and verify actual ingestion before adding
   credibility claims, cases or bigger coverage numbers.
3. Publish two independently reviewed cases with official before/after documents,
   capture dates, exact section changes and evidence limitations (G04/R-13).
   Estimated 2-4 working days after usable evidence. Included/free promise retained.
4. Offer a public source catalogue with jurisdiction, source type, recorded health,
   last verified capture and explicit exclusions (G02/G05). Estimate 3-5 days for
   catalogue, then 3-5 days for state/county navigation; avoid double-counting shared UI.
5. Consider CSV export, source provenance labels and paged search before new
   transcription, AI answers or parcel products.

## Acceptance and scope boundaries

- Coverage catalogue: every displayed field comes from stored evidence; configured,
  reachable and ingested remain distinct. Empty dates display unavailable. No count
  is promoted to complete jurisdiction coverage.
- Cases: exact source links and dates, independently checked text, no invented
  customer savings, prediction accuracy or claim of historical captures never made.
- CSV export: customer entitlement enforced server-side; only authorized fields;
  spreadsheet-formula injection handled; named columns and traceable source links.
- Developer API (G12): optional separate product; hashed keys, revoke/rotate,
  account scopes, quotas and automated entitlement regression. Internal JWT APIs
  are not advertised as a finished developer API.
- MCP (G15): depends on that API; no additional entitlements or credentials inside
  the MCP server. Meeting transcription and parcel intelligence need independent
  feasibility/data-rights review before estimation.

## Budget preparation

R-17 alerts/watchlists ($100), R-18 88-source expansion ($150) and R-19 first-month
support ($25) retain their historical quote and unplaced-order state. They are not
repriced here. Future competitor work has no agreed hourly/day rate or selected
bundle. Final budget is selected engineering effort times agreed rate, plus any
explicitly approved provider costs. G12/G15 are estimates, not authorized additions.
Do not use these planning ranges as a commercial offer or claim payment received.

## Research evidence

- [ZoneWire home](https://www.zonewire.co/): source-linked examples and capability
  limits; public market selection. Counts are competitor claims, not our audit.
- [Pricing](https://www.zonewire.co/pricing): free alerts, per-market and broader
  tiers, paid Q&A and archive/export positioning. Home says 161 markets while pricing
  advertises 172; API availability wording also differs across pages. Flag the
  inconsistency instead of treating either figure as verified.
- [Developer docs](https://www.zonewire.co/docs/api): key authentication, scoped
  reads, cursors, a changes feed and MCP integration. No key was created or paid
  endpoint exercised.
- [States](https://www.zonewire.co/states), [meetings](https://www.zonewire.co/meetings),
  [blog](https://www.zonewire.co/blog) and [comparison](https://www.zonewire.co/compare)
  were reviewed individually. The requested how-it-works URL resolved to the home
  page; /glossary did not resolve in the research tool, so no verified glossary gap
  is included. Blog cases were not independently validated as legal outcomes.
- [Bassett](https://www.bassett.ai/): early-access marketing, cited-source/parcel
  positioning and audience sections. Login points to Zoneomics. Neither a full
  accessible Bassett product nor paid behavior was established from this page.
