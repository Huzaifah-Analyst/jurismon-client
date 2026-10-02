"""JurisMon REST API & JSON Endpoint Connector.

Sub-Task 1.6:
Provides a structured REST API connector for municipal open data portals,
state legislative APIs (e.g. Socrata, ArcGIS REST, CKAN, federal JSON feeds),
mapping their payloads into our unified internal DiscoveredDocument schema.
"""

import logging
from typing import Dict, Any, List
from crawler.adapters.base_adapter import BaseAdapter
from crawler.base import DiscoveredDocument
from crawler.url_normalizer import URLNormalizer

logger = logging.getLogger("jurismon.adapter.rest_api")


class RestApiAdapter(BaseAdapter):
    """Adapter for REST APIs and structured JSON municipal endpoints."""

    def extract_documents(self, source_config: Dict[str, Any]) -> List[DiscoveredDocument]:
        endpoint_url = source_config.get("base_url", "")
        selectors = source_config.get("selectors_config", {})
        headers = selectors.get("headers", {"Accept": "application/json"})
        params = selectors.get("params", {})

        logger.info(f"Connecting to REST API endpoint: {endpoint_url}")
        res = self.session.fetch_page(endpoint_url, extra_headers=headers, params=params)
        
        try:
            data = res.json()
        except Exception as e:
            logger.error(f"Failed to parse JSON response from {endpoint_url}: {e}")
            raise ValueError(f"Expected JSON from {endpoint_url} but could not parse it: {e}")

        documents: List[DiscoveredDocument] = []
        
        # Handle list of items or nested data key
        items_key = selectors.get("items_key")
        items = data.get(items_key, []) if (isinstance(data, dict) and items_key) else (data if isinstance(data, list) else [data])

        title_field = selectors.get("title_field", "title")
        url_field = selectors.get("url_field", "url")
        # Many registers return only a record id, with the document living at a
        # predictable address, e.g. "https://www.legislation.gov.au/{id}".
        url_template = selectors.get("url_template")
        content_field = selectors.get("content_field", "body")
        date_field = selectors.get("date_field", "updated_at")

        for item in items:
            if not isinstance(item, dict):
                continue

            title = str(item.get(title_field) or item.get("name") or item.get("filename") or "Municipal Record")

            doc_url = ""
            if url_template:
                try:
                    doc_url = url_template.format(**item)
                except (KeyError, IndexError):
                    logger.debug(f"url_template did not resolve for a record from {endpoint_url}")
            if not doc_url:
                doc_url = str(
                    item.get(url_field) or item.get("download_url") or item.get("link") or endpoint_url
                )
            norm_url = URLNormalizer.normalize_url(endpoint_url, doc_url)
            doc_type = URLNormalizer.classify_document(title, norm_url)

            # Raw text payload or metadata
            raw_content = str(item.get(content_field) or item.get("description") or item.get("summary") or "")

            documents.append(
                DiscoveredDocument(
                    title=title.strip(),
                    url=norm_url,
                    document_type=doc_type,
                    extra_metadata={
                        "raw_json_snippet": raw_content[:500],
                        "source_format": "rest_api_json",
                        "date": str(item.get(date_field, "")),
                    }
                )
            )

        logger.info(f"REST API connector extracted {len(documents)} structured items from {endpoint_url}")
        return documents
