"""Comprehensive Unit Tests for Day 2: Extraction, Cleaning & OCR Engine."""

import io
import unittest
import pymupdf
from PIL import Image

from extractor.cleaner import TextCleaner
from extractor.pdf_extractor import PDFExtractor
from extractor.html_extractor import HTMLExtractor
from extractor.ocr import OCRExtractor


class TestTextCleaner(unittest.TestCase):

    def test_cleaner_strips_repeating_headers_and_footers(self):
        page1 = """Town of Greenfield - Board of Zoning Appeals
Page 1 of 3
Notice of Public Hearing for Variance Application 2026-08.
The applicant requests a 5-foot setback variance for a garage.
 Official Record of the Town Clerk"""

        page2 = """Town of Greenfield - Board of Zoning Appeals
Page 2 of 3
Staff report indicates no adverse impact on adjacent properties.
Motion made to approve variance subject to drainage plan.
 Official Record of the Town Clerk"""

        page3 = """Town of Greenfield - Board of Zoning Appeals
Page 3 of 3
Vote taken: 5 in favor, 0 opposed. Hearing closed at 8:15 PM.
 Official Record of the Town Clerk"""

        pages = [page1, page2, page3]
        cleaned = TextCleaner.clean_multipage_text(pages)

        # Repeating header and footer must be stripped across pages
        self.assertNotIn("Town of Greenfield - Board of Zoning Appeals", cleaned)
        self.assertNotIn("Official Record of the Town Clerk", cleaned)
        self.assertNotIn("Page 1 of 3", cleaned)

        # Unique meeting content must be preserved
        self.assertIn("Notice of Public Hearing for Variance Application 2026-08.", cleaned)
        self.assertIn("Staff report indicates no adverse impact on adjacent properties.", cleaned)
        self.assertIn("Vote taken: 5 in favor, 0 opposed.", cleaned)

    def test_cleaner_strips_boilerplate_disclaimers(self):
        text = """
§ 105.4 Commercial Loading Docks.
All commercial buildings exceeding 10,000 sq ft shall provide off-street loading.

This document is provided for informational purposes only.
Draft - Subject to Change
Crown Copyright 2026
"""
        cleaned = TextCleaner.clean_single_text(text)
        self.assertIn("§ 105.4 Commercial Loading Docks.", cleaned)
        self.assertIn("All commercial buildings exceeding 10,000 sq ft shall provide off-street loading.", cleaned)
        self.assertNotIn("This document is provided for informational purposes only.", cleaned)
        self.assertNotIn("Draft - Subject to Change", cleaned)
        self.assertNotIn("Crown Copyright 2026", cleaned)

    def test_cleaner_dehyphenates_line_breaks(self):
        text = """
The planning commission approved the resi-\ndential zoning ordi-\nnance update.
"""
        cleaned = TextCleaner.clean_single_text(text)
        self.assertIn("residential zoning ordinance update.", cleaned)


class TestPDFExtractor(unittest.TestCase):

    def test_pdf_extractor_in_memory_multi_page(self):
        """Generates an in-memory PDF and tests layout-aware text extraction."""
        doc = pymupdf.open()
        
        # Create Page 1
        page1 = doc.new_page()
        page1.insert_text((50, 50), "County Zoning Board Header\nPage 1 of 2\nOrdinance No. 2026-101: Solar Energy Systems.")
        
        # Create Page 2
        page2 = doc.new_page()
        page2.insert_text((50, 50), "County Zoning Board Header\nPage 2 of 2\nRooftop solar collectors are permitted in all districts.")

        pdf_bytes = doc.tobytes()
        doc.close()

        cleaned_text, raw_text, ocr_applied, page_count = PDFExtractor.extract_from_bytes(pdf_bytes)

        self.assertEqual(page_count, 2)
        self.assertFalse(ocr_applied)
        self.assertIn("Ordinance No. 2026-101: Solar Energy Systems.", cleaned_text)
        self.assertIn("Rooftop solar collectors are permitted in all districts.", cleaned_text)
        # Repeating header should be stripped
        self.assertNotIn("County Zoning Board Header", cleaned_text)


class TestHTMLExtractor(unittest.TestCase):

    def test_html_extractor_decomposes_noise(self):
        html = """
        <!DOCTYPE html>
        <html>
          <head><title>Zoning Notice</title></head>
          <body>
            <nav><a href="/">Home</a><a href="/contact">Contact</a></nav>
            <main>
              <h1>Special Use Permit Notice</h1>
              <p>Hearing date: October 12, 2026 for parcel #4492.</p>
            </main>
            <footer>Copyright 2026 Municipal Portal</footer>
          </body>
        </html>
        """
        cleaned, raw = HTMLExtractor.extract_from_html(html)
        self.assertIn("Special Use Permit Notice", cleaned)
        self.assertIn("Hearing date: October 12, 2026 for parcel #4492.", cleaned)
        self.assertNotIn("Home", cleaned)
        self.assertNotIn("Contact", cleaned)
        self.assertNotIn("Copyright 2026", cleaned)


class TestOCRExtractor(unittest.TestCase):

    def test_image_preprocessing(self):
        """Tests that image preprocessing enhances contrast and converts to grayscale."""
        img = Image.new("RGB", (100, 100), color=(200, 100, 100))
        processed = OCRExtractor.preprocess_image(img)
        self.assertEqual(processed.mode, "L")  # Grayscale
        self.assertEqual(processed.size, (100, 100))


if __name__ == "__main__":
    unittest.main()
