import asyncio
import sys
import requests
from playwright.async_api import async_playwright
from urllib.parse import urlparse

sys.path.insert(0, ".")
from crawler.session import DEFAULT_USER_AGENT

TARGET_ISSUES = [
    # 7 Cloudflare suspected
    {"name": "New York City Rules", "url": "https://rules.cityofnewyork.us", "expected": "Cloudflare CAPTCHA"},
    {"name": "Harris County Engineering", "url": "https://www.eng.hctx.net", "expected": "Cloudflare CAPTCHA"},
    {"name": "Bexar County Texas", "url": "https://www.bexar.org", "expected": "Cloudflare CAPTCHA"},
    {"name": "Santa Clara County Planning", "url": "https://www.sccgov.org/sites/dpd", "expected": "Cloudflare CAPTCHA"},
    {"name": "Alberta Gazette", "url": "https://open.alberta.ca/publications/alberta-gazette", "expected": "Cloudflare CAPTCHA"},
    {"name": "Greater London Authority", "url": "https://www.london.gov.uk/what-we-do/planning", "expected": "Cloudflare CAPTCHA"},
    {"name": "Glasgow City Council", "url": "https://www.glasgow.gov.uk/planning", "expected": "Cloudflare CAPTCHA"},
    
    # 12 Dead / 404 suspected
    {"name": "City of Austin Code", "url": "https://www.austintexas.gov/page/code-ordinances", "expected": "404 Not Found"},
    {"name": "Ontario Gazette", "url": "https://www.ontario.ca/page/ontario-gazette", "expected": "404 Not Found"},
    {"name": "Calgary Land Use Bylaw", "url": "https://www.calgary.ca/pda/pd/calgary-land-use-bylaw.html", "expected": "404 Not Found"},
    {"name": "City of Montreal Regulations", "url": "https://montreal.ca/en/regulations", "expected": "404 Not Found"},
    {"name": "San Bernardino County", "url": "https://lu.sbcounty.gov", "expected": "DNS/Connection Error"},
    {"name": "Tarrant County Administrator", "url": "https://www.tarrantcounty.com", "expected": "DNS/Connection Error"},
    {"name": "Dallas County Planning", "url": "https://www.dallascounty.org", "expected": "DNS/Connection Error"},
    {"name": "Publications du Québec", "url": "https://www.publicationsquebec.gouv.qc.ca", "expected": "DNS/Connection Error"},
    {"name": "The Edinburgh Gazette", "url": "https://www.theedinburghgazette.co.uk", "expected": "DNS/Connection Error"},
    {"name": "San Diego County Planning", "url": "https://www.sandiegocounty.gov", "expected": "Timeout/Connection Error"},
    {"name": "Miami-Dade County Regulatory", "url": "https://www.miamidade.gov", "expected": "Timeout/Connection Error"},
    {"name": "City of Melbourne Planning", "url": "https://www.melbourne.vic.gov.au", "expected": "HTTP 202/Blocked"}
]

HEADERS = {
    "User-Agent": DEFAULT_USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

async def check_with_playwright(browser, url):
    page = await browser.new_page(
        user_agent=HEADERS["User-Agent"],
        viewport={"width": 1280, "height": 800}
    )
    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        status = response.status if response else None
        content = await page.content()
        title = await page.title()
        
        # Check for Cloudflare
        is_cf = ("Just a moment" in content or "Cloudflare" in content or "Attention Required" in content or "challenge-platform" in content) and (status in (403, 503, 429) or "challenge" in content.lower())
        is_404 = (status == 404) or ("404" in title) or ("Page Not Found" in title) or ("Page not found" in content[:1000])
        
        await page.close()
        return {
            "pw_status": status,
            "pw_title": title,
            "is_cloudflare": is_cf,
            "is_404": is_404,
            "pw_error": None
        }
    except Exception as e:
        await page.close()
        return {
            "pw_status": None,
            "pw_title": None,
            "is_cloudflare": False,
            "is_404": False,
            "pw_error": str(e)[:120]
        }

async def main():
    print(f"=== RE-VERIFYING ALL {len(TARGET_ISSUES)} SUSPECTED SITES LIVE ===")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        results = []
        for item in TARGET_ISSUES:
            name = item["name"]
            url = item["url"]
            print(f"\nTesting: {name} ({url}) ...")
            
            # 1. Test with Requests
            req_status = None
            req_err = None
            req_cf = False
            req_404 = False
            try:
                r = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
                req_status = r.status_code
                if r.status_code == 404 or "404" in r.text[:1000] or "Page Not Found" in r.text[:1000]:
                    req_404 = True
                if ("Just a moment" in r.text or "Cloudflare" in r.text or "cf-ray" in r.headers) and r.status_code in (403, 503):
                    req_cf = True
            except Exception as e:
                req_err = type(e).__name__ + ": " + str(e)[:80]
                
            # 2. Test with Playwright Chromium
            pw_res = await check_with_playwright(browser, url)
            
            # Determine Final Diagnosis
            final_diagnosis = "UNKNOWN"
            if req_404 or pw_res["is_404"] or req_status == 404 or pw_res["pw_status"] == 404:
                final_diagnosis = "CONFIRMED_404_DEAD_LINK"
            elif pw_res["pw_error"] and ("net::ERR_NAME_NOT_RESOLVED" in pw_res["pw_error"] or "net::ERR_CONNECTION" in pw_res["pw_error"]):
                final_diagnosis = "CONFIRMED_DNS_OR_CONNECTION_DEAD"
            elif pw_res["pw_error"] and "Timeout" in pw_res["pw_error"] and req_err and "Timeout" in req_err:
                final_diagnosis = "CONFIRMED_SERVER_DOWN_TIMEOUT"
            elif req_cf or pw_res["is_cloudflare"] or req_status == 403 or pw_res["pw_status"] == 403:
                final_diagnosis = "CONFIRMED_CLOUDFLARE_CAPTCHA"
            elif req_status == 200 and not pw_res["is_404"] and not pw_res["is_cloudflare"]:
                final_diagnosis = "OPERATIONAL_PASS"
            else:
                final_diagnosis = f"FAILED (Req:{req_status or req_err}, PW:{pw_res['pw_status'] or pw_res['pw_error']})"
                
            print(f" -> Requests: Status={req_status}, Err={req_err}")
            print(f" -> Playwright: Status={pw_res['pw_status']}, Title='{pw_res['pw_title']}', Err={pw_res['pw_error']}")
            print(f" => FINAL VERDICT: {final_diagnosis}")
            
            results.append({
                "name": name,
                "url": url,
                "requests_status": req_status,
                "requests_err": req_err,
                "pw_status": pw_res["pw_status"],
                "pw_title": pw_res["pw_title"],
                "pw_err": pw_res["pw_error"],
                "verdict": final_diagnosis
            })
            
        await browser.close()
        
    print("\n" + "="*80)
    print("=== SUMMARY OF 19 RE-VERIFIED SITES ===")
    print("="*80)
    import json
    os.makedirs("docs/reports/data", exist_ok=True)
    with open("docs/reports/data/live-reverification-19-sites.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("Saved raw live results to docs/reports/data/live-reverification-19-sites.json")

if __name__ == "__main__":
    asyncio.run(main())
