# Antigravity Handoff — JurisMon Fixes

Give these **one at a time, in order**. Do not give the next one until the
previous report has been verified.

Paste **Block A (standing rules)** at the top of *every* prompt, then the
numbered task below it.

---

# BLOCK A — Standing rules (paste every time)

```
You are working on JurisMon, a production system that is already live at
https://jurismon.com and already has real data in a Supabase database.

HARD RULES — breaking any of these is worse than not doing the task:

1. Change ONLY what the task says. No refactoring, no renaming, no tidying,
   no reformatting, no "while I was here" improvements. If you notice another
   problem, write it in your report and leave it alone.

2. Do NOT touch any of these unless the task explicitly says to:
   - .env, credentials/, any file with a key or password
   - db/migrations/*.sql
   - deploy/, scripts/vps_setup.sh, scripts/deploy.sh
   - .github/workflows/
   - config/sites.json, config/plans.json

3. Do NOT deploy. Do NOT ssh anywhere. Do NOT run git push.
   Local changes and local tests only.

4. Run `python -m pytest tests/ -q` BEFORE you start and AFTER you finish.
   Report both numbers. The after number must be >= the before number.

5. If a test fails after your change: STOP. Report the failure.
   Do NOT edit the test to make it pass. Do NOT delete or skip the test.
   A failing test means your change is wrong, not that the test is wrong.

6. Do not add new dependencies. Do not edit requirements.txt.

7. Keep the existing code style. This codebase uses plain functions, explicit
   names, and comments that explain WHY, not WHAT. Match it.

AT THE END, reply with exactly this report and nothing else:

REPORT
------
TASK:            <task number>
FILES CHANGED:   <list each file and the line range you touched>
WHAT I CHANGED:  <3-5 lines, plain description>
TESTS BEFORE:    <N passed>
TESTS AFTER:     <N passed>
NEW TESTS ADDED: <names, or "none">
VERIFY OUTPUT:   <paste the exact output of the verification command below>
ANYTHING ELSE I NOTICED: <or "nothing">
DID I TOUCH ANYTHING OUTSIDE THE TASK: <yes/no — if yes, say what and why>
```

---

# TASK 1 — Stop the site showing invented legal content

**Severity: BLOCKER. Do this one first.**

```
THE PROBLEM

frontend/index.html contains a constant called DEFAULT_DATA: eight fabricated
statutory amendments attributed to real government bodies (New York City Rules
& Planning, City of Los Angeles Planning Commission, Chicago City Council
Board, Houston City Council Commission, City of Miami Hearing Board, City of
Phoenix Council, Dallas Zoning Board of Adjustment, San Diego Land Use &
Housing).

The function fetchLiveSearch() falls back to DEFAULT_DATA whenever the API
returns no items — which happens on an empty database, on an API error, or on
a network failure. The page then displays those invented amendments, complete
with a redline diff, as though they were real.

This has already happened in production: a user searched and was shown
"§ 18-6, City of Phoenix Council, Ordinance 2026-09, Off-street parking".
The database contains zero Phoenix records.

This is a legal-monitoring product. Showing a fabricated amendment is worse
than showing nothing.

WHAT TO DO

1. Delete the DEFAULT_DATA constant entirely from frontend/index.html.

2. In fetchLiveSearch(), replace the fallback so that:
   - On a successful response, DATA = json.items (even when that is empty).
   - On a non-OK response or a thrown error, DATA = [] AND an honest error
     state is shown to the user — wording: "Could not reach the search
     service. Please try again." Do not invent content in any branch.

3. Make the empty state honest and distinguish the two cases:
   - Empty because the search matched nothing: "No amendments match that
     search."
   - Empty because nothing has been ingested yet (DATA empty AND the query is
     empty): "No amendments recorded yet. The crawler runs daily."
   There is already an #empty element in the page — use it.

4. Remove any other reference to DEFAULT_DATA left behind.

WHAT NOT TO DO

- Do not change the search, filter, sort or render logic.
- Do not change any CSS or layout.
- Do not touch frontend/admin.html.
- Do not change any API endpoint.

VERIFICATION — run these and paste the output

  grep -c "DEFAULT_DATA" frontend/index.html
  (must print 0)

  node --check <(python -c "import re,pathlib; print(re.findall(r'<script[^>]*>(.*?)</script>', pathlib.Path('frontend/index.html').read_text(encoding='utf-8'), re.DOTALL)[0])")
  (must print nothing — nothing means the JavaScript parses)

  python -m pytest tests/ -q
```

---

# TASK 1B — The page discards the search results the server found

**Severity: BLOCKER. Do this immediately after Task 1.**

```
THE PROBLEM

The server searches PostgreSQL with full-text search, which stems words: a
query for "parking" matches text containing "park", "parks" or "parked".

frontend/index.html then re-filters those results on line 941:

    const base = DATA.filter(d => toks.every(t => d.hay.includes(t)));

That is a literal substring test. A snapshot the server matched by stem, but
which does not contain the exact letters "parking", is thrown away.

Measured on production right now:
    GET /api/search?q=parking   ->  16 items
    the page displays           ->  0 results

The search runs twice, under two different sets of rules, and the stricter one
wins. Deleting DEFAULT_DATA exposed this; before that, demo data was being
filtered and the page looked like it worked.

WHAT TO DO

1. The server is the search engine. Results that arrive from /api/search must
   NOT be filtered again by the query. In getResults(), stop applying the token
   filter to DATA.

2. Keep everything else in getResults() exactly as it is: the filter pills
   (all / added / removed / snapshot), the sort, and the counts must still work
   on the server-returned set.

3. Keep the highlight regex `re` being built from the tokens - highlighting the
   query in the results is still wanted, and is independent of filtering.
   Highlighting a stem match imperfectly is fine; discarding it is not.

4. Check #summary still reads correctly, e.g. "16 results for “parking”".

WHILE YOU ARE IN THIS FILE, also fix these two leftovers:

5. Line 787: `let SOURCES = 50;` is declared and never used anywhere. Delete it.

6. Line 677: the header still contains the hardcoded literal
   `<span class="navcount" id="source-count">32 / 51</span>`.
   loadSourcesCount() overwrites it on boot, but if /api/sources fails the page
   keeps showing "32 / 51", which is a fabricated count. Change the initial
   content to an em dash so a failed fetch shows nothing rather than a number
   that was never true.

WHAT NOT TO DO

- Do not change /api/search or anything in api/.
- Do not change how DATA is fetched or assigned - Task 1 settled that.
- Do not change the sort, the pills, the rendering or the CSS.
- Do not add client-side search of any kind as a "fallback".

VERIFICATION — run these and paste the output

  grep -n "SOURCES" frontend/index.html
  (must print nothing)

  grep -n "32 / 51" frontend/index.html
  (must print nothing)

  grep -n "hay.includes" frontend/index.html
  (must print nothing)

  python -m pytest tests/ -q
```

---

# TASK 2 — Make the crawler identify itself honestly and configurably

**Severity: HIGH**

```
THE PROBLEM

There are three different User-Agent strings in this codebase and the wrong
one is the one that actually goes out:

  crawler/session.py:26   DEFAULT_USER_AGENT = "Mozilla/5.0 ... Chrome/128 ...
                          (JurisMon Statutory Monitor Bot; contact@jurismon.com)"
                          -> THIS is what production sends
  crawler/base.py:41      "JurisMonBot/1.0 (+https://jurismon.com/bot;
                          research@jurismon.com)"  -> effectively unused
  .env.example            CRAWLER_USER_AGENT=...  -> no code ever reads it

So JurisMon presents itself to 41 government websites as Chrome on Windows,
the contact address is inconsistent between files, and the one in .env does
nothing at all.

Three other documented settings are also never read: CRAWLER_DELAY_SECONDS,
CRAWLER_CONCURRENCY, HEADLESS_BROWSER. Their real values are hardcoded
(orchestrator max_workers=3, session default_delay=1.5).

WHAT TO DO

1. In crawler/session.py, change DEFAULT_USER_AGENT to the honest identifier:
       JurisMonBot/1.0 (+https://jurismon.com/bot; contact@jurismon.com)
   Remove the Chrome masquerade string entirely.

2. In crawler/base.py, change the fallback User-Agent to the SAME string, so
   there is exactly one value in the codebase. Define it in ONE place and
   import it in the other — do not leave two copies.

3. Make these four settings actually read from the environment, each with the
   current hardcoded value as the default:
       CRAWLER_USER_AGENT     -> the User-Agent above
       CRAWLER_DELAY_SECONDS  -> 1.5
       CRAWLER_CONCURRENCY    -> 3
       HEADLESS_BROWSER       -> true

   IMPORTANT: use `os.getenv("NAME", default)` read at the point of use, and
   where a function parameter also exists, the parameter default must be None
   so an explicit argument wins and the env var is still reachable. A truthy
   parameter default combined with `param or os.getenv(...)` is a bug that has
   already occurred in this codebase — do not reintroduce it.

4. Update .env.example so CRAWLER_USER_AGENT matches the new value.

WHAT NOT TO DO

- Do not change crawling logic, retries, rate-limit timing or any adapter.
- Do not change the headers dict beyond the User-Agent value.
- Do not touch tests/test_session_ocr_civicplus.py expectations except where
  they assert the old Chrome string; if one fails, report it rather than
  weakening the assertion.

VERIFICATION — run these and paste the output

  grep -rn "Mozilla/5.0" --include="*.py" . | grep -v venv
  (must print nothing)

  python -c "from crawler.session import SafeHTTPSession; from crawler.base import BaseCrawler; import crawler.base as b; s=SafeHTTPSession(); print('session:', s.user_agent); print('base   :', b.BaseCrawler(None).user_agent if False else 'see next'); print('match  :', s.user_agent)"

  python -c "import os; os.environ['CRAWLER_DELAY_SECONDS']='7'; from crawler.session import SafeHTTPSession; print('delay from env:', SafeHTTPSession().default_delay)"
  (must print 7.0)

  python -m pytest tests/ -q
```

---

# TASK 3 — A broken source must not report success

**Severity: HIGH**

```
THE PROBLEM

crawler/adapters/rest_api.py:32 — when the response is not valid JSON, the
adapter logs the error and returns []. BaseAdapter.crawl() then builds
CrawlResult(success=True, documents=[]).

So a source whose API starts returning HTML instead of JSON appears
"operational" on the dashboard with zero documents — indistinguishable from a
source that genuinely had nothing new. The same shape exists anywhere an
adapter returns [] after an error.

WHAT TO DO

1. In crawler/adapters/rest_api.py, when res.json() fails, raise instead of
   returning []. Raise a clear exception carrying the endpoint and the reason,
   e.g.:
       raise ValueError(f"Expected JSON from {endpoint_url} but could not
       parse it: {e}")
   BaseAdapter.crawl() already catches exceptions and records
   success=False with the message, which is the correct outcome.

2. Do the same review for crawler/adapters/xml_feed.py: if the response is not
   parseable XML, that must be a failure, not an empty list. Note: returning []
   because the document genuinely contains no records is CORRECT and must stay
   — only a parse or transport failure becomes an exception.

3. Add a test for each of the two adapters proving that a malformed response
   produces CrawlResult(success=False) with a message naming the source, and
   that a well-formed but empty response still produces success=True with zero
   documents.

WHAT NOT TO DO

- Do not change BaseAdapter.crawl().
- Do not change the other adapters (custom, municode, granicus, civicplus).
- Do not change the orchestrator.

VERIFICATION — run these and paste the output

  python -m pytest tests/ -q

  python -c "
from unittest.mock import MagicMock
from crawler.adapters.rest_api import RestApiAdapter
res = MagicMock(); res.json.side_effect = ValueError('not json')
s = MagicMock(); s.fetch_page.return_value = res
r = RestApiAdapter(session=s).crawl({'id':'t','name':'Test','base_url':'https://x.test'})
print('success:', r.success)
print('error  :', r.error_message)
"
  (success must be False and the error must mention the URL)
```

---

# TASK 4 — Record every crawl run

**Severity: HIGH**

```
THE PROBLEM

The crawl_runs table exists in the schema and in the SQLite fallback, but no
code ever writes to it — grep for "crawl_runs" finds only the table
definitions. A full production crawl has already run and the table is empty.

Combined with Task 3, this means that if the daily crawl stops running
entirely, or starts failing on every source, nothing in the system records it.

WHAT TO DO

1. Add two methods to db/repository.py, following the exact style of the
   existing methods (Supabase branch first, SQLite fallback after, same error
   handling shape):

       start_crawl_run() -> str
           Inserts a row with status='running' and started_at=now.
           Returns the run id.

       finish_crawl_run(run_id, status, total_sources, sources_succeeded,
                        sources_failed, documents_found, diffs_created,
                        error_logs=None)
           Updates that row with finished_at=now and the given counts.
           status is 'completed', 'failed' or 'partial_failure'.

   Use the columns that already exist in the crawl_runs table — read both
   db/migrations/001_initial_schema.sql and the SQLite schema in
   db/repository.py first and match them exactly. Do not add columns.

2. Wire them into scripts/run_crawler.py: call start_crawl_run() before the
   loop, and finish_crawl_run() at the end, inside a try/finally so a crash
   still records the run as 'failed'.

   Choose status as: 'completed' if sources_failed == 0, 'failed' if
   sources_succeeded == 0, otherwise 'partial_failure'.

3. Add tests covering: a run is recorded; the counts are stored; a crash still
   closes the run with status='failed'.

WHAT NOT TO DO

- Do not add columns to any table or write a migration.
- Do not change the crawling logic or the per-source loop.
- Do not change the notifications/ code.

VERIFICATION — run these and paste the output

  python -m pytest tests/ -q

  python -c "
import tempfile, os
from unittest.mock import patch
from db.repository import Repository
d = tempfile.mkdtemp()
with patch('db.repository.DatabaseClient.get_supabase', return_value=None):
    r = Repository(db_path=os.path.join(d,'t.db'))
    rid = r.start_crawl_run()
    r.finish_crawl_run(rid, 'completed', 41, 40, 1, 120, 3)
import sqlite3
print(sqlite3.connect(os.path.join(d,'t.db')).execute('select status, total_sources, sources_succeeded, sources_failed, documents_found from crawl_runs').fetchall())
"
  (must print one row with completed, 41, 40, 1, 120)
```

---

# TASK 5 — Clean up documentation drift and dead code

**Severity: MEDIUM / LOW. Do this one last.**

```
THE PROBLEM

Four settings documented in .env.example are read by nothing. Two of them
(PAYPAL_PLAN_ID_MONTHLY, PAYPAL_PLAN_ID_ANNUAL, PAYPAL_PRODUCT_ID) are
genuinely redundant because plans come from config/plans.json. HOST and PORT
are redundant because the systemd unit supplies them.

Two functions have no callers anywhere:
  crawler/base.py:45        compute_hash()   — duplicated by compute_sha256()
                                               in scripts/run_crawler.py
  diff_engine/models.py:52  to_dict()

NOTE: CRAWLER_USER_AGENT, CRAWLER_DELAY_SECONDS, CRAWLER_CONCURRENCY and
HEADLESS_BROWSER are NOT in this list — Task 2 makes those real. If Task 2 has
not been done yet, stop and say so.

WHAT TO DO

1. In .env.example, for PAYPAL_PLAN_ID_MONTHLY, PAYPAL_PLAN_ID_ANNUAL,
   PAYPAL_PRODUCT_ID, HOST and PORT: either delete them, or keep them with a
   comment saying exactly where the real value comes from. Prefer a comment
   for the PayPal ones (they are useful as a record) and deletion for
   HOST/PORT. Do not change any value.

2. Delete compute_hash() from crawler/base.py. Confirm first that nothing
   references it.

3. Delete to_dict() from diff_engine/models.py. Confirm first that nothing
   references it.

WHAT NOT TO DO

- Do not delete anything else, however unused it looks. Ask instead.
- Do not touch .env (only .env.example).
- Do not change config/plans.json.

VERIFICATION — run these and paste the output

  grep -rn "compute_hash\|to_dict" --include="*.py" --include="*.html" . | grep -v venv
  (must print nothing)

  python -m pytest tests/ -q
```

---

# After each report, send me:

1. The REPORT block exactly as returned
2. The output of: `git diff --stat`

I will verify and confirm before you move to the next task.
