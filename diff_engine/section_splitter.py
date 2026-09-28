"""JurisMon Section & Statutory Clause Splitter.

Sub-Task 3.1:
Partitions municipal code, zoning amendments, bylaws, and meeting minutes
into structured clauses keyed on section numbering (§, Section, Article, Chapter, Division)
with robust fallback to paragraph-level units.
"""

import re
from typing import List, Tuple, Optional
from diff_engine.models import Clause

# Comprehensive statutory section header patterns
SECTION_PATTERNS = [
    # § 12-301 or § 4.2.1 or §§ 101-102
    re.compile(r"^(§+\s*[\d]+[A-Za-z0-9\.\-_/]*)(?:\s*[:\.\-–—]?\s*(.*))?$", re.MULTILINE),
    # Section 101.4 or Sec. 12-4 or SEC. 401
    re.compile(r"^(?:Section|Sec\.|SEC\.)\s*([\d]+[A-Za-z0-9\.\-_/]*)(?:\s*[:\.\-–—]?\s*(.*))?$", re.MULTILINE | re.IGNORECASE),
    # Article IV or Art. 3 or ARTICLE 12
    re.compile(r"^(?:Article|Art\.|ART\.)\s*([IVXLCDM\d]+[A-Za-z0-9\.\-_/]*)(?:\s*[:\.\-–—]?\s*(.*))?$", re.MULTILINE | re.IGNORECASE),
    # Chapter 15 or Chap. 3 or CHAPTER VII
    re.compile(r"^(?:Chapter|Chap\.|CHAP\.)\s*([IVXLCDM\d]+[A-Za-z0-9\.\-_/]*)(?:\s*[:\.\-–—]?\s*(.*))?$", re.MULTILINE | re.IGNORECASE),
    # Division 2 or Div. 10
    re.compile(r"^(?:Division|Div\.|DIV\.)\s*([\d]+[A-Za-z0-9\.\-_/]*)(?:\s*[:\.\-–—]?\s*(.*))?$", re.MULTILINE | re.IGNORECASE),
    # Part 4 or PART II
    re.compile(r"^(?:Part|PART)\s*([IVXLCDM\d]+[A-Za-z0-9\.\-_/]*)(?:\s*[:\.\-–—]?\s*(.*))?$", re.MULTILINE),
]


class SectionSplitter:
    """Parses legal and zoning statutory texts into identifiable structured clauses."""

    @classmethod
    def split(cls, text: str) -> Tuple[List[Clause], str]:
        """
        Splits statutory text into clauses.
        Returns:
            Tuple of (List[Clause], strategy: 'section' | 'paragraph')
        """
        if not text or not text.strip():
            return [], "paragraph"

        cleaned_text = text.strip()
        section_clauses = cls._split_by_sections(cleaned_text)

        # If at least 2 distinct sections were identified, use section-based strategy
        if len(section_clauses) >= 2:
            return section_clauses, "section"

        # Otherwise fallback to paragraph-based units
        paragraph_clauses = cls._split_by_paragraphs(cleaned_text)
        return paragraph_clauses, "paragraph"

    @classmethod
    def _split_by_sections(cls, text: str) -> List[Clause]:
        lines = text.splitlines()
        clauses: List[Clause] = []
        current_identifier = None
        current_sec_num = None
        current_title = None
        current_lines: List[str] = []
        start_line = 1

        for idx, raw_line in enumerate(lines, start=1):
            line_str = raw_line.strip()
            matched_header = None
            matched_sec_num = None
            matched_title = None

            for pattern in SECTION_PATTERNS:
                match = pattern.match(line_str)
                if match:
                    matched_sec_num = match.group(1).strip()
                    matched_title = match.group(2).strip() if match.group(2) else None
                    matched_header = line_str
                    break

            if matched_header:
                # Flush previously accumulated section
                if current_identifier and current_lines:
                    clause_text = "\n".join(current_lines).strip()
                    if clause_text:
                        clauses.append(
                            Clause(
                                identifier=current_identifier,
                                section_number=current_sec_num,
                                title=current_title,
                                text=clause_text,
                                line_start=start_line,
                                line_end=idx - 1,
                            )
                        )
                # Initialize new section
                current_identifier = matched_header
                current_sec_num = matched_sec_num
                current_title = matched_title
                current_lines = [raw_line]
                start_line = idx
            else:
                if current_identifier is not None:
                    current_lines.append(raw_line)
                else:
                    # Content before the first section header (Preamble / Recitals)
                    if not clauses and not current_lines:
                        current_identifier = "Preamble & Enacting Clause"
                        current_sec_num = "0"
                        current_title = "Preamble"
                        start_line = 1
                    current_lines.append(raw_line)

        # Flush final accumulated section
        if current_identifier and current_lines:
            clause_text = "\n".join(current_lines).strip()
            if clause_text:
                clauses.append(
                    Clause(
                        identifier=current_identifier,
                        section_number=current_sec_num,
                        title=current_title,
                        text=clause_text,
                        line_start=start_line,
                        line_end=len(lines),
                    )
                )

        return clauses

    @classmethod
    def _split_by_paragraphs(cls, text: str) -> List[Clause]:
        """Fallback splitter dividing text by blank lines."""
        raw_paragraphs = re.split(r"\n\s*\n+", text.strip())
        clauses: List[Clause] = []

        for idx, p in enumerate(raw_paragraphs, start=1):
            content = p.strip()
            if content:
                # First line as title if short
                first_line = content.splitlines()[0].strip()
                title = first_line[:60] if len(first_line) < 60 else None

                clauses.append(
                    Clause(
                        identifier=f"Paragraph {idx}",
                        section_number=str(idx),
                        title=title,
                        text=content,
                        line_start=None,
                        line_end=None,
                    )
                )

        return clauses
