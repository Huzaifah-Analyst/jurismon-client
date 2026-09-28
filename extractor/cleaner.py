"""JurisMon Text Cleaner & Boilerplate Stripper.

Sub-Task 2.2 & 2.3:
- Cross-page frequency analysis for repeating headers, footers, and page numbers
- Strips legal disclaimers, draft stamps, and official boilerplate
- Normalizes unicode artifacts, line breaks, and de-hyphenates words
"""

import re
from typing import List, Set, Optional

# Comprehensive municipal boilerplate regex patterns (US, UK, Canada, Australia)
DEFAULT_DISCLAIMER_PATTERNS = [
    # Page numbers: "Page 1 of 5", "Page 1", "1 of 5", " - 3 - "
    re.compile(r"^\s*(?:Page\s+\d+\s+(?:of\s+\d+)?|\d+\s*/\s*\d+|\-\s*\d+\s*\-|\bPage\s+\d+\b)\s*$", re.IGNORECASE | re.MULTILINE),
    # Common legal boilerplate
    re.compile(r"^\s*This document is (?:provided )?for informational purposes only.*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*Official copy (?:is )?on file in the office of the (?:City|County|Town) Clerk.*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*All rights reserved\..*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*Draft\s*[-–—]\s*Subject to (?:Change|Approval|Correction).*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*Published pursuant to (?:state law|municipal code|local government act).*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*For questions regarding this agenda please contact.*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*In accordance with the Americans with Disabilities Act.*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*Crown Copyright\s*\d{4}.*$", re.IGNORECASE | re.MULTILINE),
]


class TextCleaner:
    """Production-grade text sanitizer for municipal and zoning statutory texts."""

    @classmethod
    def clean_multipage_text(cls, pages_text: List[str], custom_disclaimers: Optional[List[str]] = None) -> str:
        """
        Cleans multiple pages of a document by detecting cross-page repeating headers/footers.
        """
        if not pages_text:
            return ""

        if len(pages_text) == 1:
            return cls.clean_single_text(pages_text[0], custom_disclaimers)

        # 1. Frequency analysis for headers & footers across pages
        line_occurrences: dict[str, int] = {}
        for page in pages_text:
            unique_lines = set(cls._normalize_line_for_comparison(l) for l in page.splitlines() if l.strip())
            for line in unique_lines:
                if 3 < len(line) < 140:
                    line_occurrences[line] = line_occurrences.get(line, 0) + 1

        total_pages = len(pages_text)
        # If a line appears on >= 60% of pages, it is treated as a running header/footer
        threshold = max(2, int(total_pages * 0.6))
        repeating_artifacts: Set[str] = {
            line for line, count in line_occurrences.items() if count >= threshold
        }

        cleaned_pages = []
        for page in pages_text:
            lines = page.splitlines()
            filtered_lines = [
                line for line in lines
                if cls._normalize_line_for_comparison(line) not in repeating_artifacts
            ]
            cleaned_page = "\n".join(filtered_lines)
            cleaned_result = cls.clean_single_text(cleaned_page, custom_disclaimers)
            if cleaned_result:
                cleaned_pages.append(cleaned_result)

        return "\n\n".join(cleaned_pages)

    @classmethod
    def clean_single_text(cls, text: str, custom_disclaimers: Optional[List[str]] = None) -> str:
        """Cleans a single page or statutory text block."""
        if not text:
            return ""

        # Normalize unicode spaces and quotes
        text = (
            text.replace("\xa0", " ")
            .replace("\u2019", "'")
            .replace("\u2018", "'")
            .replace("\u201c", '"')
            .replace("\u201d", '"')
            .replace("\u2014", " - ")
            .replace("\u2013", " - ")
        )

        # De-hyphenate broken words across line breaks (e.g. "ordi-\nnance" -> "ordinance")
        text = re.sub(r"(\b[A-Za-z]+)-\n([A-Za-z]+\b)", r"\1\2", text)

        # Strip standard boilerplate patterns
        for pattern in DEFAULT_DISCLAIMER_PATTERNS:
            text = pattern.sub("", text)

        # Strip custom per-source disclaimers
        if custom_disclaimers:
            for disclaimer in custom_disclaimers:
                text = re.sub(re.escape(disclaimer), "", text, flags=re.IGNORECASE)

        # Collapse excessive blank lines
        lines = [l.strip() for l in text.splitlines()]
        output_lines = []
        consecutive_empty = 0

        for line in lines:
            if not line:
                consecutive_empty += 1
                if consecutive_empty <= 1:
                    output_lines.append("")
            else:
                consecutive_empty = 0
                output_lines.append(line)

        return "\n".join(output_lines).strip()

    @staticmethod
    def _normalize_line_for_comparison(line: str) -> str:
        """Strips numbers/dates for header comparison (e.g. 'Minutes - Page 1' matches 'Minutes - Page 2')."""
        normalized = re.sub(r"\d+", "#", line.strip().lower())
        return re.sub(r"\s+", " ", normalized)
