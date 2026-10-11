# JurisMon rigorous testing v2, 11 October 2026

## 0. Regression table first: all 25 previous items

Numbers in this table are from docs/ai/frontend-fix-plan.md, batches 1-3.
They are not the different numbering used by the pasted QA report's full table.
Status describes what was actually verified; local and production are separate.

| # | Page | Prior finding | Status | Fresh repro / evidence |
| --- | --- | --- | --- | --- |
| 1 | /api/search?q= | Paywall payload leak | Fixed | Anonymous response gated, 2 items, no results key; genuine admin response ungated, results key retained, 31 items. 1,605 versus 525,878 JSON-serialized UTF-8 bytes, not wire bytes. |
| 2 | / and /about | Claims versus content | Partially fixed | About now admits local/international scope. Homepage still says municipal/county; all ten selected source links are national government sources, no municipal/county. First eight previews unfit as legal text. |
| 3 | /admin Plans | Silent 409 errors | Fixed | Both actual production 409s: price mismatch and last-active guard. #toast-text contains the exact rejection within 2s. Screenshots and response statuses saved. |
| 4 | /admin Plans | Missing price history release | Fixed | Authenticated /api/admin/plans/changes returns 200; #plan-changes-body exists. Real name edit creates a row showing Professional to Professional QA verification, then name restored. |
| 5 | / | Giant result cards | Fixed | Measured all 31 real authenticated collapsed cards: 129.48-250.08px. Anonymous cards about 207-208px. Intentional full expansion/deep links remain possible. |
| 6 | / | Navigation/catalogue previews | Still broken live | Eight newest records inspected: seven page-furniture/catalogue wrappers and one empty NZ snapshot. Detailed source/section table below. Deployed extraction guards do not establish clean stored data or every adapter path. |
| 7 | /account | Subscribe button dead end | Partially fixed | Current local checkout-path/provider tests pass and selection UI is reachable; no live subscription was created or PayPal approval/payment completed. Actual charged checkout remains untested under prompt restrictions. |
| 8 | / | Logged-in placeholder flash | Fixed in covered cases | Current genuine local browser session/delayed-request tests pass; authenticated return captures immediately and after 2s show real results without logged-out controls. Not a live customer-mailbox login test. |
| 9 | HTML/API | Missing Cache-Control | Fixed | Fresh live HTML no-cache, authorized API no-store. Existing endpoint-specific anonymous policy tests included in regression. |
| 10 | HTML/API | Missing compression | Fixed in checked responses | Fresh live four HTML pages plus >1KB authorized sources/search responses gzip. 220-byte plans response uncompressed, appropriate for size. No claim that every unlisted endpoint was sampled. |
| 11 | /api/search | Variable latency | Partially fixed | Fresh identical anonymous zoning calls: 637.69, 420.25, 391.84ms. Live worker-pool change plus passing slow-search/health tests; no query-plan evidence or guaranteed latency target. |
| 12 | /admin Sources | Broken source coverage | Partially fixed | API metadata 49/65 operational, 19/21 US operational, compared with original 41/65 and 11/21. NYC Rules/Santa Clara blocked. Eight configs repaired; their completed ingestion not yet proven. |
| 13 | /admin | Crawl polling | Fixed in covered cases | Real manual crawl observed running, 17 successful status responses across >60s without reload. Local 31s run/terminal polling captured. Final live run still running, completion not claimed. |
| 14 | / | Mobile overflow | Fixed in measured cases | Six live pages, widths 375/768/1280/1920, light/dark: 48 measurements, zero page overflow. Genuine local authenticated header/pill tests pass. |
| 15 | Six pages | Dark mode missing | Fixed in measured cases | Fresh prefers-color-scheme light/dark page checks; local trial and four paid states. Readability still subject to manual/incomplete contrast review. |
| 16 | / auth | OTP field shifts on error | Fixed locally verified | Current genuine wrong-code browser responses tested at 375 and desktop with field/focus stability; no live external-mail signup in this round. |
| 17 | /admin Webhook log | Only one webhook | Fixed / confirmed non-defect | Live tab loads one event; live subscriber count zero. Quantity alone is not an application defect or evidence of working paid webhooks. |
| 18 | Auth forms | Clear errors | Partially verified | Current local invalid/nonexistent password 401, duplicate registration 400, wrong OTP 400, native empty validation and reset200 with captured mail. Failed-delivery success claim reproduced, so not an all-path pass. Live external inbox flows not attempted. |
| 19 | / search | XSS escaping | Fixed in covered inputs | Fresh live script and quote-breakout searches returned no result HTML and executed no dialog. Existing escaping/security regressions also pass; not an exhaustive stored-XSS audit. |
| 20 | /account | Tampered JWT | Fixed | Actual tampered localStorage JWT on live page produces clean signed-out account screen. |
| 21 | / | Scoped search failure | Fixed | Browser route abort only search: page shell remains usable, specific service-error message, no persistent skeleton. |
| 22 | Public pages | API counts/prices agree | Partially fixed | Displayed 49/65, trial14, $49/month/$468/year agree with current APIs. Numeric agreement does not prove ingestion; municipal-only wording/admin run claims remain wrong. |
| 23 | /account | Paid-state testing gap | Partially covered | Real isolated accounts/subscriptions across 3 engines, 2 widths/themes; transitions with mocked PayPal. Actual provider/mailbox agreement not proved. One Firefox navigation timeout, isolated reruns pass. |
| 24 | Search/account | Cross-browser gap | Partially covered | Fresh live Chromium/Firefox/WebKit search, zero/clear/filter/gate/account checks and local authenticated matrix. Native Safari/physical mobile browser not attempted. |
| 25 | Accessibility | Automated audit gap | Partially fixed | Local current code: 84 axe views, zero confirmed violations. Live old release: critical admin label and serious role/dialog defects below. No Lighthouse score; axe has no numeric score. Manual keyboard found a closed-dialog focus defect. |

## Environment, method and raw evidence

- Production: https://jurismon.com, health version e33ef18, database ok.
- Development accessibility fixes: b67560f, not deployed during this round.
- Playwright 1.63.0, actual Chromium/Firefox/WebKit, Windows. No engine
  installation needed. Mobile viewport emulation is not a physical device test.
- Unthrottled network; no root cause attributed to client/VPS/network latency
  without direct evidence. Fonts and finite animations settled for measurements.
- Local backend: isolated genuine Uvicorn/SQLite accounts/JWTs. Billing mocked,
  mail captured/disabled. No paid subscriptions, charges, live lifecycle calls
  or emails to uncontrolled recipients.
- Production writes explicitly exercised by the requested prompt: display-name
  edit then restoration, brief annual-catalogue deactivation then restoration
  to test the last-active refusal, and one manual crawl. Monthly offer remained
  active; final two plans/names/prices/trial restored. Audit rows intentionally
  preserve these real changes. No price or existing subscription changed.
- Evidence directory: ignored test-results/rigorous-v2/. Raw JSON, screenshots
  and audit scripts remain local; no credentials or tokens belong in this report.
  live.json, admin.json, last-active.json, links.json, final-state.json,
  engines.json, local-extra.json, mail-failure.json, focus-hidden.json,
  local-crawl-31s.json, axe-live-*.json and firefox-reruns.txt.
- Earlier audit harness errors were corrected: owned browser contexts, real
  logout, visible expand-control selector, and crawl waiter endpoint. The
  application uses /api/admin/crawl/run, not /crawl/trigger. The initial waiter
  timeout is not evidence of a failed crawl: subsequent real polling/status
  proves it started. No second crawl triggered.

## 1-10. Findings grouped by page

| # | Page | Finding / expected behavior | Severity | Repro steps and repetition |
| --- | --- | --- | --- | --- |
| F1 | / latest results | Seven of first eight captured previews are page furniture; the eighth is empty. Expect actual legal text or explicit unsupported-source state. | High | Chromium, genuine admin search?q=, newest first; inspect first eight and open sources. Repeated matching anonymous wrappers on search/clear. authenticated-home.png, previews.json. |
| F2 | / headline and preview banner | Says live municipal/county portals although all ten sampled result URLs are national registries. About intro is more accurate. Expect consistent scope/ingestion claims. | High | Signed out and real admin; home + /about + /api/sources. Across three engines; home.png, authenticated-home.png, sources data. This is a sample of newest results, not the entire corpus. |
| F3 | /admin Overview | Ingestion runs today shows 49/65 operational sources. Last daily run says 11 days ago while actual crawl status has a completed run earlier today. Expect genuine run count/date. | Medium | Genuine admin, Sources/Plans, compare overview with /api/admin/crawl/status. Repeated admin captures. live-plan-history.png + admin.json. Direct code reads confirm #k-runs uses ok/total source counts and run-meta uses source timestamps. |
| F4 | /admin signed-out | axe label Critical on #login-email; aria-prohibited-attr Serious on #k-bars; region Moderate. Expect properly named controls/valid roles and landmarks. | Medium | Open signed out, run full axe default rules. Both light/dark, axe-live-*-admin.json. Fixes exist locally, not live. |
| F5 | / auth dialog | aria-dialog-name Serious: referenced heading missing in live markup. Expect named dialog. | Medium | Live homepage full axe, light/dark; axe-live-*-home.json. Local fix exists but not deployed. |
| F6 | /account signed-out | No h1, axe page-has-heading-one Moderate. Expect a visible top-level page heading. | Low | Live signed-out account, light/dark axe; current local h1 fix not live. |
| F7 | / keyboard | Tab enters invisible auth-modal-close while dialog is closed/opacity0. Expect closed dialogs removed from tab order and focus only in visible UI. | Medium | Signed-out Chromium, Tab through homepage without opening dialog. Observed in initial focus traversal and reproduced again, focus-hidden.json + keyboard-hidden-auth.png. Computed outline exists but its ancestor is invisible. |
| F8 | / auth signup/resend, local | Provider returns false, but signup/resend200 promise mail sent; failed resend replaces previous usable code and old code then returns400. Expect accurate delivery failure and preserved usable code. | High | Genuine isolated browser/backend, mailer false, register then resend then verify previous code. One explicit failure scenario, local-failed-delivery-code-screen.png + mail-failure.json; code read confirms ignored send return. Not reproduced against live mail provider. |
| F9 | /account local Firefox | One cancelled-expired/dark/375 test failed at goto load after30s. Expected normal navigation. | Medium, unconfirmed reproducibility | Full suite under concurrent live-browser audits: one occurrence; exact case passed 3 isolated reruns. No unsupported CPU/network/browser root cause assigned. firefox-reruns.txt plus full pytest output. |

### Worst five, with priority reasons

1. F1 legal-content quality: the core searchable product is unreliable even
   when every control works, so it leads onboarding and interface findings.
2. F8 false delivery success: under delivery failure a new user cannot verify
   and resend can invalidate the usable code, ahead of copy-only inconsistencies.
3. F2 scope mismatch: misleads the business promise and buyer expectations,
   broader than the affected accessibility controls.
4. F4/F5 undeployed accessibility fixes: actual critical/serious live issues
   affect form/dialog identification, ahead of the separately found focus trap.
5. F7 invisible keyboard focus: makes keyboard navigation confusing even after
   the semantic fixes; admin metric diagnostics are lower priority here.

### Eight content previews read individually

| Position | Source / document / section | Observed text quality |
| --- | --- | --- |
| 1 | Germany Gesetze im Internet, Aktualitaetendienst, Paragraph1 diff | Startseite, navigation, RSS subscription instructions; not a statute clause. |
| 2 | Same German document, Snapshot v6 | Same navigation/RSS catalogue wrapper. |
| 3 | New Zealand Resource Management Act1991 XML, Snapshot v11 | Empty text and full fields; source navigation produced202/empty in this run. |
| 4 | Canada PIT bulk XML, DCAT(XML), Snapshot v11 | Dataset description/download instructions, not legal text. |
| 5 | Canada PIT, Data DictionaryHTML French resource, Snapshot v11 | Go to resource, no views, metadata. |
| 6 | Canada PIT, Data DictionaryHTML English resource, Snapshot v11 | Same resource wrapper/metadata. |
| 7 | Australia, Telephone Regulations(Amendment)(Provisional), Snapshot v7 | Text/Details/Authorises/download/account controls and title wrapper. |
| 8 | Australia, War Pensions Act1914, Snapshot v7 | Title navigation, account controls and document selectors, not body clauses. |

These observations do not establish whether each record is historical-only
contamination or a still-active ingestion bypass. Some captured timestamps are
recent; inspect adapter route and actual release/run timestamps before cleanup.

### Ten source-document links opened

All ten distinct selected result URLs were attempted in a real browser:
one German national catalogue, one NZ national XML route, three Canadian
national data routes, five Australian federal titles. **0 municipal/county,
10 national/federal** by official host/source classification. This classification
does not imply all ten loaded successfully.

- Seven returned200; NZ returned202 and empty visible text.
- Canadian DCAT XML started a download, not a rendered HTML page.
- One Canadian French resource timed out at20s; another English resource loaded
 200. A single client-side timeout is not proof of a permanently dead source.
- Exact URLs, titles, final URLs, status/error and text excerpts: links.json.

### Performance, claims, controls and edge cases

- Actual navigation/first-content/load timings for /, /about, /account, /admin
  and the other pages are in live.json. First light homepage: TTFB4584.5ms,
  first-contentful-paint6016ms, load7529ms. It is one observed cold navigation,
  not a controlled benchmark or a diagnosed server defect.
- Anonymous versus admin sizes above are JSON serialization sizes. Live raw
  gzip headers observed for four HTML pages and source/search responses;
  authorized API no-store is expected. The small plans response needs no gzip.
- Public trial14 and prices49/month,468/year match API. Metadata counts49/65
  and19/21 US operational agree, but stored labels are not proof of legal
  ingestion/freshness for every source.
- About names existing adapters/OCR; repository contains these implementations.
  Live wrapper records disprove universal successful stripping; no OCR success
  on a particular production record was claimed without an actual sample.
- Three engines: parking/zoning200 with2 gated cards; zero query200 with0;
  clear restores2; labels match rendered filter counts (0 added/removed,
  1 snapshot,2 all). Locked full-section opens registration gate, consistent
  with needing an account. No real checkout/payment approval attempted.
- Copied genuine admin result URL opened in new tab and rendered the exact
  target's full details; live-deep-link.png. Local genuine user equivalent
  also renders full details. Intentional expansion can be large.
- Search-only network abort and true context offline show a specific error
  instead of an infinite skeleton. Shell remains available; offline screenshot
  captures the failed search on a previously loaded page, not an offline
  first-ever navigation to an uncached site.
- Script/quote-breakout inputs executed no alert and returned no injected
  result HTML. Tampered JWT gets a clean account login screen.
- Source rows, Subscribers, Plans/history and Webhook tab load real data.
  Both 409s visible within2s; actual name history row verified and restored.
- 48 live responsive measurements, no page overflow. Local CSS zoom2 reflow
  approximation passed all six pages; actual browser UI200% zoom not established.
- All sampled images have alt attributes. Homepage/account/admin have live
  regions; page-specific static informational pages do not need live regions.
  Complete icon-only control naming and manual screen-reader coverage remain
  outstanding beyond axe, rather than silently marked passed.

### Cache-disabled hard-refresh timings and anonymous headers

Chromium CDP Network.setCacheDisabled true, then reload, unthrottled client
network. Single measurements, not a server benchmark or a diagnosed cause.

| Page | TTFB ms | First contentful paint ms | Load ms |
| --- | --- | --- | --- |
| / | 826.40 | 1236 | 1626.90 |
| /about | 265.70 | 560 | 688.60 |
| /account | 396.50 | 672 | 787.90 |
| /admin | 247.60 | 504 | 609.70 |

Anonymous requests: / no-cache, encoding gzip (83698 decoded bytes); /about no-cache, encoding gzip (26896 decoded bytes); /account no-cache, encoding gzip (36635 decoded bytes); /admin no-cache, encoding gzip (91700 decoded bytes); /api/sources public, max-age=60, encoding none (50 decoded bytes); /api/plans no-cache, encoding none (220 decoded bytes); /api/search?q= no-store, encoding gzip (1529 decoded bytes).
All sampled HTML/JSON responses over1KB had encoding. Raw evidence: hard-refresh.json.

## Test result and remaining verification limits

- Full current regression: **450 passed,1 failed,1 warning,569.16s**.
  Firefox cancelled-expired/dark/375 timed out at navigation;3 isolated reruns
  passed in9.60/8.23/8.28s. Do not rewrite the full result as451 passed.
- Additional isolated observation checks:2 completed in60.68s; mail failure
  capture1 completed in5.25s. Their completion records defects too.
- Full local axe:84 views,0 confirmed violations; incomplete contrast requires
  manual review. Live axe six pages/light-dark: defects listed above. axe
  reports have no numeric score; Lighthouse was not run.
- No controlled external inbox was provided. Signup/resend/reset and lifecycle
  email delivery were tested locally/captured, not proved live delivered.
- No PayPal Sandbox credentials supplied. Real provider lifecycle/state/email
  agreement and paid checkout intentionally not tested; no live charges made.
- Native Safari/physical mobile and screen readers remain untested. Browser
  engines plus mobile viewports do not close those gaps.
- Final live release still e33ef18; trial14; both original active offers restored;
  requested manual crawl still running. Its eventual ingestion/final state
  requires follow-up and is not included in successful UI polling evidence.

Task ownership and next work: [remaining-work](../ai/remaining-work.md).
Implementation/release ledger: [implemented-work](../ai/implemented-work.md).
