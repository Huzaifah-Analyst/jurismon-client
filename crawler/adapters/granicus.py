"""JurisMon Granicus Legistar Platform Adapter.

Sub-Task 1.3:
Handles Granicus / Legistar municipal meeting calendars, agendas, and minutes tables.
Parses ASPX tables (table.rgMasterTable) and resolves View.ashx document links.
"""

from typing import Dict, Any, List
from bs4 import BeautifulSoup
from crawler.adapters.base_adapter import BaseAdapter
from crawler.base import DiscoveredDocument
from crawler.url_normalizer import URLNormalizer


class GranicusAdapter(BaseAdapter):
    """Specialized adapter for Granicus Legistar portals."""

    def extract_documents(self, source_config: Dict[str, Any]) -> List[DiscoveredDocument]:
        base_url = source_config.get("base_url", "")
        source_id = str(source_config.get("id", ""))
        
        response = self.session.fetch_page(base_url)
        soup = BeautifulSoup(response.content, "lxml")

        discovered: List[DiscoveredDocument] = []
        seen_urls = set()

        # Legistar typically uses RadGrid tables: table.rgMasterTable or standard calendar tables
        table = soup.select_one("table.rgMasterTable") or soup.select_one("table[id*='grid']") or soup

        # Extract all links matching View.ashx, pdfs, agendas, and minutes
        link_elements = table.select("a[href*='View.ashx'], a[href*='.pdf'], a[id*='hlAgenda'], a[id*='hlMinutes']")

        for a in link_elements:
            raw_href = a.get("href")
            if not raw_href or raw_href.startswith("javascript:"):
                continue

            normalized_url = URLNormalizer.normalize_url(base_url, raw_href)
            if normalized_url in seen_urls:
                continue

            seen_urls.add(normalized_url)

            # Try to grab row context (Meeting name, date)
            row = a.find_parent("tr")
            meeting_title = ""
            meeting_date = ""

            if row:
                cells = [td.get_text(strip=True) for td in row.find_all("td")]
                if len(cells) >= 2:
                    meeting_title = cells[0]
                    meeting_date = cells[1]

            link_text = a.get_text(strip=True) or a.get("title") or "Legistar Document"
            doc_title = f"{meeting_title} - {link_text}" if meeting_title else link_text
            doc_type = URLNormalizer.classify_document(doc_title, normalized_url)

            discovered.append(
                DiscoveredDocument(
                    title=doc_title,
                    url=normalized_url,
                    document_type=doc_type,
                    source_id=source_id,
                    published_date=meeting_date or None,
                    extra_metadata={"platform": "granicus_legistar"}
                )
            )

        return discovered
