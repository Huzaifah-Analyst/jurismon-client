# Case studies: evidence and publication

Prepared 11 October 2026. The page is `/case-studies`; summaries are authored in
`config/case_studies.json`. Publication requires a stored, searchable capture at
the specified official URL containing the reviewed legal section identifiers.
The API returns the capture version/date and public summary, not full captured text.

| Written example | Official evidence | Production capture verification |
| --- | --- | --- |
| Austin preservation-bonus rule | [Adoption notice and attached rule](https://services.austintexas.gov/edims/document.cfm?id=478413), [city listing](https://www.austintexas.gov/development-services/development-policy-corner) | Relevant sections matched internally; version 1 captured 11 October 2026 at 13:53:09 UTC. |
| San Bernardino Ordinance 4400 | [Official ordinance](https://lus.sbcounty.gov/wp-content/uploads/sites/48/DevelopmentCode/ORD-No-4400-WEB.pdf), [county listing](https://lus.sbcounty.gov/planning-home/development-code/) | Relevant sections matched internally; version 1 captured 11 October 2026 at 14:03:35 UTC. |

These are real source-document review examples supported by the ingestion pipeline.
Both captures are baselines. No before/after pipeline diff or customer savings is
claimed. Legal dates come from official notices/listings and are separate from
capture dates. Historic documents do not establish the latest applicable law.
Customer/vote-based market validation requires actual customer or voting evidence;
it cannot be inferred from two source-document captures.

If a supporting capture is quarantined or missing, its case is withheld. A storage
error returns 503 and the page offers retry; an unavailable database cannot publish
an example from unrelated local data. Verification artifacts contain supporting
booleans/timestamps only, with no production document excerpt export.
