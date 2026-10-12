# P2-16 implementation and live evidence — 12 October 2026

Order: [P2-16](../ai/orders/ORDER-P2-16.md). No client push, deployment or
production cleanup has happened. Production health remains `e2693b7`.
This is a reviewable implementation, not a claim that all live defects are closed.

## Changes and acceptance

| Item | Implemented / measured | Production acceptance still needed |
|---|---|---|
| N1 huge expanded document | `.full-box` max-height 70vh, own vertical scroll and contained overscroll. Genuine local authenticated browser rendered >500k characters, checked bounded height, overflow and scrollTop. | Deploy with sign-off, expand Crimes Act snapshot `1311845b-3c04-420f-b940-419f49691aa2` and capture actual live DOM dimensions. Read-only live review confirms its 505330-character payload still exists. |
| N2 bot-check capture | Exact robot/JavaScript-language guard used by ingestion and historical audit. Fixture audit quarantines without deletion and excludes from search. | Run existing `audit_capture_quality.py --apply` with reviewed manifest after staging/sign-off; live NZ snapshot `ef0c9afc-6e7d-48a2-9aec-35e38c5b3dc1` is freshly flagged by new guard but remains unchanged. |
| N3 Ontario pager titles | Static and browser discovery skip navigation labels. Stored-text repair prefers actual Ontario Gazette volume/issue/date; explicit unlabeled fallback otherwise. Compare-and-set title updates preserve snapshots in SQLite/Supabase. | Apply `repair_document_titles.py --apply` after review; live metadata review found ten matching entries, including Last page and Page1–Page9 (report originally said nine). Recovered actual issue titles from current live bodies. |
| N4 generic UK titles | Atom prefers alternate instrument link. Title extraction prefers instrument headings and joins wrapped legal titles. Re-ingestion corrects only known bad existing titles; same repair CLI supports historic rows. | Apply reviewed correction and verify actual live distinct titles. Read-only derivation recovered Firearms Rules 2026 and the full distinct Welsh food-regulation title ending 2025, without exporting body text. |
| Prior 2 content mix | No ranking, coverage-count or product-positioning changes. | Lead engineer decides source repair versus permanent disclosed mix. |
| Prior 11 variance | Actual authenticated live browser fetch/JSON timings for three identical `zoning` requests: **6939.30 / 4445.30 / 4685.50 ms** (1.56x). Follow-up: 5254.10 / 3770.10 / 3893.20 ms (1.39x). All HTTP 200, ungated, 30 returned items, 48 matching snapshots, zero diffs. | Absolute latency remains high. No query-plan tuning performed; observed variance below the order's roughly 2x investigation threshold. |
| Prior 12 source instability | Configurable document read timeout defaults to 60 seconds (previously 20); existing bounded retries remain. Five US sources and actual linked PDF responses probed; see below. TLS verification retained. | Timeout improvement is local and not deployed; no successful production ingestion claimed from page/PDF HTTP responses. NYC access and Clark selectors/certificate remain open. |
| Prior 13 polling | Triggered real production admin crawl; watched 35.06 seconds without reload: 11 automatic status requests, all HTTP 200, ~3.4–3.7 seconds apart after initial calls. Follow-ups show continuing requests while running. | No polling fix needed. Terminal-stop behavior covered by existing isolated regression; not observed live in that 35-second window. |

## Per-source diagnostics

| Source | Fresh outcome | Decision |
|---|---|---|
| NYC Planning | Landing page HTTP 403 | Access issue open; no bypass, no claim repaired. |
| San Diego Planning | Landing HTTP 200, 16 matching links; Update97.pdf HTTP 200, PDF signature, 1277567 bytes | Download now reachable from tester; configurable timeout improvement ready. Production ingestion/storage requires follow-up. |
| Clark County Planning | Landing HTTP 200 but zero configured-selector matches | Existing homepage selector does not discover legal documents; replacement endpoint work remains. |
| Clark file host | HTTPS verification fails; direct default-trust/SNI socket reports self-signed certificate. Public peer-certificate inspection: subject and issuer both `CN=WMSvc-SHA2-INSTANCE-202109`; its self-signature verifies, expiry 2031-09-19. | Genuine self-signed endpoint certificate, not merely a missing intermediate CA. Keep file host excluded until its certificate/official endpoint is repaired; do not mark entire county unreachable. Certificate-only diagnostic read an untrusted peer certificate; document downloads still require full TLS verification. |
| Travis Permitting | Landing HTTP 200, 3 matches; linked permit-waiver PDF HTTP 200, signature, 2641683 bytes | Reachable document, not evidence of amendment ingestion or extraction quality. |
| Austin Code | Landing HTTP 200, 20 matches; document.cfm?id=478413 HTTP 200, PDF signature, 367199 bytes | Reachable document handler; existing PDF-signature path retained. |

Live source probes were selected for US county/city value, not claimed to be
the current five highest failure counts. The crawler was still running at the
end of the polling window, so this order does not invent its final per-source
ingestion outcomes.

The 60-second document timeout increases worst-case crawl duration (up to three
bounded attempts plus backoff per failed fetch). It is configurable and does not
resolve 403s, bad certificates or missing selectors. No endpoint is marked healthy
solely because a longer timeout was configured.

## Test and release evidence

- Initial targeted capture/extraction/browser run: 32 passed.
- Expanded target including network/Supabase/schema contracts: 84 passed.
- First full run: 506 passed, one Firefox `BrowserType.launch` timeout at setup,
  one existing Starlette warning; no passing full-suite claim from that run.
- Second full run: **509 passed, one Firefox account Page.goto timeout**, one
  existing warning; also not a passing full-suite result.
- Final focused run: **9 passed in 38.41 seconds**, including both earlier
  Firefox failures and all final P2-16 cases. No skip or retry plugin. The two
  earlier timeout root causes remain unconfirmed.
- Final complete acceptance run: **510 passed, one existing Starlette warning,
  400.53 seconds**. `test-results/p2-16/full-suite-acceptance.xml`. No skips or
  retry plugin; fail-fast enabled but not triggered. Earlier failed runs remain
  documented above rather than replaced with an unsupported root-cause claim.
- Both actual title-repair and quarantine CLIs passed against an isolated local
  database: title manifest saved, exact bot row quarantined, captures preserved,
  visible snapshot count corrected. No production mutation.
- Final artifact run: **7 passed in 4.32 seconds**. Local expanded full-box height
  504px (70vh), clientHeight 502px, scrollHeight 156237px, overflowY auto; setting
  scrollTop to 500 succeeds. These are local fixture measurements, not live
  Crimes Act dimensions after deployment.
- Live zero-match query: HTTP 200, zero items/snapshots/diffs. Browser empty-state
  and filter click checks after deployment remain separate acceptance steps.
- Evidence (ignored): `test-results/p2-16/live.json`,
  `live-document-probes.json`, `capture-review.json`, and suite XML files.
  Local expanded-document screenshot and measured DOM:
  `expanded-document.png`, `expanded-document-dom.json`.
- User confirmed no separate staging exists and corrected the order: local
  acceptance is sufficient before review; production remains sign-off gated.

## Release sequence requiring approval

1. Complete local real-server acceptance and final tests (user-corrected sequence).
2. Review title-repair dry run and capture-audit manifest.
3. Obtain explicit client-remote push and VPS deployment sign-off as required by
   this order; no production mutation is implied by passing local tests.
4. Deploy, apply reviewed reversible quarantine/title repairs, then repeat each
   original live reproduction and search empty/filter checks.

Implementation does not include P2-17 PayPal/inbox tests or a new product decision.
