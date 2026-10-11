"""JurisMon HTML Notice Extractor.

Sub-Task 2.5:
Extracts clean statutory text from HTML municipal pages, removing navigation,
headers, footers, stylesheets, forms, and tracking scripts.
"""

import re
from urllib.parse import urlparse, urljoin
from lxml import etree
from typing import List, Tuple, Optional
from bs4 import BeautifulSoup
from extractor.cleaner import TextCleaner


class NonDocumentPage(ValueError):
    """A feed/catalogue page, not the text of a legal document."""


class HTMLExtractor:
    """Extracts cleaned statutory and notice text from HTML pages."""

    NON_CONTENT_TAGS = ["script", "style", "nav", "footer", "noscript", "svg", "form", "aside", "iframe"]

    @staticmethod
    def embedded_document_url(html_content: str, source_url: str) -> Optional[str]:
        """Follow only the official AU registry's same-host legal text iframe."""
        source = urlparse(source_url)
        if source.hostname != "www.legislation.gov.au":
            return None
        frame = BeautifulSoup(html_content, "lxml").select_one("iframe#epubFrame[src]")
        if frame is None:
            return None
        target = urljoin(source_url, frame["src"])
        parsed = urlparse(target)
        if parsed.scheme != "https" or parsed.netloc != source.netloc or "/text/" not in parsed.path or not parsed.path.endswith(".html"):
            raise NonDocumentPage("Unsupported embedded legislation document URL")
        return target

    @classmethod
    def extract_from_html(
        cls,
        html_content: str,
        target_selector: Optional[str] = None,
        custom_disclaimers: Optional[List[str]] = None,
        source_url: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Extracts and cleans text from HTML string.
        Returns:
            Tuple of (cleaned_text, raw_text)
        """
        if not html_content or not html_content.strip():
            return "", ""

        parsed_url = urlparse(source_url or "")
        if parsed_url.hostname == "www.gesetze-im-internet.de" and parsed_url.path == "/aktuDienst.html":
            raise NonDocumentPage("RSS update catalogue is not a legal document")

        # XML statutes need an XML parser: an HTML parser can discard their body.
        if html_content.lstrip().startswith("<?xml") or re.match(r"\s*<(?:act|legislation|regulation|rss|feed|rdf:RDF)\b", html_content):
            xml = re.sub(r'encoding=[\'"][^\'"]+[\'"]', 'encoding="UTF-8"', html_content, count=1)
            root = etree.fromstring(xml.encode("utf-8"), etree.XMLParser(resolve_entities=False, no_network=True))
            name = etree.QName(root).localname.lower()
            if name in {"rss", "feed", "rdf", "catalog"}:
                raise NonDocumentPage("Feed or catalogue metadata is not legal text")
            if name != "html":
                bodies = root.xpath('//*[local-name()="body"]')
                container = bodies[0] if bodies else root
                raw_text = "\n".join(text.strip() for text in container.itertext() if text.strip())
                return TextCleaner.clean_single_text(raw_text, custom_disclaimers), raw_text
            # XHTML pages still need HTML navigation/script stripping.
            html_content = re.sub(r"^\s*<\?xml[^?]*\?>", "", html_content)

        soup = BeautifulSoup(html_content, "lxml")
        if parsed_url.hostname == "www.legislation.gov.au" and soup.select_one("iframe#epubFrame"):
            raise NonDocumentPage("Registry wrapper requires its embedded legal document")
        if soup.select_one(".module-resource .resource-url-analytics, .dataset-resources"):
            raise NonDocumentPage("CKAN resource landing page is not the linked document")

        # Preserve headings that belong to a legal article; remove site headers.
        for header in soup.find_all("header"):
            if not header.find_parent(["article", "main"]):
                header.decompose()

        for element in soup.select('[role="navigation"], [role="tablist"], .breadcrumb, #nav_2022, #fTop, #fusszeile'):
            element.decompose()

        # Decompose non-content elements
        for tag in cls.NON_CONTENT_TAGS:
            for element in soup.find_all(tag):
                element.decompose()

        # Prioritize target selector or semantic containers
        container = None
        if target_selector:
            container = soup.select_one(target_selector)

        if not container:
            container = (
                soup.select_one("#content_2022")
                or soup.select_one("main")
                or soup.select_one("article")
                or soup.select_one("#content")
                or soup.select_one(".content")
                or soup.body
                or soup
            )

        # Extract text lines preserving paragraphs
        lines = []
        for string in container.stripped_strings:
            lines.append(string)

        raw_text = "\n".join(lines)
        cleaned_text = TextCleaner.clean_single_text(raw_text, custom_disclaimers)

        return cleaned_text, raw_text
