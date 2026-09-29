"""Tests for the connectors added for the 18 additional statutory sources.

Covers the XML/Atom feed adapter, the direct-document adapter, and the
url_template and params handling added to the REST connector.
"""

import json
import unittest
from unittest.mock import MagicMock

from crawler.adapters import get_adapter
from crawler.adapters.xml_feed import XmlFeedAdapter
from crawler.adapters.direct_document import DirectDocumentAdapter
from crawler.adapters.rest_api import RestApiAdapter


def _session_returning(content: bytes, headers=None, payload=None) -> MagicMock:
    """A SafeHTTPSession stand-in whose fetch_page returns a canned response."""
    res = MagicMock()
    res.content = content
    res.headers = headers or {}
    if payload is not None:
        res.json.return_value = payload
    else:
        res.json.side_effect = ValueError("not json")

    session = MagicMock()
    session.fetch_page.return_value = res
    session.user_agent = "JurisMonBot/1.0"
    return session


ATOM_FEED = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>New Statutory Instruments</title>
  <entry>
    <title>The Green Gas Support Scheme (Amendment) Regulations 2026</title>
    <link href="https://www.legislation.gov.uk/id/uksi/2026/1051"/>
    <updated>2026-09-25T00:00:00Z</updated>
  </entry>
  <entry>
    <title>The Air Navigation (Restriction of Flying) Regulations 2026</title>
    <link href="https://www.legislation.gov.uk/id/uksi/2026/1054"/>
    <updated>2026-09-26T00:00:00Z</updated>
  </entry>
  <entry>
    <title>Duplicate Entry</title>
    <link href="https://www.legislation.gov.uk/id/uksi/2026/1051"/>
  </entry>
  <entry>
    <title>Entry With No Link</title>
  </entry>
</feed>
"""

RSS_FEED = b"""<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item>
    <title>Zoning Ordinance Amendment 44</title>
    <link>https://example.gov/ordinances/44.pdf</link>
    <pubDate>Mon, 28 Sep 2026 10:00:00 GMT</pubDate>
  </item>
</channel></rss>
"""

XML_INDEX = b"""<?xml version="1.0"?>
<Legis>
  <Act><title>Environmental Protection Act</title><link href="/eng/acts/E-14/"/></Act>
  <Act><title>Fisheries Act</title><link href="/eng/acts/F-14/"/></Act>
</Legis>
"""


class TestXmlFeedAdapter(unittest.TestCase):

    def _adapter(self, content):
        return XmlFeedAdapter(session=_session_returning(content))

    def test_parses_atom_entries(self):
        adapter = self._adapter(ATOM_FEED)
        docs = adapter.extract_documents({
            "id": "uk-atom",
            "name": "UK New SIs",
            "base_url": "https://www.legislation.gov.uk/new/uksi",
            "selectors_config": {"date_tag": "updated"},
        })

        titles = [d.title for d in docs]
        self.assertIn("The Green Gas Support Scheme (Amendment) Regulations 2026", titles)
        self.assertEqual(docs[0].source_id, "uk-atom")
        self.assertEqual(docs[0].extra_metadata["source_format"], "xml_feed")

    def test_reads_link_from_atom_href_attribute(self):
        """Atom puts the URL in an attribute, not in the element text."""
        docs = self._adapter(ATOM_FEED).extract_documents({
            "id": "uk", "base_url": "https://www.legislation.gov.uk/new/uksi",
            "selectors_config": {},
        })
        self.assertIn("https://www.legislation.gov.uk/id/uksi/2026/1051",
                      [d.url for d in docs])

    def test_reads_link_from_rss_element_text(self):
        docs = self._adapter(RSS_FEED).extract_documents({
            "id": "rss", "base_url": "https://example.gov/feed",
            "selectors_config": {},
        })
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].url, "https://example.gov/ordinances/44.pdf")

    def test_deduplicates_and_skips_entries_without_links(self):
        docs = self._adapter(ATOM_FEED).extract_documents({
            "id": "uk", "base_url": "https://www.legislation.gov.uk/new/uksi",
            "selectors_config": {},
        })
        urls = [d.url for d in docs]
        self.assertEqual(len(urls), len(set(urls)))
        self.assertEqual(len(docs), 2)  # 4 entries, one duplicate, one linkless

    def test_captures_publication_date_when_configured(self):
        docs = self._adapter(ATOM_FEED).extract_documents({
            "id": "uk", "base_url": "https://www.legislation.gov.uk/new/uksi",
            "selectors_config": {"date_tag": "updated"},
        })
        self.assertEqual(docs[0].extra_metadata["date"], "2026-09-25T00:00:00Z")

    def test_resolves_relative_links_in_xml_index(self):
        docs = self._adapter(XML_INDEX).extract_documents({
            "id": "ca", "base_url": "https://laws-lois.justice.gc.ca/eng/XML/Legis.xml",
            "selectors_config": {"item_tag": "Act"},
        })
        self.assertEqual(len(docs), 2)
        self.assertIn("https://laws-lois.justice.gc.ca/eng/acts/E-14/",
                      [d.url for d in docs])

    def test_returns_empty_when_no_records_match(self):
        adapter = self._adapter(b"<?xml version='1.0'?><document><body>text</body></document>")
        docs = adapter.extract_documents({
            "id": "x", "base_url": "https://example.gov/a.xml", "selectors_config": {},
        })
        self.assertEqual(docs, [])

    def test_classifies_documents_from_title(self):
        docs = self._adapter(RSS_FEED).extract_documents({
            "id": "rss", "base_url": "https://example.gov/feed", "selectors_config": {},
        })
        self.assertEqual(docs[0].document_type, "ordinance")


class TestDirectDocumentAdapter(unittest.TestCase):
    """Sources that are a single Act rather than a listing page."""

    def test_registers_the_url_as_one_document(self):
        session = _session_returning(b"<xml/>", headers={"content-type": "application/xml; charset=utf-8"})
        adapter = DirectDocumentAdapter(session=session)

        docs = adapter.extract_documents({
            "id": "site-57-nzlegislation-xml",
            "name": "New Zealand Resource Management Act 1991 (XML)",
            "base_url": "https://www.legislation.govt.nz/act/public/1990/109/en/latest.xml",
            "selectors_config": {"document_title": "Resource Management Act 1991 (XML)"},
        })

        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].url,
                         "https://www.legislation.govt.nz/act/public/1990/109/en/latest.xml")
        self.assertEqual(docs[0].title, "Resource Management Act 1991 (XML)")
        self.assertEqual(docs[0].extra_metadata["source_format"], "direct_document")
        self.assertEqual(docs[0].extra_metadata["content_type"], "application/xml")

    def test_falls_back_to_source_name_for_title(self):
        adapter = DirectDocumentAdapter(session=_session_returning(b"%PDF", headers={}))
        docs = adapter.extract_documents({
            "id": "s", "name": "Queensland Planning Act", "base_url": "https://example.gov/act.pdf",
            "selectors_config": {},
        })
        self.assertEqual(docs[0].title, "Queensland Planning Act")

    def test_unreachable_document_propagates_as_failed_crawl(self):
        """The reachability check must surface a dead link, not an empty snapshot."""
        session = MagicMock()
        session.fetch_page.side_effect = Exception("404 Client Error")
        adapter = DirectDocumentAdapter(session=session)

        result = adapter.crawl({
            "id": "s", "name": "Dead Act", "base_url": "https://example.gov/gone.pdf",
            "selectors_config": {},
        })
        self.assertFalse(result.success)
        self.assertIn("404", result.error_message)

    def test_returns_empty_without_a_url(self):
        adapter = DirectDocumentAdapter(session=_session_returning(b""))
        self.assertEqual(adapter.extract_documents({"id": "s", "base_url": ""}), [])


class TestRestApiUrlTemplate(unittest.TestCase):
    """Registers that return only a record id need the document URL built."""

    AU_PAYLOAD = {
        "value": [
            {"id": "C1913L00243", "name": "Inter-State Commission Regulations 1913",
             "makingDate": "1913-01-01"},
            {"id": "C1913L00244", "name": "Financial and Allowance Regulations",
             "makingDate": "1913-02-01"},
        ]
    }

    def test_builds_document_url_from_template(self):
        session = _session_returning(b"{}", payload=self.AU_PAYLOAD)
        adapter = RestApiAdapter(session=session)

        docs = adapter.extract_documents({
            "id": "au", "base_url": "https://api.prod.legislation.gov.au/v1/titles",
            "selectors_config": {
                "items_key": "value", "title_field": "name",
                "url_template": "https://www.legislation.gov.au/{id}",
                "date_field": "makingDate",
            },
        })

        self.assertEqual(len(docs), 2)
        self.assertEqual(docs[0].url, "https://www.legislation.gov.au/C1913L00243")
        self.assertEqual(docs[0].title, "Inter-State Commission Regulations 1913")
        self.assertEqual(docs[0].extra_metadata["date"], "1913-01-01")

    def test_falls_back_when_template_field_is_missing(self):
        """A record missing the templated key must not abort the whole batch."""
        session = _session_returning(b"{}", payload={"value": [{"name": "Untitled record"}]})
        adapter = RestApiAdapter(session=session)

        docs = adapter.extract_documents({
            "id": "au", "base_url": "https://api.example.gov/v1/titles",
            "selectors_config": {
                "items_key": "value", "title_field": "name",
                "url_template": "https://example.gov/{id}",
            },
        })

        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].url, "https://api.example.gov/v1/titles")

    def test_query_params_are_sent_to_the_endpoint(self):
        session = _session_returning(b"{}", payload={"value": []})
        adapter = RestApiAdapter(session=session)

        adapter.extract_documents({
            "id": "au", "base_url": "https://api.example.gov/v1/titles",
            "selectors_config": {"items_key": "value", "params": {"$top": "200"}},
        })

        _, kwargs = session.fetch_page.call_args
        self.assertEqual(kwargs["params"], {"$top": "200"})


class TestAdapterRegistry(unittest.TestCase):

    def test_new_adapter_types_are_registered(self):
        expected = {
            "xml": "XmlFeedAdapter",
            "atom": "XmlFeedAdapter",
            "feed": "XmlFeedAdapter",
            "direct_document": "DirectDocumentAdapter",
            "document": "DirectDocumentAdapter",
            "rest_api": "RestApiAdapter",
        }
        for key, cls_name in expected.items():
            self.assertEqual(get_adapter(key).__class__.__name__, cls_name, key)

    def test_unknown_type_still_falls_back_to_custom(self):
        self.assertEqual(get_adapter("something-new").__class__.__name__, "CustomAdapter")


class TestSitesConfigIntegrity(unittest.TestCase):
    """The source catalogue is operational config; a typo here silently drops a source."""

    @classmethod
    def setUpClass(cls):
        with open("config/sites.json", encoding="utf-8") as f:
            cls.sites = json.load(f)

    def test_every_source_has_required_fields(self):
        for s in self.sites:
            for field in ("id", "name", "base_url", "adapter_type", "is_active"):
                self.assertIn(field, s, f"{s.get('id')} is missing '{field}'")

    def test_ids_and_urls_are_unique(self):
        ids = [s["id"] for s in self.sites]
        urls = [s["base_url"] for s in self.sites]
        self.assertEqual(len(ids), len(set(ids)), "duplicate source id")
        self.assertEqual(len(urls), len(set(urls)), "duplicate base_url")

    def test_every_adapter_type_resolves(self):
        from crawler.adapters import ADAPTER_MAP
        for s in self.sites:
            self.assertIn(s["adapter_type"], ADAPTER_MAP,
                          f"{s['id']} uses unregistered adapter '{s['adapter_type']}'")

    def test_inactive_sources_record_why(self):
        for s in self.sites:
            if not s.get("is_active", True):
                self.assertTrue(s.get("health_status"),
                                f"{s['id']} is inactive without a health_status")

    def test_the_18_additional_sources_are_present(self):
        ids = {s["id"] for s in self.sites}
        for n in range(52, 66):
            self.assertTrue(any(i.startswith(f"site-{n}-") for i in ids),
                            f"source site-{n}-* was not integrated")

    def test_recovered_ontario_gazette_uses_the_working_url(self):
        ontario = next(s for s in self.sites if s["id"] == "site-22-ontario")
        self.assertEqual(ontario["base_url"], "https://www.ontario.ca/search/ontario-gazette")
        self.assertTrue(ontario["is_active"])


if __name__ == "__main__":
    unittest.main()
