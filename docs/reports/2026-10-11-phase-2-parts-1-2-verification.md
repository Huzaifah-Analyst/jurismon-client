# Phase 2 Parts 1 and 2 — verification, 11 October 2026

Tests ran against actual application HTTP handlers and temporary SQLite databases.
Browser actions used genuine login/JWT authentication and real server state.
PayPal and email boundaries were mocked; no real payment, lifecycle operation,
or mail delivery was performed. Production and the user's local plans file were
not edited. This report does not certify real PayPal or inbox outcomes.

## Numbered manual checklist results

| # | Check | Evidence and result | Remaining verification |
|---|---|---|---|
| 1 | Account gate and login | Browser: signed-out gate, hidden pause control, wrong password error, correct form login passed. | None for the exercised local flow. |
| 2 | Trial account | Browser: trial overview, email, upgrade control and refresh passed; backend verifies configured expiration. | None for the exercised local flow. |
| 3 | Active paid details | Real database-backed account screens and account endpoint passed. | Compare displayed amounts/dates with a genuine Sandbox subscription. |
| 4 | Dismiss pause | Browser dismissal leaves active state and makes zero provider calls. Passed. | None for the exercised local flow. |
| 5 | Confirm pause | Browser: paused state, same ID, refresh passed; backend confirms access deadline and paid search access. | Genuine Sandbox SUSPENDED status. |
| 6 | Pause email | Exactly one mail submission with real application figures passed. | Actual inbox receipt NOT tested. |
| 7 | Resume | Browser: active state, same ID, refresh, one provider call and one additional mail submission passed. | Genuine Sandbox ACTIVE status and inbox receipt. |
| 8 | Abort cancellation | Browser: modal opens/closes; zero cancellation provider calls. Passed. | None for the exercised local flow. |
| 9 | Confirm cancellation | Browser: reason submission, cancelled state, refresh, continued paid search access and one mail submission passed. | Genuine Sandbox CANCELLED status and inbox receipt. |
| 10 | Subscribe Again | Browser navigates to real checkout dialog; original subscription remains cancelled. | Approve a new Sandbox subscription and verify its distinct ID. |
| 11 | Expired paid access | Browser expired screen and real search API gating passed in three engines. | No real billing clock/payment event was exercised. |
| 12 | Admin Plans authorization | Genuine admin browser authentication and Plans cards passed; backend rejects customer writes. | None for exercised authorization checks. |
| 13 | Edit fields and discard | Browser name/price edits discarded; status/provider-ID fields visible; refresh and public catalogue unchanged. Passed. | None for the exercised local flow. |
| 14 | Price mismatch | Backend rejects 59 against provider 49 with 409; no audit row. Browser errors visible in light/dark modes. Passed with mocked provider. | Genuine Sandbox plan comparison. |
| 15 | Valid new price | Backend accepts matching provider price 59, invalidates catalogue cache, persists change and writes audit. Passed with mocked provider. | Browser save of a new provider ID and actual new-subscriber Sandbox charge. |
| 16 | Old/new subscriber prices | Existing test confirms inactive legacy plan still resolves a subscriber's plan name/price. Partial coverage only. | Explicit old-customer 49/new-customer 59 comparison and actual provider billing remain unverified. |
| 17 | Change history | Backend checks old/new values, multi-field rows, newest-first ordering, authentication and absence of refused/unchanged rows passed. | Full browser refresh inspection of a successful edit's history remains unperformed. |
| 18 | Global trial setting | Backend admin setting 34 reaches public offer and new trial; browser wording tested at 14/34/45/67/0. Existing trial expiration remains unchanged. Passed in isolated fixtures. | A single browser admin-save 34→14 sequence across every wording location remains unperformed; real configuration was preserved. |

## Executed evidence

- Initial targeted run: **77 passed**, one existing Starlette deprecation warning.
  `test-results/phase2-acceptance.xml`.
- Browser run: **60 passed**, 26 deselected. Includes 48 account-state cases:
  Chromium/Firefox/WebKit × 375/1280 widths × light/dark × four account states.
  `test-results/phase2-browser.xml`.
- Account-state screenshots: `test-results/qa-23-25/account/` (ignored artifacts).
- New regression test: `tests/test_phase2_browser_acceptance.py`. Customer actions
  are executed sequentially; an independent admin test verifies edit discard.
- Final rerun verifies the checkout dialog itself rather than only its URL;
  result recorded in `test-results/phase2-sequential-final.xml`.

No application defect was found in the exercised flows. No application behavior
was changed by this verification work. The original offer's automatic PayPal plan
creation/update and existing-customer opt-in migration are still implementation
gaps; passing catalogue validation tests does not establish those features.
