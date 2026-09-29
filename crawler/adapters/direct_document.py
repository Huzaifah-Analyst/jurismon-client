"""JurisMon Direct Document Connector.

Some sources are not listing pages to crawl but a single statutory document
addressed directly - a per-Act XML or PDF, for example
https://www.legislation.govt.nz/act/public/1990/109/en/latest.xml

There is nothing to discover on such a source: the URL is the document. This
adapter registers it as one DiscoveredDocument so the extraction, snapshot and
diff pipeline treats it like any other, which is what makes version-to-version
diffing of a known Act possible.
"""

import logging
from typing import Dict, Any, List
from crawler.adapters.base_adapter import BaseAdapter
from crawler.base import DiscoveredDocument
from crawler.url_normalizer import URLNormalizer

logger = logging.getLogger("jurismon.adapter.direct_document")


class DirectDocumentAdapter(BaseAdapter):
    """Adapter for sources that are themselves a single statutory document."""

    def extract_documents(self, source_config: Dict[str, Any]) -> List[DiscoveredDocument]:
        url = source_config.get("base_url", "")
        if not url:
            return []

        selectors = source_config.get("selectors_config", {})
        title = selectors.get("document_title") or source_config.get("name") or "Statutory Document"

        # Confirm the document is actually reachable before registering it, so a
        # dead link surfaces as a failed crawl rather than an empty snapshot.
        res = self.session.fetch_page(url)
        content_type = res.headers.get("content-type", "").split(";")[0].strip()

        logger.info(f"Direct document registered: {url} ({content_type})")

        return [
            DiscoveredDocument(
                title=str(title).strip(),
                url=url,
                document_type=URLNormalizer.classify_document(str(title), url),
                source_id=source_config.get("id"),
                extra_metadata={
                    "source_format": "direct_document",
                    "content_type": content_type,
                },
            )
        ]
