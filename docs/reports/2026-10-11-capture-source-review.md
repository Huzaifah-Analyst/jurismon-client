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

## Executed remediation and source-only backfill

- Verified release 0c8d0a4 deployed; truthful ingestion-outcome follow-up ea54057
  deployed before backfill. Quarantined 2343 snapshots and 1852 dependent diffs,
  preserving all 3755 snapshots and 2647 diffs. Visible counts after quarantine:
  1412 snapshots and 795 diffs. Restore manifest exists on VPS and locally, ignored.
- Crawl 83e4a73e-52cb-4dd6-a5d2-d127e4ce5069 ran 13:31:23–14:05:09 UTC,
  status partial_failure: 8 attempted sources, 7 succeeded, 1 failed; 76 discovered
  documents, 60 actual new baseline captures and zero new diffs. Mail disabled.
- Stored captures: San Bernardino 21, Austin 20, Miami-Dade 12, Harris 2,
  Dallas 2, Tarrant 2, Bexar 1, San Diego 0. San Diego's 16 PDF downloads timed out;
  browser listing discovery succeeded but did not prove document ingestion.
- Final raw totals: 3815 snapshots and 2647 diffs; visible 1472 and 795. The 60
  new baseline captures explain the snapshot increase. Unflagged does not certify
  every document's legal completeness. Austin/San Bernardino case sections were
  separately checked internally and matched; no production excerpts exported.
- Old unconfirmed run 95abf92c-e156-4dd5-a2b8-e5ac6fd3f6ad was marked failed by
  existing stale-run recovery at 13:31:23 UTC; it was not counted as completed.
- Updated only eight relevant config status blocks from actual results; San Diego
  is degraded with daily retries enabled. Config/live synchronization is recorded
  after release, not assumed. Sixteen inactive endpoints remain explicitly excluded.
