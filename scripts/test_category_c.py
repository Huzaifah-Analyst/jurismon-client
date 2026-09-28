"""JurisMon Category C (WAF / 403 / JS Rendering) Verification Suite.

Tests all 12 Category C sites using the Stealth Playwright Browser Fallback.
Iterates and verifies document extraction across these protected municipal portals.
"""

import sys
import json
import time

# Add project root
sys.path.insert(0, ".")

from crawler.session import SafeHTTPSession
from crawler.adapters.custom import CustomAdapter
from crawler.playwright_crawler import PlaywrightCrawler


def test_category_c_sites():
    print("\n" + "=" * 75)
    print("      JURISMON CATEGORY C (WAF / 403 BYPASS) RE-TESTING SUITE      ")
    print("=" * 75 + "\n")

    # The 12 Category C sites identified in the audit
    category_c_sources = [
        {"id": "site-01-cityofnewyork", "name": "New York City Rules", "base_url": "https://rules.cityofnewyork.us", "use_browser": True},
        {"id": "site-05-hctx", "name": "Harris County Engineering & Permits", "base_url": "https://www.eng.hctx.net", "use_browser": True},
        {"id": "site-16-rctlma", "name": "Riverside County Land Management", "base_url": "https://rctlma.org", "use_browser": True},
        {"id": "site-20-bexar", "name": "Bexar County Texas", "base_url": "https://www.bexar.org", "use_browser": True},
        {"id": "site-21-sccgov", "name": "Santa Clara County Planning", "base_url": "https://www.sccgov.org/sites/dpd", "use_browser": True},
        {"id": "site-25-vancouver", "name": "City of Vancouver Bylaws", "base_url": "https://vancouver.ca/your-government/vancouver-bylaws.aspx", "use_browser": True},
        {"id": "site-26-alberta", "name": "Alberta Gazette", "base_url": "https://open.alberta.ca/publications/alberta-gazette", "use_browser": True},
        {"id": "site-33-london", "name": "Greater London Authority Planning", "base_url": "https://www.london.gov.uk/what-we-do/planning", "use_browser": True},
        {"id": "site-35-manchester", "name": "Manchester City Council Local Plan", "base_url": "https://www.manchester.gov.uk/info/200074/local_plan", "use_browser": True},
        {"id": "site-37-glasgow", "name": "Glasgow City Council Planning", "base_url": "https://www.glasgow.gov.uk/planning", "use_browser": True},
        {"id": "site-43-legislationnsw", "name": "NSW Legislation", "base_url": "https://www.legislation.nsw.gov.au", "use_browser": True},
        {"id": "site-51-legislationsa", "name": "South Australian Legislation", "base_url": "https://www.legislation.sa.gov.au", "use_browser": True},
    ]

    session = SafeHTTPSession()
    adapter = CustomAdapter(session=session)

    succeeded = 0
    failed = 0

    for idx, site in enumerate(category_c_sources, start=1):
        print(f"[{idx:02d}/12] Testing: {site['name']} ({site['base_url']})...")
        t0 = time.time()
        
        try:
            docs = adapter.extract_documents(site)
            dur = round(time.time() - t0, 2)
            
            if docs:
                succeeded += 1
                print(f"   [PASS: WAF BYPASSED] Found {len(docs)} documents in {dur}s")
                print(f"   Sample: {docs[0].title[:55]} -> {docs[0].url[:65]}...\n")
            else:
                # Direct Playwright attempt
                pw = PlaywrightCrawler(user_agent=session.user_agent)
                res = pw.crawl_source(site)
                dur = round(time.time() - t0, 2)
                if res.success and res.documents:
                    succeeded += 1
                    print(f"   [PASS: PLAYWRIGHT DIRECT] Found {len(res.documents)} documents in {dur}s\n")
                else:
                    failed += 1
                    print(f"   [RE-TUNING NEEDED] 0 docs discovered ({dur}s)\n")

        except Exception as e:
            failed += 1
            print(f"   [FAIL] {e}\n")

    print("=" * 75)
    print(f"Category C Re-test Complete: {succeeded}/{len(category_c_sources)} successfully bypassed & parsed!")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    test_category_c_sites()
