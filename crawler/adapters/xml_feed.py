"""JurisMon XML & Atom Feed Connector.

Several statutory sources publish machine-readable XML rather than JSON:
Atom feeds of newly made instruments (UK legislation.gov.uk), XML indexes of
consolidated Acts (Canada Justice Laws, Germany gii-toc), and per-Act XML
documents (New Zealand legislation).

The REST connector cannot read these - it calls .json() and silently yields
nothing - so this adapter parses XML into the same DiscoveredDocument schema.
"""

import logging
import xml.parsers.expat
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
from crawler.adapters.base_adapter import BaseAdapter
from crawler.base import DiscoveredDocument
from crawler.url_normalizer import URLNormalizer

logger = logging.getLogger("jurismon.adapter.xml_feed")

# Element names that commonly wrap one record, in priority order.
DEFAULT_ITEM_TAGS = ("entry", "item", "Act", "Regulation", "document", "record")

XML_ACCEPT_HEADER = {
    "Accept": "application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.8"
}


class XmlFeedAdapter(BaseAdapter):
    """Adapter for Atom/RSS feeds and structured XML legislation indexes."""

    def extract_documents(self, source_config: Dict[str, Any]) -> List[DiscoveredDocument]:
        endpoint_url = source_config.get("base_url", "")
        selectors = source_config.get("selectors_config", {})
        source_id = source_config.get("id")

        headers = selectors.get("headers", XML_ACCEPT_HEADER)
        logger.info(f"Fetching XML source: {endpoint_url}")
        res = self.session.fetch_page(endpoint_url, extra_headers=headers)

        # Validate that the response is well-formed XML rather than an HTML
        # error page or broken markup.
        try:
            parser = xml.parsers.expat.ParserCreate()
            parser.UseForeignDTD(True)
            parser.Parse(res.content, True)
            # The "xml" tree builder drops namespace prefixes, so <atom:entry> and
            # <entry> can both be found by plain tag name.
            soup = BeautifulSoup(res.content, "xml")
        except Exception as e:
            raise ValueError(f"Expected XML from {endpoint_url} but could not parse it: {e}")

        root = soup.find()
        if root is None:
            raise ValueError(f"Expected XML from {endpoint_url} but could not parse it: no XML root element found")
        if root.name.lower() == "html":
            raise ValueError(f"Expected XML from {endpoint_url} but got HTML document")

        items = self._find_items(soup, selectors.get("item_tag"))
        if not items:
            logger.warning(f"No XML records matched in {endpoint_url}")
            return []

        title_tag = selectors.get("title_tag", "title")
        link_tag = selectors.get("link_tag", "link")
        date_tag = selectors.get("date_tag")

        documents: List[DiscoveredDocument] = []
        seen: set = set()

        for item in items:
            title = self._text_of(item, title_tag) or "Statutory Record"
            raw_link = self._link_of(item, link_tag)
            if not raw_link:
                continue

            normalized = URLNormalizer.normalize_url(endpoint_url, raw_link)
            if not normalized or normalized in seen:
                continue
            if not URLNormalizer.is_valid_statutory_url(normalized):
                continue
            seen.add(normalized)

            metadata: Dict[str, Any] = {"source_format": "xml_feed"}
            if date_tag:
                published = self._text_of(item, date_tag)
                if published:
                    metadata["date"] = published

            documents.append(
                DiscoveredDocument(
                    title=title.strip(),
                    url=normalized,
                    document_type=URLNormalizer.classify_document(title, normalized),
                    source_id=source_id,
                    extra_metadata=metadata,
                )
            )

        logger.info(f"XML connector extracted {len(documents)} records from {endpoint_url}")
        return documents

    @staticmethod
    def _find_items(soup: BeautifulSoup, item_tag: Optional[str]) -> list:
        """Returns the record elements, using the configured tag when given."""
        if item_tag:
            return soup.find_all(item_tag)

        for candidate in DEFAULT_ITEM_TAGS:
            found = soup.find_all(candidate)
            if found:
                return found
        return []

    @staticmethod
    def _text_of(item, tag_name: str) -> str:
        node = item.find(tag_name)
        return node.get_text(strip=True) if node else ""

    @staticmethod
    def _link_of(item, link_tag: str) -> str:
        """Resolves a record's URL.

        Atom carries it as <link href="..."/>, RSS as <link>text</link>, and
        XML indexes often use an href or url attribute on the record itself.
        """
        node = item.find(link_tag)
        if node is not None:
            href = node.get("href") or node.get("url")
            if href:
                return href
            text = node.get_text(strip=True)
            if text:
                return text

        for attr in ("href", "url", "link"):
            value = item.get(attr)
            if value:
                return value

        return ""
