"""JurisMon PDF Extractor.

Sub-Task 2.1 & 2.4:
Layout-aware PDF parser with text density analysis, automatic OCR trigger
for scanned pages, and multi-page boilerplate cleaning.
"""

import logging
from typing import Tuple, List, Optional
import pymupdf  # Modern PyMuPDF import
from extractor.cleaner import TextCleaner
from extractor.ocr import OCRExtractor

logger = logging.getLogger("jurismon.pdf_extractor")


class PDFExtractor:
    """Extracts, cleans, and OCRs PDF files with multi-page layout awareness."""

    @classmethod
    def extract_from_bytes(
        cls, pdf_bytes: bytes, custom_disclaimers: Optional[List[str]] = None
    ) -> Tuple[str, str, bool, int]:
        """
        Parses PDF bytes, cleans multi-page artifacts, and applies OCR if scanned.
        Returns:
            Tuple of (cleaned_text, raw_text, ocr_applied, page_count)
        """
        if not pdf_bytes:
            return "", "", False, 0

        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        page_count = len(doc)
        pages_raw_text: List[str] = []
        ocr_applied = False

        for page_idx in range(page_count):
            page = doc[page_idx]
            page_text = page.get_text("text").strip()

            # If text density is very low (< 40 characters), check if it is a scanned document
            if len(page_text) < 40:
                images = page.get_images()
                if images or len(page_text) == 0:
                    logger.info(f"Page {page_idx + 1}/{page_count} has low text density ({len(page_text)} chars). Triggering OCR.")
                    ocr_text = OCRExtractor.extract_from_pdf_page_image(page)
                    if ocr_text:
                        page_text = ocr_text
                        ocr_applied = True

            pages_raw_text.append(page_text)

        doc.close()

        raw_text = "\n\n--- PAGE BREAK ---\n\n".join(pages_raw_text)
        cleaned_text = TextCleaner.clean_multipage_text(pages_raw_text, custom_disclaimers)

        return cleaned_text, raw_text, ocr_applied, page_count
