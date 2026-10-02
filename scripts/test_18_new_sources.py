import requests
import json
import sys
from urllib.parse import urlparse

sys.path.insert(0, ".")
from crawler.session import DEFAULT_USER_AGENT

SOURCES_18 = [
    {"id": "new-01-aus-api", "name": "Australia Federal Register API", "url": "https://api.prod.legislation.gov.au/v1/", "type": "api"},
    {"id": "new-02-aus-web", "name": "Australia Federal Register Website", "url": "https://www.legislation.gov.au/", "type": "html"},
    {"id": "new-03-qld-leg", "name": "Queensland Legislation", "url": "https://www.legislation.qld.gov.au/", "type": "html"},
    {"id": "new-04-vic-plan", "name": "Victoria Planning Schemes", "url": "https://planning-schemes.app.planning.vic.gov.au/", "type": "browser"},
    {"id": "new-05-uk-leg", "name": "UK Legislation API", "url": "https://www.legislation.gov.uk/", "type": "api/xml"},
    {"id": "new-06-uk-atom", "name": "UK Legislation Atom Feeds", "url": "https://www.legislation.gov.uk/new/uksi", "type": "feed"},
    {"id": "new-07-uk-planning", "name": "UK Planning Data API", "url": "https://www.planning.data.gov.uk/entity.json", "type": "json_api"},
    {"id": "new-08-uk-datagov", "name": "UK Data.gov.uk API", "url": "https://data.gov.uk/api/action/", "type": "api"},
    {"id": "new-09-ca-xml", "name": "Canada Justice Laws XML", "url": "https://laws-lois.justice.gc.ca/eng/XML/Legis.xml", "type": "xml"},
    {"id": "new-10-ca-web", "name": "Canada Justice Laws Web", "url": "https://laws-lois.justice.gc.ca/eng/", "type": "html"},
    {"id": "new-11-ca-bulk", "name": "Canada Point-in-Time Bulk XML", "url": "https://open.canada.ca/data/en/dataset/4d277b82-c4af-4431-b31d-48fcece6dd8a", "type": "bulk"},
    {"id": "new-12-ontario-search", "name": "Canada Ontario Gazette Search", "url": "https://www.ontario.ca/search/ontario-gazette", "type": "html"},
    {"id": "new-13-nz-api", "name": "New Zealand Legislation API", "url": "https://api.legislation.govt.nz/v0/works/", "type": "api"},
    {"id": "new-14-nz-xml", "name": "New Zealand Legislation XML", "url": "https://www.legislation.govt.nz/act/public/1990/109/en/latest.xml", "type": "xml"},
    {"id": "new-15-nz-pdf", "name": "New Zealand Legislation PDF", "url": "https://www.legislation.govt.nz/act/public/1990/109/en/latest.pdf", "type": "pdf"},
    {"id": "new-16-eu-cellar", "name": "EU Cellar Legal Repository", "url": "https://publications.europa.eu/resource/cellar/", "type": "rest_repo"},
    {"id": "new-17-de-gesetze", "name": "Germany Gesetze im Internet", "url": "https://www.gesetze-im-internet.de/", "type": "html"},
    {"id": "new-18-de-toc", "name": "Germany XML Table of Contents", "url": "https://www.gesetze-im-internet.de/gii-toc.xml", "type": "xml"}
]

HEADERS = {
    "User-Agent": DEFAULT_USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.9,*/*;q=0.8",
}

print("=== TESTING 18 NEW SOURCES LIVE ===")
results = []

for s in SOURCES_18:
    name = s["name"]
    url = s["url"]
    print(f"Testing {name} ({url}) ...")
    try:
        r = requests.get(url, headers=HEADERS, timeout=12, allow_redirects=True)
        status = r.status_code
        content_type = r.headers.get("Content-Type", "")
        content_len = len(r.content)
        
        is_cf = ("Just a moment" in r.text or "Cloudflare" in r.text) and status in (403, 503)
        
        verdict = "PASS"
        if status >= 400:
            verdict = f"FAIL (HTTP {status})"
        if is_cf:
            verdict = "CLOUDFLARE_CAPTCHA"
            
        print(f" -> Status: {status}, Type: {content_type[:30]}, Size: {content_len} bytes => {verdict}")
        results.append({
            "name": name,
            "url": url,
            "status_code": status,
            "content_type": content_type,
            "size": content_len,
            "verdict": verdict
        })
    except Exception as e:
        print(f" -> ERROR: {type(e).__name__}: {str(e)[:80]}")
        results.append({
            "name": name,
            "url": url,
            "status_code": None,
            "content_type": "",
            "size": 0,
            "verdict": f"ERROR ({type(e).__name__})"
        })

print("\n=== SUMMARY ===")
pass_count = sum(1 for r in results if r["verdict"] == "PASS")
fail_count = len(results) - pass_count
print(f"Passed: {pass_count}/{len(results)}, Failed/Need Key: {fail_count}")

with open("docs/audit_18_new_sources.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)
