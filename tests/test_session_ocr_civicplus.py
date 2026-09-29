"""Tests for the three modules left without meaningful cover.

- SafeHTTPSession: per-host rate limiting, retries, and the download size cap
  that protects a 4GB VPS from a malicious or mis-sized PDF.
- OCRExtractor: the scanned-PDF fallback. Tesseract is not installed in this
  environment, so the binary is mocked; that also means these paths had never
  executed anywhere before now.
- CivicPlusAdapter: AgendaCenter / DocumentCenter link extraction.
"""

import io
import unittest
from unittest.mock import patch, MagicMock

import requests
from PIL import Image

from crawler.session import SafeHTTPSession, MAX_DOWNLOAD_BYTES
from crawler.adapters.civicplus import CivicPlusAdapter
from extractor.ocr import OCRExtractor


def _response(content=b"", headers=None, chunks=None):
    res = MagicMock()
    res.content = content
    res.headers = headers or {}
    res.raise_for_status.return_value = None
    res.iter_content.return_value = chunks if chunks is not None else [content]
    return res


class TestPoliteDelay(unittest.TestCase):
    """Municipal servers block bots that hammer them; the delay is per host."""

    def setUp(self):
        self.session = SafeHTTPSession(default_delay=2.0)

    def test_first_request_to_a_host_is_not_delayed(self):
        with patch("crawler.session.time.sleep") as mock_sleep:
            self.session._polite_delay("https://example.gov/a")
        mock_sleep.assert_not_called()

    def test_second_request_to_same_host_waits(self):
        with patch("crawler.session.time.sleep"):
            self.session._polite_delay("https://example.gov/a")
        with patch("crawler.session.time.sleep") as mock_sleep:
            self.session._polite_delay("https://example.gov/b")
        mock_sleep.assert_called_once()
        self.assertGreater(mock_sleep.call_args[0][0], 0)

    def test_delay_is_tracked_per_host_not_globally(self):
        """A pause owed to one municipality must not stall a different one."""
        with patch("crawler.session.time.sleep"):
            self.session._polite_delay("https://austin.gov/a")
        with patch("crawler.session.time.sleep") as mock_sleep:
            self.session._polite_delay("https://calgary.ca/a")
        mock_sleep.assert_not_called()

    def test_jitter_never_drops_below_the_half_second_floor(self):
        session = SafeHTTPSession(default_delay=0.0)
        session._last_request_times["example.gov"] = 0.0

        observed = []
        with patch("crawler.session.time.sleep", side_effect=observed.append), \
                patch("crawler.session.time.time", return_value=0.0):
            for _ in range(40):
                session._last_request_times["example.gov"] = 0.0
                session._polite_delay("https://example.gov/a")

        self.assertTrue(observed)
        self.assertTrue(all(v >= 0.5 for v in observed), min(observed))

    def test_host_timestamp_is_recorded(self):
        with patch("crawler.session.time.sleep"):
            self.session._polite_delay("https://example.gov/a")
        self.assertIn("example.gov", self.session._last_request_times)


class TestFetchPage(unittest.TestCase):

    def setUp(self):
        self.session = SafeHTTPSession(default_delay=0)

    def test_sends_headers_and_params(self):
        with patch.object(self.session.session, "get", return_value=_response(b"ok")) as mock_get, \
                patch("crawler.session.time.sleep"):
            self.session.fetch_page(
                "https://example.gov/api",
                extra_headers={"Accept": "application/json"},
                params={"limit": "5"},
            )

        kwargs = mock_get.call_args.kwargs
        self.assertEqual(kwargs["headers"], {"Accept": "application/json"})
        self.assertEqual(kwargs["params"], {"limit": "5"})
        self.assertTrue(kwargs["allow_redirects"])

    def test_omits_params_when_none_given(self):
        with patch.object(self.session.session, "get", return_value=_response(b"ok")) as mock_get, \
                patch("crawler.session.time.sleep"):
            self.session.fetch_page("https://example.gov/page")
        self.assertIsNone(mock_get.call_args.kwargs["params"])

    def test_http_error_propagates(self):
        failing = MagicMock()
        failing.raise_for_status.side_effect = requests.HTTPError("403 Forbidden")
        with patch.object(self.session.session, "get", return_value=failing), \
                patch("crawler.session.time.sleep"), patch("tenacity.nap.time.sleep"):
            with self.assertRaises(requests.HTTPError):
                self.session.fetch_page("https://example.gov/blocked")

    def test_retries_three_times_on_connection_error(self):
        with patch.object(self.session.session, "get",
                          side_effect=requests.ConnectionError("down")) as mock_get, \
                patch("crawler.session.time.sleep"), patch("tenacity.nap.time.sleep"):
            with self.assertRaises(requests.ConnectionError):
                self.session.fetch_page("https://example.gov")
        self.assertEqual(mock_get.call_count, 3)


class TestDownloadStreamSafetyCap(unittest.TestCase):
    """A 4GB VPS must not be taken down by one oversized PDF."""

    def setUp(self):
        self.session = SafeHTTPSession(default_delay=0, max_file_size=1000)

    def test_downloads_and_joins_chunks(self):
        res = _response(headers={"Content-Length": "6"}, chunks=[b"abc", b"def"])
        with patch.object(self.session.session, "get", return_value=res), \
                patch("crawler.session.time.sleep"):
            self.assertEqual(self.session.download_stream("https://example.gov/a.pdf"), b"abcdef")

    def test_rejects_on_content_length_before_downloading(self):
        """The header check must abort before any bytes are pulled."""
        res = _response(headers={"Content-Length": "5000"}, chunks=[b"x" * 5000])
        with patch.object(self.session.session, "get", return_value=res), \
                patch("crawler.session.time.sleep"), patch("tenacity.nap.time.sleep"):
            with self.assertRaises(ValueError) as ctx:
                self.session.download_stream("https://example.gov/huge.pdf")

        self.assertIn("exceeds maximum safety limit", str(ctx.exception))
        res.iter_content.assert_not_called()

    def test_aborts_mid_stream_when_server_lies_about_size(self):
        """No Content-Length, or a false one, is caught by the running total."""
        res = _response(headers={}, chunks=[b"x" * 400] * 10)
        with patch.object(self.session.session, "get", return_value=res), \
                patch("crawler.session.time.sleep"), patch("tenacity.nap.time.sleep"):
            with self.assertRaises(ValueError) as ctx:
                self.session.download_stream("https://example.gov/lying.pdf")

        self.assertIn("exceeded safety threshold", str(ctx.exception))

    def test_skips_empty_keepalive_chunks(self):
        res = _response(headers={}, chunks=[b"abc", b"", None, b"def"])
        with patch.object(self.session.session, "get", return_value=res), \
                patch("crawler.session.time.sleep"):
            self.assertEqual(self.session.download_stream("https://example.gov/a.pdf"), b"abcdef")

    def test_default_cap_is_fifty_megabytes(self):
        self.assertEqual(MAX_DOWNLOAD_BYTES, 50 * 1024 * 1024)
        self.assertEqual(SafeHTTPSession().max_file_size, MAX_DOWNLOAD_BYTES)


class TestSessionLifecycle(unittest.TestCase):

    def test_close_releases_the_pool(self):
        session = SafeHTTPSession()
        with patch.object(session.session, "close") as mock_close:
            session.close()
        mock_close.assert_called_once()

    def test_user_agent_carries_a_contact_address(self):
        ua = SafeHTTPSession().session.headers["User-Agent"]
        self.assertIn("JurisMon", ua)
        self.assertIn("@", ua)

    def test_custom_user_agent_is_honoured(self):
        session = SafeHTTPSession(user_agent="TestBot/9.9")
        self.assertEqual(session.session.headers["User-Agent"], "TestBot/9.9")
        self.assertEqual(session.user_agent, "TestBot/9.9")


class TestOCRAvailability(unittest.TestCase):
    """Tesseract is an external binary; every entry point must degrade safely."""

    def test_unavailable_when_libraries_are_missing(self):
        with patch("extractor.ocr.OCR_SUPPORTED", False):
            self.assertFalse(OCRExtractor.is_available())

    def test_unavailable_when_binary_is_absent(self):
        with patch("extractor.ocr.OCR_SUPPORTED", True), \
                patch("extractor.ocr.pytesseract.get_tesseract_version",
                      side_effect=Exception("TesseractNotFoundError")):
            self.assertFalse(OCRExtractor.is_available())

    def test_available_when_binary_reports_a_version(self):
        with patch("extractor.ocr.OCR_SUPPORTED", True), \
                patch("extractor.ocr.pytesseract.get_tesseract_version", return_value="5.3.0"):
            self.assertTrue(OCRExtractor.is_available())


class TestOCRPreprocessing(unittest.TestCase):

    def _colour_image(self):
        img = Image.new("RGB", (60, 30), color=(180, 40, 40))
        for x in range(0, 60, 4):
            for y in range(30):
                img.putpixel((x, y), (20, 20, 20))
        return img

    def test_converts_to_greyscale(self):
        processed = OCRExtractor.preprocess_image(self._colour_image())
        self.assertEqual(processed.mode, "L")

    def test_preserves_dimensions(self):
        img = self._colour_image()
        self.assertEqual(OCRExtractor.preprocess_image(img).size, img.size)

    def test_autocontrast_widens_the_tonal_range(self):
        """Faint scans are the reason OCR accuracy drops; contrast is stretched."""
        faint = Image.new("L", (40, 40), color=118)
        for x in range(0, 40, 2):
            for y in range(40):
                faint.putpixel((x, y), 138)

        before = faint.getextrema()
        after = OCRExtractor.preprocess_image(faint).getextrema()
        self.assertGreater(after[1] - after[0], before[1] - before[0])


class TestOCRExtraction(unittest.TestCase):

    def _png_bytes(self):
        buf = io.BytesIO()
        Image.new("RGB", (30, 20), color="white").save(buf, format="PNG")
        return buf.getvalue()

    def test_image_bytes_returns_empty_when_ocr_unavailable(self):
        with patch.object(OCRExtractor, "is_available", return_value=False):
            self.assertEqual(OCRExtractor.extract_from_image_bytes(self._png_bytes()), "")

    def test_image_bytes_returns_stripped_text(self):
        with patch.object(OCRExtractor, "is_available", return_value=True), \
                patch("extractor.ocr.pytesseract.image_to_string",
                      return_value="  SECTION 4.2 SETBACKS \n"):
            self.assertEqual(
                OCRExtractor.extract_from_image_bytes(self._png_bytes()),
                "SECTION 4.2 SETBACKS",
            )

    def test_corrupt_image_bytes_do_not_raise(self):
        with patch.object(OCRExtractor, "is_available", return_value=True):
            self.assertEqual(OCRExtractor.extract_from_image_bytes(b"not-an-image"), "")

    def test_pdf_page_warns_and_returns_empty_without_tesseract(self):
        with patch.object(OCRExtractor, "is_available", return_value=False):
            with self.assertLogs("jurismon.ocr", level="WARNING") as captured:
                result = OCRExtractor.extract_from_pdf_page_image(MagicMock())
        self.assertEqual(result, "")
        self.assertTrue(any("Tesseract" in line for line in captured.output))

    def test_pdf_page_renders_at_double_scale_for_sharpness(self):
        page = MagicMock()
        pix = MagicMock()
        pix.tobytes.return_value = self._png_bytes()
        page.get_pixmap.return_value = pix

        with patch.object(OCRExtractor, "is_available", return_value=True), \
                patch("extractor.ocr.pytesseract.image_to_string", return_value="ORDINANCE 12"):
            text = OCRExtractor.extract_from_pdf_page_image(page)

        self.assertEqual(text, "ORDINANCE 12")
        page.get_pixmap.assert_called_once()
        matrix = page.get_pixmap.call_args.kwargs["matrix"]
        self.assertEqual((matrix.a, matrix.d), (2.0, 2.0))
        pix.tobytes.assert_called_once_with("png")

    def test_pdf_page_render_failure_is_contained(self):
        page = MagicMock()
        page.get_pixmap.side_effect = Exception("page render failed")
        with patch.object(OCRExtractor, "is_available", return_value=True):
            self.assertEqual(OCRExtractor.extract_from_pdf_page_image(page), "")


CIVICPLUS_PAGE = b"""
<html><body>
  <a href="/AgendaCenter/ViewFile/Agenda/_09282026-1234">Planning Board Agenda</a>
  <a href="/DocumentCenter/View/8821/Zoning-Ordinance-Amendment">Zoning Ordinance Amendment</a>
  <a href="/DocumentCenter/View/8821/Zoning-Ordinance-Amendment">Duplicate link</a>
  <a href="https://cdn.example.gov/minutes/march.pdf">March Meeting Minutes</a>
  <a href="javascript:void(0)">Open menu</a>
  <a href="#content">Skip</a>
  <a href="/DocumentCenter/View/9001/untitled" title="Fallback Title"></a>
  <a href="/news">City News</a>
</body></html>
"""


class TestCivicPlusAdapter(unittest.TestCase):

    def setUp(self):
        res = _response(CIVICPLUS_PAGE)
        self.http = MagicMock()
        self.http.fetch_page.return_value = res
        self.adapter = CivicPlusAdapter(session=self.http)
        self.config = {
            "id": "site-cp", "name": "CivicPlus City",
            "base_url": "https://www.examplecity.gov", "selectors_config": {},
        }

    def test_extracts_agenda_and_document_center_links(self):
        docs = self.adapter.extract_documents(self.config)
        urls = [d.url for d in docs]

        self.assertIn("https://www.examplecity.gov/AgendaCenter/ViewFile/Agenda/_09282026-1234", urls)
        self.assertIn("https://www.examplecity.gov/DocumentCenter/View/8821/Zoning-Ordinance-Amendment", urls)
        self.assertIn("https://cdn.example.gov/minutes/march.pdf", urls)

    def test_excludes_links_outside_the_selector(self):
        urls = " ".join(d.url for d in self.adapter.extract_documents(self.config))
        self.assertNotIn("/news", urls)
        self.assertNotIn("javascript:", urls)
        self.assertNotIn("#content", urls)

    def test_deduplicates_repeated_documents(self):
        urls = [d.url for d in self.adapter.extract_documents(self.config)]
        self.assertEqual(len(urls), len(set(urls)))

    def test_classifies_by_title_and_url(self):
        by_url = {d.url: d.document_type for d in self.adapter.extract_documents(self.config)}
        self.assertEqual(
            by_url["https://www.examplecity.gov/DocumentCenter/View/8821/Zoning-Ordinance-Amendment"],
            "ordinance",
        )
        self.assertEqual(by_url["https://cdn.example.gov/minutes/march.pdf"], "meeting_minutes")

    def test_falls_back_to_title_attribute_then_default(self):
        docs = self.adapter.extract_documents(self.config)
        titles = [d.title for d in docs]
        self.assertTrue(
            "Fallback Title" in titles or "CivicPlus Document" in titles,
            f"empty anchor produced no usable title: {titles}",
        )

    def test_tags_documents_with_the_platform(self):
        for doc in self.adapter.extract_documents(self.config):
            self.assertEqual(doc.extra_metadata["platform"], "civicplus")
            self.assertEqual(doc.source_id, "site-cp")

    def test_custom_selector_overrides_the_default(self):
        config = dict(self.config, selectors_config={"link_selector": "a[href*='/news']"})
        docs = self.adapter.extract_documents(config)
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].url, "https://www.examplecity.gov/news")

    def test_unreachable_portal_surfaces_as_failed_crawl(self):
        self.http.fetch_page.side_effect = requests.ConnectionError("portal down")
        result = self.adapter.crawl(self.config)

        self.assertFalse(result.success)
        self.assertIn("portal down", result.error_message)
        self.assertEqual(result.documents, [])


if __name__ == "__main__":
    unittest.main()
