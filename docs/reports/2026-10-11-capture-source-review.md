# Production capture and source review, 11 October 2026

Read-only audit; no historical rows deleted or rewritten.

Checked 3755 snapshots. 2343 match conservative known non-document patterns. This is not a complete content-quality audit.

| Reason | Flagged snapshots |
| --- | --- |
| registry_wrapper | 2175 |
| empty_text | 129 |
| rss_catalogue | 6 |
| dataset_metadata_or_resource_wrapper | 33 |

## Eight repaired source IDs

Every audited repaired ID had zero stored documents at this read. No actual ingestion success was established for these repairs. Config health and successful document discovery are separate.

| Source ID | Stored documents |
| --- | --- |
| site-07-sandiegocounty | 0 |
| site-17-sbcounty | 0 |
| site-09-miamidade | 0 |
| site-13-austintexas | 0 |
| site-05-hctx | 0 |
| site-15-dallascounty | 0 |
| site-19-tarrantcounty | 0 |
| site-20-bexar | 0 |

## Sixteen previously unresolved endpoints

| Source | Recorded state | HTTP read | Current conclusion |
| --- | --- | --- | --- |
| New York City Rules | cloudflare_blocked | 200 | Index returns 200, but sampled adopted-rule detail returns 403. Retain exclusion; no bypass. |
| Santa Clara County Planning & Development | cloudflare_blocked | 403 | Unresolved; excluded from operational coverage. |
| Alberta Gazette | cloudflare_blocked | 403 | Unresolved; excluded from operational coverage. |
| Calgary Land Use Bylaw | dead_link | 404 | Unresolved; excluded from operational coverage. |
| Publications du Québec | dead_link | ConnectionError | Unresolved; excluded from operational coverage. |
| City of Montreal Regulations | dead_link | 404 | Unresolved; excluded from operational coverage. |
| Greater London Authority Planning | cloudflare_blocked | 403 | Unresolved; excluded from operational coverage. |
| Glasgow City Council Planning | cloudflare_blocked | 403 | Unresolved; excluded from operational coverage. |
| The Edinburgh Gazette | dead_link | ConnectionError | Unresolved; excluded from operational coverage. |
| City of Melbourne Planning | dead_link | 403 | Unresolved; excluded from operational coverage. |
| UK data.gov.uk Catalogue API | blocked_403 | 403 | Unresolved; excluded from operational coverage. |
| Canada Justice Laws XML Index | unreachable | 200 | Headers returned 200; subsequent full XML download timed out. Retain exclusion. |
| Canada Justice Laws Website | unreachable | 200 | Endpoint responds; legal content and ingestion not established. Keep existing exclusion until verified. |
| New Zealand Legislation API | auth_required | 401 | Unresolved; excluded from operational coverage. |
| EU Publications Office CELLAR | dead_link | 404 | Unresolved; excluded from operational coverage. |
| Germany XML Table of Contents | unreachable | 200 | XML index downloads; links target XML ZIP archives, not current supported document extraction. Retain exclusion. |

A 200 index response is not a legal document or an ingestion proof. Temporary failures do not prove permanent disappearance. No config status was changed on reachability alone. CAPTCHA/auth-required sources remain excluded.

## Historical remediation plan

1. Keep the read-only manifest and backing snapshot/diff history.
2. Add a reversible searchable/quarantine status in SQLite and PostgreSQL with matching migration.
3. Quarantine only reviewed snapshot IDs and dependent diffs; preserve all raw text, capture dates and versions.
4. Update search/counts in both backends to exclude quarantined captures consistently.
5. Re-ingest official legal content under stable document/source IDs; do not generate amendments against invalid prior baselines.
6. Verify before/after counts and rollback by restoring visibility, never deleting snapshots.

Schema/search/quarantine implementation is committed and locally verified. Migration 009 has been applied to production, with both BOOLEAN defaults verified. Application release, explicit quarantine and source backfill are next. Manifest artifacts are ignored locally; this report contains aggregate evidence only. The older manual crawl record says running from 08:19 UTC, but a fresh process check found the crawl unit inactive and no run_crawler.py process. Checked dispatch/fallback is now implemented; the precise historical dispatch failure is unconfirmed.
