"""JurisMon Base Adapter Interface.

Defines the contract for all platform-specific adapters.
"""

import abc
import logging
from typing import Dict, Any, List
from crawler.base import CrawlResult, DiscoveredDocument
from crawler.session import SafeHTTPSession
from crawler.url_normalizer import URLNormalizer

logger = logging.getLogger("jurismon.adapter")


class BaseAdapter(abc.ABC):
    """Abstract base class for platform adapters."""

    def __init__(self, session: SafeHTTPSession = None):
        self.session = session or SafeHTTPSession()

    @abc.abstractmethod
    def extract_documents(self, source_config: Dict[str, Any]) -> List[DiscoveredDocument]:
        """Extracts document links and metadata from the target municipal site."""
        pass

    def crawl(self, source_config: Dict[str, Any]) -> CrawlResult:
        """Executes crawl with error boundaries and duration logging."""
        import time
        start_time = time.time()
        source_id = str(source_config.get("id", "unknown"))
        source_name = source_config.get("name", "Unnamed Source")

        try:
            logger.info(f"[{self.__class__.__name__}] Crawling '{source_name}' ({source_config.get('base_url')})")
            docs = self.extract_documents(source_config)
            duration = round(time.time() - start_time, 2)
            
            return CrawlResult(
                source_id=source_id,
                source_name=source_name,
                success=True,
                documents=docs,
                duration_seconds=duration,
            )
        except Exception as e:
            duration = round(time.time() - start_time, 2)
            error_msg = f"Failed crawling '{source_name}': {str(e)}"
            logger.error(error_msg, exc_info=True)
            return CrawlResult(
                source_id=source_id,
                source_name=source_name,
                success=False,
                documents=[],
                error_message=str(e),
                duration_seconds=duration,
            )
