"""JurisMon Requests & BeautifulSoup Crawler.

Handles fast, lightweight crawling for static municipal websites, downloading
PDF notices and extracting document links.
"""

import time
import logging
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from crawler.base import BaseCrawler, CrawlResult, DiscoveredDocument

logger = logging.getLogger("jurismon.requests_crawler")


class RequestsCrawler(BaseCrawler):
    """Crawler based on requests and BeautifulSoup for static HTML portals."""

    def __init__(self, user_agent: Optional[str] = None, request_delay: Optional[float] = None, timeout: int = 20):
        super().__init__(user_agent=user_agent, request_delay=request_delay)
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.RequestException,)),
        reraise=True,
    )
    def fetch_url(self, url: str) -> requests.Response:
        """Fetches a URL with exponential backoff retries."""
        self.polite_sleep()
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response

    def fetch_pdf_bytes(self, pdf_url: str) -> bytes:
        """Downloads raw PDF bytes with safety checks."""
        response = self.fetch_url(pdf_url)
        return response.content

    def crawl_source(self, source_config: Dict[str, Any]) -> CrawlResult:
        """Crawls a static municipal page based on its selector configuration."""
        source_id = str(source_config.get("id", source_config.get("name", "unknown")))
        source_name = source_config.get("name", "Unnamed Source")
        base_url = source_config.get("base_url")
        selectors = source_config.get("selectors_config", {})

        start_time = time.time()
        discovered_docs: List[DiscoveredDocument] = []

        try:
            logger.info(f"Crawling source '{source_name}' at {base_url}")
            response = self.fetch_url(base_url)
            soup = BeautifulSoup(response.content, "lxml")

            link_selector = selectors.get("link_selector", "a[href*='.pdf'], a[href*='notice'], a[href*='minutes']")
            matching_links = soup.select(link_selector)

            for link in matching_links:
                href = link.get("href")
                if not href:
                    continue

                full_url = urljoin(base_url, href)
                title = link.get_text(strip=True) or link.get("title") or "Notice Document"

                # Infer document type
                doc_type = "notice"
                if "minute" in title.lower() or "minute" in full_url.lower():
                    doc_type = "meeting_minutes"
                elif "ordinance" in title.lower() or "ordinance" in full_url.lower():
                    doc_type = "ordinance"

                discovered_docs.append(
                    DiscoveredDocument(
                        title=title,
                        url=full_url,
                        document_type=doc_type,
                        source_id=source_id,
                    )
                )

            duration = round(time.time() - start_time, 2)
            logger.info(f"Successfully crawled '{source_name}': found {len(discovered_docs)} docs in {duration}s")
            return CrawlResult(
                source_id=source_id,
                source_name=source_name,
                success=True,
                documents=discovered_docs,
                duration_seconds=duration,
            )

        except Exception as e:
            duration = round(time.time() - start_time, 2)
            error_msg = f"Failed crawling source '{source_name}' ({base_url}): {str(e)}"
            logger.error(error_msg, exc_info=True)
            return CrawlResult(
                source_id=source_id,
                source_name=source_name,
                success=False,
                documents=[],
                error_message=str(e),
                duration_seconds=duration,
            )
