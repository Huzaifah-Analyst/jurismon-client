"""Comprehensive Unit Tests for Day 1: Crawler Engine & Adapters."""

import unittest
from unittest.mock import MagicMock, patch
import requests

from crawler.url_normalizer import URLNormalizer
from crawler.session import SafeHTTPSession
from crawler.adapters.granicus import GranicusAdapter
from crawler.adapters.municode import MunicodeAdapter
from crawler.adapters.civicplus import CivicPlusAdapter
from crawler.adapters.custom import CustomAdapter
from crawler.orchestrator import CrawlOrchestrator


class TestURLNormalizer(unittest.TestCase):

    def test_relative_and_protocol_relative_resolution(self):
        base = "https://www.countygov.org/planning/index.html"
        
        # Relative link
        res1 = URLNormalizer.normalize_url(base, "/documents/zoning_ordinance_2026.pdf")
        self.assertEqual(res1, "https://www.countygov.org/documents/zoning_ordinance_2026.pdf")

        # Protocol-relative link
        res2 = URLNormalizer.normalize_url(base, "//cdn.countygov.org/files/minutes.pdf")
        self.assertEqual(res2, "https://cdn.countygov.org/files/minutes.pdf")

    def test_strip_tracking_and_fragments(self):
        base = "https://www.citygov.org"
        link = "/code?utm_source=newsletter&utm_medium=email&section=12#part-a"
        res = URLNormalizer.normalize_url(base, link)
        self.assertEqual(res, "https://www.citygov.org/code?section=12")

    def test_document_classification(self):
        self.assertEqual(URLNormalizer.classify_document("Zoning Board Meeting Minutes", "https://gov.us/doc.pdf"), "meeting_minutes")
        self.assertEqual(URLNormalizer.classify_document("Ordinance 2026-44 Amendment", "https://gov.us/ord.pdf"), "ordinance")
        self.assertEqual(URLNormalizer.classify_document("Land Use Bylaw Revision", "https://gov.us/bylaw.pdf"), "bylaw")
        self.assertEqual(URLNormalizer.classify_document("General Notice of Hearing", "https://gov.us/notice.pdf"), "notice")


class TestPlatformAdapters(unittest.TestCase):

    def test_granicus_adapter_extracts_table_rows(self):
        html_content = b"""
        <html>
          <body>
            <table class="rgMasterTable">
              <tr>
                <td>Zoning Board Meeting</td>
                <td>09/26/2026</td>
                <td><a href="View.ashx?M=A&ID=12345" id="ctl00_hlAgenda">Agenda</a></td>
                <td><a href="View.ashx?M=M&ID=12345" id="ctl00_hlMinutes">Minutes</a></td>
              </tr>
            </table>
          </body>
        </html>
        """
        mock_response = MagicMock(spec=requests.Response)
        mock_response.content = html_content
        mock_response.status_code = 200

        mock_session = MagicMock(spec=SafeHTTPSession)
        mock_session.fetch_page.return_value = mock_response

        adapter = GranicusAdapter(session=mock_session)
        docs = adapter.extract_documents({
            "id": "granicus-test",
            "name": "Test Granicus",
            "base_url": "https://test.legistar.com/Calendar.aspx"
        })

        self.assertEqual(len(docs), 2)
        self.assertTrue(any("Agenda" in d.title for d in docs))
        self.assertTrue(any("Minutes" in d.title for d in docs))
        self.assertEqual(docs[0].published_date, "09/26/2026")

    def test_municode_adapter_extracts_code_links(self):
        html_content = b"""
        <html>
          <body>
            <div class="toc-container">
              <a href="/codes/chapter_101_zoning.pdf" class="municode-doc-link">Chapter 101 - Zoning</a>
              <a href="/codes/ordinance_2026.pdf">Ordinance 2026 Update</a>
            </div>
          </body>
        </html>
        """
        mock_response = MagicMock(spec=requests.Response)
        mock_response.content = html_content
        mock_response.status_code = 200

        mock_session = MagicMock(spec=SafeHTTPSession)
        mock_session.fetch_page.return_value = mock_response

        adapter = MunicodeAdapter(session=mock_session)
        docs = adapter.extract_documents({
            "id": "municode-test",
            "name": "Test Municode",
            "base_url": "https://library.municode.com/fl/test"
        })

        self.assertEqual(len(docs), 2)
        self.assertEqual(docs[0].title, "Chapter 101 - Zoning")

    def test_custom_adapter_heuristics(self):
        html_content = b"""
        <html>
          <body>
            <div class="content">
              <a href="/downloads/bylaw_amendment_2026.pdf">Bylaw Amendment 2026</a>
              <a href="/about-us">About the Mayor</a>
              <a href="/notices/zoning-hearing.html">Public Notice: Zoning Hearing</a>
            </div>
          </body>
        </html>
        """
        mock_response = MagicMock(spec=requests.Response)
        mock_response.content = html_content
        mock_response.status_code = 200

        mock_session = MagicMock(spec=SafeHTTPSession)
        mock_session.fetch_page.return_value = mock_response

        adapter = CustomAdapter(session=mock_session)
        docs = adapter.extract_documents({
            "id": "custom-test",
            "name": "Test Custom City",
            "base_url": "https://customcity.gov/planning"
        })

        # Should match bylaw and zoning hearing, but exclude /about-us
        self.assertEqual(len(docs), 2)
        titles = [d.title for d in docs]
        self.assertIn("Bylaw Amendment 2026", titles)
        self.assertIn("Public Notice: Zoning Hearing", titles)

    def test_rest_api_adapter_extracts_json_items(self):
        from crawler.adapters.rest_api import RestApiAdapter
        
        mock_response = MagicMock(spec=requests.Response)
        mock_response.json.return_value = {
            "results": [
                {"title": "Ordinance 2026-01 Land Use", "url": "https://api.city.gov/files/ord01.pdf", "description": "Zoning amendment for ADU"},
                {"title": "Meeting Notice 2026", "url": "https://api.city.gov/files/notice.pdf", "description": "Planning commission hearing"}
            ]
        }
        mock_response.status_code = 200

        mock_session = MagicMock(spec=SafeHTTPSession)
        mock_session.fetch_page.return_value = mock_response

        adapter = RestApiAdapter(session=mock_session)
        docs = adapter.extract_documents({
            "id": "api-test",
            "name": "State Open Data Portal",
            "base_url": "https://api.city.gov/datasets/regulations",
            "selectors_config": {"items_key": "results"}
        })

        self.assertEqual(len(docs), 2)
        self.assertEqual(docs[0].title, "Ordinance 2026-01 Land Use")
        self.assertEqual(docs[0].document_type, "ordinance")


class TestCrawlOrchestrator(unittest.TestCase):

    def test_orchestrator_handles_isolated_failures(self):
        sources = [
            {
                "id": "site-1-good",
                "name": "Good Site",
                "base_url": "https://goodsite.gov",
                "adapter_type": "custom",
                "is_active": True
            },
            {
                "id": "site-2-bad",
                "name": "Bad Site (Down)",
                "base_url": "https://badsite-does-not-exist-12345.gov",
                "adapter_type": "custom",
                "is_active": True
            }
        ]

        def mock_crawl_single(source_config):
            from crawler.base import CrawlResult, DiscoveredDocument
            if "good" in source_config["id"]:
                return CrawlResult(
                    source_id=source_config["id"],
                    source_name=source_config["name"],
                    success=True,
                    documents=[DiscoveredDocument(title="Doc 1", url="https://goodsite.gov/doc1.pdf")],
                    duration_seconds=0.1
                )
            else:
                return CrawlResult(
                    source_id=source_config["id"],
                    source_name=source_config["name"],
                    success=False,
                    documents=[],
                    error_message="Connection refused",
                    duration_seconds=0.1
                )

        orchestrator = CrawlOrchestrator(max_workers=2)
        with patch.object(orchestrator, "crawl_single_source", side_effect=mock_crawl_single):
            summary = orchestrator.run_all(sources)

        self.assertEqual(summary.total_sources, 2)
        self.assertEqual(summary.succeeded_sources, 1)
        self.assertEqual(summary.failed_sources, 1)
        self.assertEqual(summary.total_documents_discovered, 1)
        self.assertEqual(len(summary.failed_source_details), 1)


if __name__ == "__main__":
    unittest.main()
