"""JurisMon Municode & eCode360 Platform Adapter.

Sub-Task 1.3:
Handles Municode, General Code eCode360, and statutory code portals.
Extracts code chapters, recent ordinances, and attached regulatory amendments.
"""

from typing import Dict, Any, List
from bs4 import BeautifulSoup
from crawler.adapters.base_adapter import BaseAdapter
from crawler.base import DiscoveredDocument
from crawler.url_normalizer import URLNormalizer


class MunicodeAdapter(BaseAdapter):
    """Specialized adapter for Municode and eCode360 code portals."""

    def extract_documents(self, source_config: Dict[str, Any]) -> List[DiscoveredDocument]:
        base_url = source_config.get("base_url", "")
        source_id = str(source_config.get("id", ""))
        selectors = source_config.get("selectors_config", {})

        response = self.session.fetch_page(base_url)
        soup = BeautifulSoup(response.content, "lxml")

        discovered: List[DiscoveredDocument] = []
        seen_urls = set()

        selector_str = selectors.get(
            "link_selector",
            "a[href*='/codes/'], a[href*='ordinance'], a[href*='.pdf'], a[href*='nodeId'], .toc-item a, .municode-doc-link"
        )

        for a in soup.select(selector_str):
            raw_href = a.get("href")
            if not raw_href or raw_href.startswith("javascript:") or raw_href == "#":
                continue

            normalized_url = URLNormalizer.normalize_url(base_url, raw_href)
            if normalized_url in seen_urls:
                continue

            seen_urls.add(normalized_url)
            title = a.get_text(strip=True) or a.get("title") or "Municode Statutory Item"
            doc_type = URLNormalizer.classify_document(title, normalized_url)

            discovered.append(
                DiscoveredDocument(
                    title=title,
                    url=normalized_url,
                    document_type=doc_type,
                    source_id=source_id,
                    extra_metadata={"platform": "municode_ecode360"}
                )
            )

        return discovered
