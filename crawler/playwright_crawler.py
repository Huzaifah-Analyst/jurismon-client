"""JurisMon Playwright Headless Browser Crawler.

Handles dynamic JavaScript SPAs, Cloudflare WAF bot challenges, and 403-protected
municipal portals using headless Chromium with stealth evasion properties.
"""

import re
import time
import logging
from typing import Dict, Any, List
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from crawler.base import BaseCrawler, CrawlResult, DiscoveredDocument
from crawler.url_normalizer import URLNormalizer

logger = logging.getLogger("jurismon.playwright_crawler")

STEALTH_JS_INJECTION = """
// Overwrite the 'webdriver' property to prevent bot detection
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined
});

// Mock plugins and languages
Object.defineProperty(navigator, 'languages', {
    get: () => ['en-US', 'en']
});
Object.defineProperty(navigator, 'plugins', {
    get: () => [1, 2, 3, 4, 5]
});
"""


class PlaywrightCrawler(BaseCrawler):
    """Playwright-based browser crawler with stealth properties for WAF/403 bypass."""

    def __init__(self, user_agent: str = None, request_delay: float = 1.5, headless: bool = True):
        super().__init__(user_agent=user_agent, request_delay=request_delay)
        self.headless = headless

    def crawl_source(self, source_config: Dict[str, Any]) -> CrawlResult:
        """Launches headless Chromium, evades bot detection, waits for DOM rendering, and extracts docs."""
        from playwright.sync_api import sync_playwright

        source_id = str(source_config.get("id", "unknown"))
        source_name = source_config.get("name", "Unnamed Source")
        base_url = source_config.get("base_url")
        selectors = source_config.get("selectors_config", {})
        wait_selector = selectors.get("wait_selector")
        custom_link_selector = selectors.get("link_selector")

        start_time = time.time()
        discovered_docs: List[DiscoveredDocument] = []
        seen_urls = set()

        try:
            logger.info(f"[Playwright] Launching browser for '{source_name}' ({base_url})")
            self.polite_sleep()

            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=self.headless,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-infobars",
                    ],
                )

                context = browser.new_context(
                    user_agent=self.user_agent,
                    viewport={"width": 1280, "height": 800},
                    locale="en-US",
                    timezone_id="America/New_York",
                )

                # Inject anti-detection stealth script before every page load
                context.add_init_script(STEALTH_JS_INJECTION)

                page = context.new_page()
                page.set_default_timeout(35000)

                # Navigate to target municipal portal with graceful error catch
                try:
                    page.goto(base_url, wait_until="domcontentloaded", timeout=35000)
                except Exception as nav_err:
                    logger.warning(f"[Playwright] Initial navigation warning for {base_url}: {nav_err}. Continuing with DOM parsing.")
                
                # Small grace period for dynamic client-side JS hydration
                try:
                    page.wait_for_timeout(2500)
                except Exception:
                    pass

                if wait_selector:
                    try:
                        page.wait_for_selector(wait_selector, timeout=8000)
                    except Exception:
                        pass

                page_content = page.content()
                browser.close()

            # Parse rendered HTML with BeautifulSoup
            soup = BeautifulSoup(page_content, "lxml")

            if custom_link_selector:
                candidate_links = soup.select(custom_link_selector)
            else:
                candidate_links = soup.find_all("a", href=True)

            heuristic_pattern = re.compile(
                r"(\.pdf|\.ashx|\.aspx|notice|minute|agenda|ordinance|bylaw|by-law|zoning|statut|regulation|gazette|rule|plan|code|legislation|act|permit|report|document|view|hearing|bylaws|ordinances)",
                re.IGNORECASE
            )

            for a in candidate_links:
                raw_href = a.get("href")
                if not raw_href or raw_href.startswith("javascript:") or raw_href.startswith("mailto:") or raw_href == "#":
                    continue

                link_text = a.get_text(strip=True) or a.get("title") or ""
                
                # Check heuristic if no custom selector is specified
                if not custom_link_selector:
                    combined_signal = f"{raw_href} {link_text}"
                    if not heuristic_pattern.search(combined_signal):
                        continue

                normalized_url = URLNormalizer.normalize_url(base_url, raw_href)
                if not normalized_url or normalized_url in seen_urls:
                    continue

                # Filter non-statutory / vendor / social media domains
                if not URLNormalizer.is_valid_statutory_url(normalized_url):
                    continue

                seen_urls.add(normalized_url)
                doc_title = link_text or "Municipal Document"
                doc_type = URLNormalizer.classify_document(doc_title, normalized_url)

                discovered_docs.append(
                    DiscoveredDocument(
                        title=doc_title,
                        url=normalized_url,
                        document_type=doc_type,
                        source_id=source_id,
                        extra_metadata={"platform": "playwright_browser_rendered"}
                    )
                )

            duration = round(time.time() - start_time, 2)
            logger.info(f"[Playwright] Succeeded for '{source_name}': {len(discovered_docs)} docs found in {duration}s")
            
            return CrawlResult(
                source_id=source_id,
                source_name=source_name,
                success=True,
                documents=discovered_docs,
                duration_seconds=duration,
            )

        except Exception as e:
            duration = round(time.time() - start_time, 2)
            error_msg = f"[Playwright] Failed for '{source_name}': {str(e)}"
            logger.error(error_msg, exc_info=True)
            return CrawlResult(
                source_id=source_id,
                source_name=source_name,
                success=False,
                documents=[],
                error_message=str(e),
                duration_seconds=duration,
            )
