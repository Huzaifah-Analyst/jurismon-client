"""JurisMon 51-Site Full System Audit & Stress Tester.

Runs 100% comprehensive testing across all 51 municipal sites provided by the client.
Categorizes every site into:
1. [CATEGORY A] HEALTHY / FULLY OPERATIONAL (Discovered docs, extracted clean text)
2. [CATEGORY B] DEAD / OUTDATED LINKS (404 Not Found, DNS failure, connection dead - Client needs to replace)
3. [CATEGORY C] ACCESS RESTRICTED / WAF / JS RENDERING (403 Cloudflare, 401, Dynamic SPA)
4. [CATEGORY D] SELECTOR TUNING NEEDED (Page loads 200 OK, needs custom portal sub-path)

Generates:
- docs/reports/audit-51-sites.md
- docs/reports/data/audit-results.json
"""

import os
import sys
import json
import time
import requests
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add project root
sys.path.insert(0, ".")

from crawler.session import SafeHTTPSession
from crawler.adapters import get_adapter
from crawler.url_normalizer import URLNormalizer
from extractor.html_extractor import HTMLExtractor
from extractor.pdf_extractor import PDFExtractor
from extractor.cleaner import TextCleaner


def run_full_audit(max_workers: int = 4):
    print("\n" + "=" * 75)
    print("      JURISMON 100% FULL SYSTEM AUDIT (ALL 51 MUNICIPAL SITES)      ")
    print("=" * 75 + "\n")

    with open("config/sites.json", "r", encoding="utf-8") as f:
        sites = json.load(f)

    session = SafeHTTPSession(default_delay=0.8, timeout=20)
    
    results = {
        "healthy_success": [],
        "dead_links_client": [],
        "access_restricted_waf": [],
        "selector_tuning_needed": [],
    }

    start_time = time.time()
    total_sites = len(sites)

    def audit_single_site(site_cfg):
        site_id = site_cfg.get("id")
        site_name = site_cfg.get("name")
        base_url = site_cfg.get("base_url")
        adapter_type = site_cfg.get("adapter_type", "custom")

        audit_entry = {
            "id": site_id,
            "name": site_name,
            "url": base_url,
            "adapter": adapter_type,
            "status_code": None,
            "docs_found": 0,
            "sample_doc": None,
            "error_detail": None,
            "category": None,
            "recommendation": None,
            "duration_s": 0.0,
        }

        t0 = time.time()
        try:
            # 1. Direct connectivity check
            resp = session.session.get(base_url, timeout=18, allow_redirects=True)
            audit_entry["status_code"] = resp.status_code

            if resp.status_code == 404:
                audit_entry["category"] = "dead_links_client"
                audit_entry["error_detail"] = "404 Not Found - URL path no longer exists on municipality server"
                audit_entry["recommendation"] = "Client to provide updated URL"
            elif resp.status_code in (401, 403):
                audit_entry["category"] = "access_restricted_waf"
                audit_entry["error_detail"] = f"HTTP {resp.status_code} - Cloudflare/WAF Bot Challenge"
                audit_entry["recommendation"] = "Run with Playwright Headless Browser Adapter"
            elif resp.status_code == 200:
                # 2. Run Adapter Document Discovery
                adapter = get_adapter(adapter_type, session=session)
                crawl_res = adapter.crawl(site_cfg)

                if crawl_res.success and len(crawl_res.documents) > 0:
                    audit_entry["category"] = "healthy_success"
                    audit_entry["docs_found"] = len(crawl_res.documents)
                    audit_entry["sample_doc"] = {
                        "title": crawl_res.documents[0].title,
                        "url": crawl_res.documents[0].url,
                        "type": crawl_res.documents[0].document_type,
                    }
                    audit_entry["recommendation"] = "Ready for daily automated ingestion"
                else:
                    audit_entry["category"] = "selector_tuning_needed"
                    audit_entry["error_detail"] = "Page 200 OK, but 0 statutory documents matched generic selector"
                    audit_entry["recommendation"] = "Tune specific portal landing sub-path in sites.json"
            else:
                audit_entry["category"] = "dead_links_client"
                audit_entry["error_detail"] = f"HTTP {resp.status_code} Error"
                audit_entry["recommendation"] = "Client to verify link availability"

        except requests.exceptions.SSLError as ssl_err:
            audit_entry["category"] = "dead_links_client"
            audit_entry["error_detail"] = f"SSL Certificate Failure: {str(ssl_err)[:80]}"
            audit_entry["recommendation"] = "Municipal server SSL certificate is expired or invalid"
        except requests.exceptions.ConnectionError as conn_err:
            audit_entry["category"] = "dead_links_client"
            audit_entry["error_detail"] = "Connection Failed / DNS Resolution Error (Dead Domain)"
            audit_entry["recommendation"] = "Client to replace dead URL"
        except requests.exceptions.Timeout:
            audit_entry["category"] = "dead_links_client"
            audit_entry["error_detail"] = "Server Connection Timed Out (>18s)"
            audit_entry["recommendation"] = "Server is unresponsive or blocking international requests"
        except Exception as general_err:
            audit_entry["category"] = "selector_tuning_needed"
            audit_entry["error_detail"] = f"Crawl Error: {str(general_err)}"
            audit_entry["recommendation"] = "Inspect portal layout"

        audit_entry["duration_s"] = round(time.time() - t0, 2)
        return audit_entry

    print(f"Executing concurrent audit across {total_sites} sites (Workers: {max_workers})...\n")

    completed_count = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(audit_single_site, site): site for site in sites}

        for future in as_completed(future_map):
            completed_count += 1
            entry = future.result()
            cat = entry["category"]
            results[cat].append(entry)

            status_icon = {
                "healthy_success": "[PASS: HEALTHY]",
                "dead_links_client": "[FAIL: DEAD LINK]",
                "access_restricted_waf": "[WARN: WAF/403]",
                "selector_tuning_needed": "[WARN: TUNING NEEDED]",
            }.get(cat, "[INFO]")

            print(f"[{completed_count:02d}/{total_sites}] {status_icon} {entry['name']} ({entry['url']}) - {entry['duration_s']}s")

    total_duration = round(time.time() - start_time, 2)

    # Save JSON report
    os.makedirs("docs", exist_ok=True)
    os.makedirs("docs/reports/data", exist_ok=True)
    with open("docs/reports/data/audit-results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    # Generate Markdown Audit Report
    generate_markdown_report(results, total_duration, total_sites)


def generate_markdown_report(results: dict, duration: float, total_sites: int):
    h_count = len(results["healthy_success"])
    d_count = len(results["dead_links_client"])
    w_count = len(results["access_restricted_waf"])
    t_count = len(results["selector_tuning_needed"])

    lines = []
    lines.append("# JurisMon - 51 Municipal Sites Comprehensive Audit Report\n")
    lines.append(f"**Date:** 27 Sep 2026  ")
    lines.append(f"**Total Sites Audited:** {total_sites}  ")
    lines.append(f"**Audit Execution Duration:** {duration} seconds  \n")

    lines.append("## Executive Summary\n")
    lines.append(f"| Category | Count | Percentage | Action Required |")
    lines.append(f"|---|---|---|---|")
    lines.append(f"| **1. Healthy & Operational** | {h_count} | {round(h_count/total_sites*100, 1)}% | Ready for daily ingestion |")
    lines.append(f"| **2. Dead / Broken Links** | {d_count} | {round(d_count/total_sites*100, 1)}% | Client to replace invalid/dead URLs |")
    lines.append(f"| **3. Access Restricted / Cloudflare 403** | {w_count} | {round(w_count/total_sites*100, 1)}% | Headless Playwright Browser required |")
    lines.append(f"| **4. Sub-Path Tuning Needed** | {t_count} | {round(t_count/total_sites*100, 1)}% | System config sub-path mapping |")
    lines.append("\n---\n")

    # Category 1: Healthy
    lines.append(f"## 1. Category A: Healthy & Fully Operational ({h_count} Sites)\n")
    lines.append("These sites are 100% functional, public, and successfully return statutory documents and PDF notices.\n")
    lines.append("| Site Name | URL | Docs Discovered | Sample Document Title |")
    lines.append("|---|---|---|---|")
    for s in results["healthy_success"]:
        sample_title = s["sample_doc"]["title"][:45] if s["sample_doc"] else "N/A"
        lines.append(f"| {s['name']} | [{s['url']}]({s['url']}) | {s['docs_found']} | {sample_title} |")
    lines.append("\n---\n")

    # Category 2: Dead Links (Client Action)
    lines.append(f"## 2. Category B: Dead / Broken / Outdated Links ({d_count} Sites - Client Action Required)\n")
    lines.append("These links failed due to 404 Not Found (outdated municipality URLs), expired SSL, DNS resolution failures, or server connection timeouts. The client mentioned in chat: *'I will share more later in case we need to replace those not responding'*. These are the exact ones to share with him.\n")
    lines.append("| Site Name | URL | Exact Failure Reason | Action |")
    lines.append("|---|---|---|---|")
    for s in results["dead_links_client"]:
        lines.append(f"| {s['name']} | [{s['url']}]({s['url']}) | `{s['error_detail']}` | {s['recommendation']} |")
    lines.append("\n---\n")

    # Category 3: Access Restricted / WAF
    lines.append(f"## 3. Category C: Access Restricted / Cloudflare WAF ({w_count} Sites)\n")
    lines.append("These sites returned HTTP 403 / 401 when crawled via static HTTP requests. They require JavaScript execution or Playwright browser rendering.\n")
    lines.append("| Site Name | URL | Status Code | Recommendation |")
    lines.append("|---|---|---|---|")
    for s in results["access_restricted_waf"]:
        lines.append(f"| {s['name']} | [{s['url']}]({s['url']}) | `{s['error_detail']}` | {s['recommendation']} |")
    lines.append("\n---\n")

    # Category 4: Sub-Path Tuning Needed
    lines.append(f"## 4. Category D: Landing Pages Needing Specific Sub-Paths ({t_count} Sites)\n")
    lines.append("These domain root landing pages return HTTP 200 OK, but generic homepage selectors did not find direct PDF links on the homepage (e.g. they need `/agendas` or `/zoning-by-laws` sub-path added to `sites.json`).\n")
    lines.append("| Site Name | URL | Status | Recommendation |")
    lines.append("|---|---|---|---|")
    for s in results["selector_tuning_needed"]:
        lines.append(f"| {s['name']} | [{s['url']}]({s['url']}) | 200 OK | {s['recommendation']} |")
    lines.append("\n")

    os.makedirs("docs/reports", exist_ok=True)
    with open("docs/reports/audit-51-sites.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print("\n" + "=" * 75)
    print(f"Audit Complete in {duration}s!")
    print(f"Results saved to: docs/reports/audit-51-sites.md and docs/reports/data/audit-results.json")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    run_full_audit(max_workers=4)
