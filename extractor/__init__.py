"""JurisMon Extractor Package."""

from extractor.cleaner import TextCleaner

# Optional imports depending on environment
try:
    from extractor.ocr import OCRExtractor
except ImportError:
    OCRExtractor = None

try:
    from extractor.pdf_extractor import PDFExtractor
except ImportError:
    PDFExtractor = None

try:
    from extractor.html_extractor import HTMLExtractor
except ImportError:
    HTMLExtractor = None

__all__ = ["TextCleaner", "OCRExtractor", "PDFExtractor", "HTMLExtractor"]
