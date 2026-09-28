"""JurisMon HTML Notice Extractor.

Sub-Task 2.5:
Extracts clean statutory text from HTML municipal pages, removing navigation,
headers, footers, stylesheets, forms, and tracking scripts.
"""

from typing import List, Tuple, Optional
from bs4 import BeautifulSoup
from extractor.cleaner import TextCleaner


class HTMLExtractor:
    """Extracts cleaned statutory and notice text from HTML pages."""

    NON_CONTENT_TAGS = ["script", "style", "nav", "footer", "header", "noscript", "svg", "form", "aside", "iframe"]

    @classmethod
    def extract_from_html(
        cls,
        html_content: str,
        target_selector: Optional[str] = None,
        custom_disclaimers: Optional[List[str]] = None,
    ) -> Tuple[str, str]:
        """
        Extracts and cleans text from HTML string.
        Returns:
            Tuple of (cleaned_text, raw_text)
        """
        if not html_content or not html_content.strip():
            return "", ""

        soup = BeautifulSoup(html_content, "lxml")

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
                soup.select_one("main")
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
