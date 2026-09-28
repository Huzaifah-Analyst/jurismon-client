"""Tests for the network layer: HTTP crawler, headless browser crawler, DB client.

These modules issue real network and browser calls in production, so every
external boundary here is mocked. The point is to cover the parsing, retry,
filtering and fallback logic that previously had no tests at all.
"""

import unittest
from unittest.mock import patch, MagicMock

import requests

from crawler.requests_crawler import RequestsCrawler
from crawler.playwright_crawler import PlaywrightCrawler


def _response(content: bytes, status: int = 200) -> MagicMock:
    res = MagicMock()
    res.content = content
    res.status_code = status
    res.raise_for_status.return_value = None
    return res


STATIC_PAGE = b"""
<html><body>
  <a href="/docs/zoning-ordinance-2026.pdf">Zoning Ordinance 2026</a>
  <a href="/docs/council-minutes-march.pdf">Council Meeting Minutes - March</a>
  <a href="https://cdn.example.gov/public-notice.pdf">Public Notice</a>
  <a href="/about">About Us</a>
  <a>Anchor with no href</a>
</body></html>
"""


class TestRequestsCrawler(unittest.TestCase):
    """The static-HTML crawler that handles most municipal portals."""

    def setUp(self):
        # request_delay=0 keeps the suite fast; politeness is covered separately.
        self.crawler = RequestsCrawler(request_delay=0)

    def test_crawl_source_discovers_and_resolves_links(self):
        source = {
            "id": "site-test",
            "name": "Test Municipality",
            "base_url": "https://example.gov/planning",
            "selectors_config": {"link_selector": "a[href*='.pdf']"},
        }
        with patch.object(self.crawler.session, "get", return_value=_response(STATIC_PAGE)):
            result = self.crawler.crawl_source(source)

        self.assertTrue(result.success)
        self.assertEqual(result.source_id, "site-test")
        self.assertEqual(len(result.documents), 3)

        urls = [d.url for d in result.documents]
        # Relative hrefs must be resolved against the base URL.
        self.assertIn("https://example.gov/docs/zoning-ordinance-2026.pdf", urls)
        # Absolute hrefs must be left intact.
        self.assertIn("https://cdn.example.gov/public-notice.pdf", urls)
        # The non-PDF link is excluded by the selector.
        self.assertNotIn("https://example.gov/about", urls)

    def test_crawl_source_infers_document_type(self):
        source = {
            "id": "site-test",
            "name": "Test Municipality",
            "base_url": "https://example.gov/planning",
            "selectors_config": {"link_selector": "a[href*='.pdf']"},
        }
        with patch.object(self.crawler.session, "get", return_value=_response(STATIC_PAGE)):
            result = self.crawler.crawl_source(source)

        by_type = {d.document_type for d in result.documents}
        self.assertIn("ordinance", by_type)
        self.assertIn("meeting_minutes", by_type)
        self.assertIn("notice", by_type)

    def test_crawl_source_isolates_failure(self):
        """A dead source must return a failed result, never raise."""
        source = {
            "id": "site-dead",
            "name": "Offline Municipality",
            "base_url": "https://offline.example.gov",
        }
        with patch.object(
            self.crawler.session, "get", side_effect=requests.ConnectionError("host unreachable")
        ), patch("tenacity.nap.time.sleep"):
            result = self.crawler.crawl_source(source)

        self.assertFalse(result.success)
        self.assertEqual(result.documents, [])
        self.assertIn("host unreachable", result.error_message)
        self.assertEqual(result.source_id, "site-dead")

    def test_fetch_url_retries_three_times_then_reraises(self):
        with patch.object(
            self.crawler.session, "get", side_effect=requests.ConnectionError("boom")
        ) as mock_get, patch("tenacity.nap.time.sleep"):
            with self.assertRaises(requests.ConnectionError):
                self.crawler.fetch_url("https://example.gov")

        self.assertEqual(mock_get.call_count, 3)

    def test_fetch_url_succeeds_after_transient_failure(self):
        ok = _response(b"recovered")
        with patch.object(
            self.crawler.session,
            "get",
            side_effect=[requests.ConnectionError("flaky"), ok],
        ) as mock_get, patch("tenacity.nap.time.sleep"):
            response = self.crawler.fetch_url("https://example.gov")

        self.assertEqual(response.content, b"recovered")
        self.assertEqual(mock_get.call_count, 2)

    def test_fetch_pdf_bytes_returns_raw_content(self):
        pdf = b"%PDF-1.7 fake bytes"
        with patch.object(self.crawler.session, "get", return_value=_response(pdf)):
            self.assertEqual(self.crawler.fetch_pdf_bytes("https://example.gov/a.pdf"), pdf)

    def test_http_error_is_captured_as_failed_result(self):
        failing = MagicMock()
        failing.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
        source = {"id": "s", "name": "S", "base_url": "https://example.gov/missing"}

        with patch.object(self.crawler.session, "get", return_value=failing), \
                patch("tenacity.nap.time.sleep"):
            result = self.crawler.crawl_source(source)

        self.assertFalse(result.success)
        self.assertIn("404", result.error_message)

    def test_polite_delay_is_applied_between_requests(self):
        polite = RequestsCrawler(request_delay=2.0)
        with patch("crawler.base.time.sleep") as mock_sleep, \
                patch.object(polite.session, "get", return_value=_response(b"<html></html>")):
            polite.fetch_url("https://example.gov")
        mock_sleep.assert_called_once_with(2.0)

    def test_identifies_itself_with_contact_user_agent(self):
        """Municipal servers block anonymous bots; the UA carries a contact address."""
        ua = self.crawler.session.headers["User-Agent"]
        self.assertIn("JurisMonBot", ua)
        self.assertIn("@", ua)


def _mock_playwright(html: str):
    """Builds a sync_playwright mock whose page renders the given HTML."""
    page = MagicMock()
    page.content.return_value = html

    context = MagicMock()
    context.new_page.return_value = page

    browser = MagicMock()
    browser.new_context.return_value = context

    p = MagicMock()
    p.chromium.launch.return_value = browser

    sync_playwright = MagicMock()
    sync_playwright.return_value.__enter__.return_value = p
    return sync_playwright, p, browser, context, page


RENDERED_PAGE = """
<html><body>
  <a href="/zoning/ordinance-114.pdf">Ordinance 114</a>
  <a href="/meetings/agenda-2026.aspx">Board Agenda 2026</a>
  <a href="https://facebook.com/ourcity/zoning-updates">Zoning Updates</a>
  <a href="https://youtube.com/watch?v=planning-hearing">Planning Hearing Video</a>
  <a href="/careers">Careers</a>
  <a href="javascript:void(0)">Toggle menu</a>
  <a href="mailto:clerk@example.gov">Email the clerk</a>
  <a href="#main">Skip to content</a>
  <a href="/zoning/ordinance-114.pdf">Ordinance 114 (duplicate link)</a>
</body></html>
"""


class TestPlaywrightCrawler(unittest.TestCase):
    """The headless browser path used for JavaScript-rendered portals."""

    def setUp(self):
        self.crawler = PlaywrightCrawler(request_delay=0)
        self.source = {
            "id": "site-dynamic",
            "name": "Dynamic Portal",
            "base_url": "https://example.gov/portal",
            "selectors_config": {},
        }

    def _crawl(self, html, source=None):
        sp, p, browser, context, page = _mock_playwright(html)
        with patch("playwright.sync_api.sync_playwright", sp):
            result = self.crawler.crawl_source(source or self.source)
        return result, p, browser, context, page

    def test_extracts_statutory_links_from_rendered_dom(self):
        result, *_ = self._crawl(RENDERED_PAGE)

        self.assertTrue(result.success)
        urls = [d.url for d in result.documents]
        self.assertIn("https://example.gov/zoning/ordinance-114.pdf", urls)
        self.assertIn("https://example.gov/meetings/agenda-2026.aspx", urls)

    def test_filters_excluded_domains_even_when_text_looks_statutory(self):
        """A social link titled "Zoning Updates" passes the keyword heuristic,
        so only the domain blocklist can reject it."""
        result, *_ = self._crawl(RENDERED_PAGE)
        urls = " ".join(d.url for d in result.documents)

        self.assertNotIn("facebook.com", urls)
        self.assertNotIn("youtube.com", urls)

    def test_filters_links_with_no_statutory_signal(self):
        result, *_ = self._crawl(RENDERED_PAGE)
        urls = " ".join(d.url for d in result.documents)

        self.assertNotIn("/careers", urls)

    def test_skips_javascript_mailto_and_fragment_hrefs(self):
        result, *_ = self._crawl(RENDERED_PAGE)
        urls = " ".join(d.url for d in result.documents)

        self.assertNotIn("javascript:", urls)
        self.assertNotIn("mailto:", urls)

    def test_deduplicates_repeated_urls(self):
        result, *_ = self._crawl(RENDERED_PAGE)
        urls = [d.url for d in result.documents]

        self.assertEqual(len(urls), len(set(urls)))

    def test_classifies_rendered_documents(self):
        result, *_ = self._crawl(RENDERED_PAGE)
        by_url = {d.url: d.document_type for d in result.documents}

        self.assertEqual(
            by_url["https://example.gov/zoning/ordinance-114.pdf"], "ordinance"
        )
        self.assertEqual(
            by_url["https://example.gov/meetings/agenda-2026.aspx"], "meeting_minutes"
        )

    def test_custom_selector_bypasses_heuristic_filter(self):
        """With an explicit selector the operator's choice wins over the heuristic."""
        html = '<html><body><a href="/newsletter">Newsletter</a></body></html>'
        source = dict(self.source, selectors_config={"link_selector": "a"})
        result, *_ = self._crawl(html, source)

        self.assertTrue(result.success)
        self.assertEqual(len(result.documents), 1)
        self.assertEqual(result.documents[0].url, "https://example.gov/newsletter")

    def test_heuristic_rejects_unrelated_links_without_selector(self):
        html = '<html><body><a href="/newsletter">Newsletter</a></body></html>'
        result, *_ = self._crawl(html)

        self.assertTrue(result.success)
        self.assertEqual(result.documents, [])

    def test_stealth_script_is_injected_before_navigation(self):
        _, _, _, context, _ = self._crawl(RENDERED_PAGE)
        context.add_init_script.assert_called_once()
        script = context.add_init_script.call_args[0][0]
        self.assertIn("webdriver", script)

    def test_browser_is_closed_after_crawl(self):
        _, _, browser, _, _ = self._crawl(RENDERED_PAGE)
        browser.close.assert_called_once()

    def test_navigation_error_still_parses_available_dom(self):
        """A slow portal that times out mid-load should not lose what did render."""
        sp, p, browser, context, page = _mock_playwright(RENDERED_PAGE)
        page.goto.side_effect = Exception("Timeout 35000ms exceeded")

        with patch("playwright.sync_api.sync_playwright", sp):
            result = self.crawler.crawl_source(self.source)

        self.assertTrue(result.success)
        self.assertGreater(len(result.documents), 0)

    def test_browser_launch_failure_is_isolated(self):
        sp, p, *_ = _mock_playwright(RENDERED_PAGE)
        p.chromium.launch.side_effect = Exception("Executable doesn't exist")

        with patch("playwright.sync_api.sync_playwright", sp):
            result = self.crawler.crawl_source(self.source)

        self.assertFalse(result.success)
        self.assertEqual(result.documents, [])
        self.assertIn("Executable", result.error_message)

    def test_documents_are_tagged_as_browser_rendered(self):
        result, *_ = self._crawl(RENDERED_PAGE)
        self.assertTrue(result.documents)
        for doc in result.documents:
            self.assertEqual(doc.extra_metadata["platform"], "playwright_browser_rendered")


class TestDatabaseClient(unittest.TestCase):
    """Supabase connector, including the fallback path used by local runs."""

    def setUp(self):
        import db.client as client_module
        self.mod = client_module
        self._saved = (
            client_module.SUPABASE_URL,
            client_module.SUPABASE_KEY,
            client_module.DatabaseClient._supabase_instance,
        )
        client_module.DatabaseClient._supabase_instance = None

    def tearDown(self):
        self.mod.SUPABASE_URL, self.mod.SUPABASE_KEY, _inst = self._saved
        self.mod.DatabaseClient._supabase_instance = self._saved[2]

    def test_returns_none_without_credentials(self):
        self.mod.SUPABASE_URL = None
        self.mod.SUPABASE_KEY = None
        self.assertIsNone(self.mod.DatabaseClient.get_supabase())

    def test_returns_none_for_placeholder_url(self):
        """An unedited .env.example must not be treated as a real project."""
        self.mod.SUPABASE_URL = "https://your-project.supabase.co"
        self.mod.SUPABASE_KEY = "your-supabase-service-role-key"
        self.assertIsNone(self.mod.DatabaseClient.get_supabase())

    def test_creates_client_with_valid_credentials(self):
        self.mod.SUPABASE_URL = "https://real-project.supabase.co"
        self.mod.SUPABASE_KEY = "real-service-role-key"
        fake_client = MagicMock()

        with patch.object(self.mod, "create_client", return_value=fake_client) as mock_create:
            result = self.mod.DatabaseClient.get_supabase()

        self.assertIs(result, fake_client)
        mock_create.assert_called_once_with(
            "https://real-project.supabase.co", "real-service-role-key"
        )

    def test_client_is_cached_between_calls(self):
        self.mod.SUPABASE_URL = "https://real-project.supabase.co"
        self.mod.SUPABASE_KEY = "real-service-role-key"

        with patch.object(self.mod, "create_client", return_value=MagicMock()) as mock_create:
            first = self.mod.DatabaseClient.get_supabase()
            second = self.mod.DatabaseClient.get_supabase()

        self.assertIs(first, second)
        mock_create.assert_called_once()

    def test_connection_error_falls_back_to_none(self):
        """A Supabase outage must degrade to SQLite, not crash the crawler."""
        self.mod.SUPABASE_URL = "https://real-project.supabase.co"
        self.mod.SUPABASE_KEY = "real-service-role-key"

        with patch.object(self.mod, "create_client", side_effect=Exception("DNS failure")):
            self.assertIsNone(self.mod.DatabaseClient.get_supabase())


class TestRepositoryFallback(unittest.TestCase):
    """Repository must work with no Supabase configured at all."""

    def test_repository_uses_sqlite_when_supabase_absent(self):
        import tempfile, shutil, os
        from db.repository import Repository

        tmp = tempfile.mkdtemp(prefix="jurismon_fallback_")
        try:
            with patch("db.repository.DatabaseClient.get_supabase", return_value=None):
                repo = Repository(db_path=os.path.join(tmp, "fallback.db"))
                self.assertFalse(repo.is_using_supabase())
                self.assertTrue(repo.is_connected())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
