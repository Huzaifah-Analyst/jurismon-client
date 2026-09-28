"""JurisMon Real-World Pipeline Test: Component 1 + Component 2 Combined.

Tests:
1. Component 1: Discovers real document and PDF links from live target portals.
2. Safe Download: Streams real document bytes safely within memory limits.
3. Component 2: Extracts layout-aware text from live PDFs/HTML and applies multi-page boilerplate cleanup.
"""

import sys
import time
import json
from urllib.parse import urlparse

# Add project root
sys.path.insert(0, ".")

from crawler.session import SafeHTTPSession
from crawler.adapters import get_adapter
from crawler.url_normalizer import URLNormalizer
from crawler.base import DiscoveredDocument
from extractor.pdf_extractor import PDFExtractor
from extractor.html_extractor import HTMLExtractor
from extractor.cleaner import TextCleaner


def test_combined_real_data():
    print("\n===================================================================")
    print("   JURISMON REAL-WORLD INTEGRATION TEST: COMPONENT 1 + COMPONENT 2  ")
    print("===================================================================\n")

    session = SafeHTTPSession(default_delay=1.0)

    # 1. Target Live Sources for Combined Test
    test_sources = [
        {
            "id": "site-32-uklegislation",
            "name": "UK Legislation Statutory Instruments",
            "base_url": "https://www.legislation.gov.uk",
            "adapter_type": "custom",
            "selectors_config": {
                "link_selector": "a[href*='/uksi/']"
            },
            "is_active": True,
        },
        {
            "id": "gov-regulatory-pdf-test",
            "name": "UK Statutory PDF Instrument",
            "base_url": "https://www.legislation.gov.uk/uksi/2024/1/made/data.pdf",
            "adapter_type": "custom",
            "is_active": True,
        }
    ]

    total_tested = 0
    total_cleaned_docs = 0

    for source_cfg in test_sources:
        print(f"--> [Step 1: Component 1] Processing source: '{source_cfg['name']}'...")
        
        # If it's a direct PDF link
        if source_cfg["base_url"].endswith(".pdf"):
            discovered_docs = [DiscoveredDocument(title="Sample Regulatory Notice PDF", url=source_cfg["base_url"], document_type="notice")]
        else:
            adapter = get_adapter(source_cfg.get("adapter_type", "custom"), session=session)
            crawl_res = adapter.crawl(source_cfg)
            if not crawl_res.success or not crawl_res.documents:
                print(f"[FAIL] Could not discover docs for {source_cfg['name']}: {crawl_res.error_message}")
                continue
            print(f"[PASS] Discovered {len(crawl_res.documents)} documents in {crawl_res.duration_seconds}s")
            discovered_docs = crawl_res.documents[:2]

        for doc in discovered_docs:
            total_tested += 1
            print(f"\n   [Step 2: Component 1 -> Download] Fetching: {doc.title[:45]}...")
            print(f"   URL: {doc.url[:70]}...")

            start_t = time.time()
            try:
                if URLNormalizer.is_pdf(doc.url):
                    raw_bytes = session.download_stream(doc.url)
                    print(f"   [Step 3: Component 2 -> PDF Extraction] Processing {len(raw_bytes)} bytes...")
                    cleaned_text, raw_text, ocr_applied, pages = PDFExtractor.extract_from_bytes(raw_bytes)
                    doc_type = "PDF"
                else:
                    resp = session.fetch_page(doc.url)
                    raw_bytes = resp.content
                    print(f"   [Step 3: Component 2 -> HTML Extraction] Processing {len(raw_bytes)} bytes...")
                    cleaned_text, raw_text = HTMLExtractor.extract_from_html(resp.text)
                    ocr_applied = False
                    pages = 1
                    doc_type = "HTML"

                duration = round(time.time() - start_t, 2)
                raw_len = len(raw_text)
                clean_len = len(cleaned_text)
                reduction = round(((raw_len - clean_len) / raw_len * 100), 1) if raw_len > 0 else 0

                print(f"   [PASS] Successfully extracted {doc_type} in {duration}s!")
                print(f"      - Pages: {pages} | OCR Applied: {ocr_applied}")
                print(f"      - Raw Characters: {raw_len} | Cleaned Characters: {clean_len}")
                print(f"      - Noise Reduction: {reduction}% stripped")
                
                snippet = cleaned_text[:180].replace("\n", " ")
                # Safe ASCII printing for Windows console
                safe_snippet = snippet.encode("ascii", "ignore").decode("ascii")
                print(f"      - Clean Snippet: \"{safe_snippet}...\"\n")
                total_cleaned_docs += 1

            except Exception as e:
                print(f"   [FAIL] Extraction error for {doc.url}: {e}\n")

    print(f"===================================================================")
    print(f"Pipeline Test Completed: {total_cleaned_docs}/{total_tested} real documents successfully extracted & cleaned.")
    print(f"===================================================================\n")


if __name__ == "__main__":
    test_combined_real_data()
