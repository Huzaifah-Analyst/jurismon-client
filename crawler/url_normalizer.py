"""JurisMon URL Normalizer & Document Classifier.

Sub-Task 1.2:
- Resolves relative, absolute, and protocol-relative links
- Strips URL fragments (#) and non-essential tracking parameters
- Categorizes document types (ordinance, meeting_minutes, bylaw, notice, zoning_code)
- Classifies target format (PDF, HTML, etc.)
"""

import re
from typing import Tuple
from urllib.parse import urljoin, urlparse, urlunparse, parse_qsl, urlencode


class URLNormalizer:
    """Normalizes URLs and classifies municipal document metadata."""

    TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "fbclid", "gclid"}
    
    EXCLUDED_DOMAINS = {
        "instagram.com", "facebook.com", "twitter.com", "x.com", "youtube.com",
        "linkedin.com", "pinterest.com", "tiktok.com", "google.com", "apple.com",
        "cloudflare.com", "cookiebot.com", "schema.org", "w3.org", "recaptcha.net",
        "doubleclick.net", "googletagmanager.com", "onetrust.com", "trustarc.com"
    }

    @classmethod
    def is_valid_statutory_url(cls, url: str) -> bool:
        """Filters out social media, marketing, and non-statutory links."""
        try:
            domain = urlparse(url).netloc.lower()
            return not any(excl in domain for excl in cls.EXCLUDED_DOMAINS)
        except Exception:
            return False

    @classmethod
    def normalize_url(cls, base_url: str, link_href: str) -> str:
        """
        Normalizes a target link relative to its base URL.
        Handles relative paths, protocol-relative links, and fragments.
        """
        if not link_href or not link_href.strip():
            return ""

        clean_href = link_href.strip()

        # Handle protocol-relative URLs (//example.com/doc.pdf)
        if clean_href.startswith("//"):
            base_scheme = urlparse(base_url).scheme or "https"
            clean_href = f"{base_scheme}:{clean_href}"

        # Join relative path to base URL
        full_url = urljoin(base_url, clean_href)

        # Parse and sanitize components
        parsed = urlparse(full_url)

        # Force https if scheme is missing
        scheme = parsed.scheme if parsed.scheme in ("http", "https") else "https"

        # Remove anchor fragment (#section-1)
        fragment = ""

        # Filter out tracking query params
        if parsed.query:
            query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
            filtered_pairs = [(k, v) for k, v in query_pairs if k.lower() not in cls.TRACKING_PARAMS]
            query = urlencode(filtered_pairs)
        else:
            query = ""

        normalized = urlunparse((
            scheme,
            parsed.netloc.lower(),
            parsed.path,
            parsed.params,
            query,
            fragment
        ))

        return normalized

    @classmethod
    def is_pdf(cls, url: str, content_type: str = "") -> bool:
        """Checks whether the target URL or Content-Type header represents a PDF document."""
        if content_type and "application/pdf" in content_type.lower():
            return True

        path_lower = urlparse(url).path.lower()
        if path_lower.endswith(".pdf"):
            return True

        # Common municipal ASPX/ASHX handlers that return PDFs (e.g. Granicus View.ashx)
        if "view.ashx" in path_lower or "viewfile" in path_lower or "documentcenter" in path_lower:
            return True

        return False

    @classmethod
    def classify_document(cls, title: str, url: str) -> str:
        """
        Infers document type based on title text and URL path heuristics.
        Returns one of: 'ordinance', 'meeting_minutes', 'bylaw', 'zoning_code', 'notice'
        """
        combined = f"{title.lower()} {url.lower()}"

        if any(w in combined for w in ("minute", "agenda", "calendar", "board-meeting", "session")):
            return "meeting_minutes"
        if any(w in combined for w in ("ordinance", "amendment", "statute", "rule")):
            return "ordinance"
        if any(w in combined for w in ("bylaw", "by-law", "land-use")):
            return "bylaw"
        if any(w in combined for w in ("zoning", "code-of-ordinances", "municode", "ecode360")):
            return "zoning_code"

        return "notice"
