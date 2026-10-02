"""JurisMon HTTP Session & Safe Streaming Downloader.

Sub-Task 1.1:
- Connection pooling with custom User-Agent and headers
- Polite rate-limiting per host
- Exponential backoff retries with jitter
- Memory-safe streaming downloader for large PDFs (max size cap)
"""

import os
import time
import random
import logging
from typing import Optional, Dict, Any
from urllib.parse import urlparse
import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

logger = logging.getLogger("jurismon.session")

DEFAULT_USER_AGENT = "JurisMonBot/1.0 (+https://jurismon.com/bot; contact@jurismon.com)"

# Max file download size cap (50 MB) to prevent Out-Of-Memory (OOM) on 2vCPU / 4GB VPS
MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024


class SafeHTTPSession:
    """Production-grade HTTP session with memory safety, rate limiting, and retries."""

    def __init__(
        self,
        user_agent: Optional[str] = None,
        default_delay: Optional[float] = None,
        timeout: int = 25,
        max_file_size: int = MAX_DOWNLOAD_BYTES,
    ):
        self.user_agent = (
            user_agent
            if user_agent is not None
            else os.getenv("CRAWLER_USER_AGENT", DEFAULT_USER_AGENT)
        )
        self.default_delay = (
            float(default_delay)
            if default_delay is not None
            else float(os.getenv("CRAWLER_DELAY_SECONDS", 1.5))
        )
        self.timeout = timeout
        self.max_file_size = max_file_size
        self._last_request_times: Dict[str, float] = {}

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Sec-Ch-Ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "DNT": "1",
            "Connection": "keep-alive",
        })

    def _polite_delay(self, url: str):
        """Enforces a polite request delay per domain to respect target municipal servers."""
        domain = urlparse(url).netloc
        now = time.time()
        last_time = self._last_request_times.get(domain, 0)
        elapsed = now - last_time

        # Add small random jitter (±0.3s) to mimic human browsing and prevent lockstep requests
        target_delay = self.default_delay + random.uniform(-0.3, 0.3)
        target_delay = max(0.5, target_delay)

        if elapsed < target_delay:
            sleep_needed = target_delay - elapsed
            time.sleep(sleep_needed)

        self._last_request_times[domain] = time.time()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1.5, min=2, max=10),
        retry=retry_if_exception_type((requests.RequestException, TimeoutError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def fetch_page(
        self,
        url: str,
        extra_headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> requests.Response:
        """Fetches a page with retries and status validation."""
        self._polite_delay(url)
        headers = extra_headers or {}

        response = self.session.get(
            url,
            headers=headers,
            params=params or None,
            timeout=self.timeout,
            allow_redirects=True,
        )
        response.raise_for_status()
        return response

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1.5, min=2, max=10),
        retry=retry_if_exception_type((requests.RequestException, TimeoutError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def download_stream(self, url: str) -> bytes:
        """
        Streams binary file (e.g. PDF) in chunks with a hard memory limit to protect VPS.
        """
        self._polite_delay(url)
        
        response = self.session.get(
            url,
            timeout=self.timeout,
            stream=True,
            allow_redirects=True,
        )
        response.raise_for_status()

        # Check Content-Length header if provided by server
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > self.max_file_size:
            raise ValueError(
                f"File size ({int(content_length)} bytes) exceeds maximum safety limit ({self.max_file_size} bytes)"
            )

        chunks = []
        downloaded_bytes = 0

        for chunk in response.iter_content(chunk_size=64 * 1024):
            if chunk:
                downloaded_bytes += len(chunk)
                if downloaded_bytes > self.max_file_size:
                    raise ValueError(
                        f"Stream exceeded safety threshold of {self.max_file_size} bytes. Aborting download."
                    )
                chunks.append(chunk)

        return b"".join(chunks)

    def close(self):
        """Closes the underlying HTTP session."""
        self.session.close()
