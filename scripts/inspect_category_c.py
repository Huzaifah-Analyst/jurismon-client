"""JurisMon Deep Inspector for Remaining Protected Category C Sites.

Fetches rendered HTML via Playwright to see exact DOM structure, titles,
and anti-bot challenge state for the remaining Category C sites.
"""

import sys
import time
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

sys.path.insert(0, ".")
from crawler.session import DEFAULT_USER_AGENT
from crawler.playwright_crawler import STEALTH_JS_INJECTION

test_sites = [
    ("NYC Rules", "https://rules.cityofnewyork.us"),
    ("Harris County", "https://www.eng.hctx.net"),
    ("Bexar County", "https://www.bexar.org"),
    ("Santa Clara County", "https://www.sccgov.org/sites/dpd"),
    ("Alberta Gazette", "https://open.alberta.ca/publications/alberta-gazette"),
    ("GLA London", "https://www.london.gov.uk/what-we-do/planning"),
    ("Glasgow City", "https://www.glasgow.gov.uk/planning"),
]

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
        ],
    )
    context = browser.new_context(
        user_agent=DEFAULT_USER_AGENT,
        viewport={"width": 1280, "height": 800},
    )
    context.add_init_script(STEALTH_JS_INJECTION)

    for name, url in test_sites:
        print(f"\n--- Inspecting: {name} ({url}) ---")
        try:
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=25000)
            page.wait_for_timeout(3000)
            
            title = page.title()
            content = page.content()
            soup = BeautifulSoup(content, "lxml")
            
            all_links = soup.find_all("a", href=True)
            print(f"Page Title: {title}")
            print(f"Total <a> tags rendered: {len(all_links)}")
            
            # Show first 5 links
            sample_links = [a.get("href") for a in all_links[:5]]
            print(f"Sample Hrefs: {sample_links}")
            
            page.close()
        except Exception as e:
            print(f"Error inspecting {name}: {e}")

    browser.close()
