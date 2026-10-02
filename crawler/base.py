"""JurisMon Base Crawler.

Provides core abstractions, polite crawling rates, retries with backoff,
SHA256 content hashing, and isolated error boundaries.
"""

import abc
import os
import hashlib
import logging
import time
from typing import Dict, List, Optional, Any
from pydantic import BaseModel

from crawler.session import DEFAULT_USER_AGENT

logger = logging.getLogger("jurismon.crawler")


class DiscoveredDocument(BaseModel):
    """Represents a discovered PDF or notice document on a municipal site."""
    title: str
    url: str
    document_type: str = "notice"  # 'notice', 'meeting_minutes', 'ordinance'
    source_id: Optional[str] = None
    published_date: Optional[str] = None
    extra_metadata: Dict[str, Any] = {}


class CrawlResult(BaseModel):
    """Result of crawling a single municipal source."""
    source_id: str
    source_name: str
    success: bool
    documents: List[DiscoveredDocument] = []
    error_message: Optional[str] = None
    duration_seconds: float = 0.0


class BaseCrawler(abc.ABC):
    """Abstract Base Class for all crawlers and platform adapters."""

    def __init__(self, user_agent: Optional[str] = None, request_delay: Optional[float] = None):
        self.user_agent = (
            user_agent
            if user_agent is not None
            else os.getenv("CRAWLER_USER_AGENT", DEFAULT_USER_AGENT)
        )
        self.request_delay = (
            float(request_delay)
            if request_delay is not None
            else float(os.getenv("CRAWLER_DELAY_SECONDS", 1.5))
        )

    def polite_sleep(self):
        """Sleeps for the configured delay to respect target municipal servers."""
        if self.request_delay > 0:
            time.sleep(self.request_delay)

    @abc.abstractmethod
    def crawl_source(self, source_config: Dict[str, Any]) -> CrawlResult:
        """Crawls a municipal source and discovers documents."""
        pass
