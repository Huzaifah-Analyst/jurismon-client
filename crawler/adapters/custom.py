"""JurisMon Custom & Generic Heuristic Adapter.

Sub-Task 1.3:
Handles arbitrary municipal and county websites using configurable CSS selectors,
regex link heuristics (bylaws, notices, ordinances, PDFs), and optional Playwright fallback.
"""

import re
from typing import Dict, Any, List
from bs4 import BeautifulSoup
from crawler.adapters.base_adapter import BaseAdapter
from crawler.base import DiscoveredDocument
from crawler.url_normalizer import URLNormalizer


class CustomAdapter(BaseAdapter):
    """Configurable multi-heuristic adapter for unique municipal layouts."""

    DEFAULT_HEURISTIC_REGEX = re.compile(
        r"(\.pdf|\.ashx|\.aspx|notice|minute|agenda|ordinance|bylaw|by-law|zoning|statut|regulation|gazette|rule|plan|code|legislation|act|permit|report|document|view|hearing|bylaws|ordinances)",
        re.IGNORECASE
    )

    def extract_documents(self, source_config: Dict[str, Any]) -> List[DiscoveredDocument]:
        base_url = source_config.get("base_url", "")
        source_id = str(source_config.get("id", ""))
        selectors = source_config.get("selectors_config", {})
        use_browser = source_config.get("use_browser", False)

        # 1. Try static HTTP requests first (fast & lightweight)
        try:
            response = self.session.fetch_page(base_url)
            soup = BeautifulSoup(response.content, "lxml")

            discovered: List[DiscoveredDocument] = []
            seen_urls = set()

            custom_selector = selectors.get("link_selector")
            if custom_selector:
                candidate_links = soup.select(custom_selector)
            else:
                candidate_links = soup.find_all("a", href=True)

            for a in candidate_links:
                raw_href = a.get("href")
                if not raw_href or raw_href.startswith("javascript:") or raw_href.startswith("mailto:") or raw_href == "#":
                    continue

                link_text = a.get_text(strip=True) or a.get("title") or ""
                
                if not custom_selector:
                    combined_signal = f"{raw_href} {link_text}"
                    if not self.DEFAULT_HEURISTIC_REGEX.search(combined_signal):
                        continue

                normalized_url = URLNormalizer.normalize_url(base_url, raw_href)
                if not normalized_url or normalized_url in seen_urls:
                    continue

                if not URLNormalizer.is_valid_statutory_url(normalized_url):
                    continue

                seen_urls.add(normalized_url)
                doc_title = link_text or "Municipal Document"
                doc_type = URLNormalizer.classify_document(doc_title, normalized_url)

                discovered.append(
                    DiscoveredDocument(
                        title=doc_title,
                        url=normalized_url,
                        document_type=doc_type,
                        source_id=source_id,
                        extra_metadata={"platform": "custom_heuristic"}
                    )
                )

            # If static extraction discovered documents, return them
            if len(discovered) > 0:
                return discovered

        except Exception as static_err:
            # 2. Automated Fallback: On 403 / 401 / WAF or static failure, switch to Playwright
            import logging
            logger = logging.getLogger("jurismon.custom_adapter")
            logger.info(f"Static crawl encountered: {static_err}. Falling back to Stealth Playwright Browser for {base_url}")

        # 3. Dynamic Playwright Headless Browser Fallback
        try:
            from crawler.playwright_crawler import PlaywrightCrawler
            playwright_crawler = PlaywrightCrawler(user_agent=self.session.user_agent)
            pw_result = playwright_crawler.crawl_source(source_config)
            if pw_result.success:
                return pw_result.documents
        except Exception as pw_err:
            import logging
            logging.getLogger("jurismon.custom_adapter").error(f"Playwright fallback also failed: {pw_err}")

        return []
