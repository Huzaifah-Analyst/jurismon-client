"""JurisMon Tesseract OCR Extractor Fallback.

Sub-Task 2.4:
- Pre-processes images for high-accuracy OCR (grayscale, contrast boost)
- Scales PDF page rendering to 2.0x (144 DPI)
- Graceful error handling when Tesseract binary is not present
"""

import io
import logging
from typing import Optional

logger = logging.getLogger("jurismon.ocr")

try:
    import pytesseract
    from PIL import Image, ImageEnhance, ImageOps
    import pymupdf  # PyMuPDF
    OCR_SUPPORTED = True
except ImportError:
    OCR_SUPPORTED = False


class OCRExtractor:
    """Performs Optical Character Recognition on scanned PDF pages or images."""

    @classmethod
    def is_available(cls) -> bool:
        if not OCR_SUPPORTED:
            return False
        try:
            # Check if tesseract binary is runnable
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    @classmethod
    def preprocess_image(cls, image: Image.Image) -> Image.Image:
        """Enhances image contrast and converts to grayscale for higher OCR accuracy."""
        # 1. Convert to grayscale
        gray = image.convert("L")
        # 2. Boost contrast
        enhancer = ImageEnhance.Contrast(gray)
        enhanced = enhancer.enhance(1.8)
        # 3. Autocontrast
        auto = ImageOps.autocontrast(enhanced)
        return auto

    @classmethod
    def extract_from_pdf_page_image(cls, page: "pymupdf.Page") -> str:
        """Renders a PDF page to image and runs OCR."""
        if not cls.is_available():
            logger.warning("Tesseract OCR is not installed or available on the host.")
            return ""

        try:
            # Render page at 2.0x zoom (144 DPI) for sharp text detection
            matrix = pymupdf.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=matrix)
            img_bytes = pix.tobytes("png")
            
            raw_image = Image.open(io.BytesIO(img_bytes))
            processed = cls.preprocess_image(raw_image)
            
            text = pytesseract.image_to_string(processed, lang="eng", config="--psm 6")
            return text.strip()
        except Exception as e:
            logger.error(f"Error during PDF page OCR: {e}")
            return ""

    @classmethod
    def extract_from_image_bytes(cls, image_bytes: bytes) -> str:
        """Runs OCR directly on raw image bytes."""
        if not cls.is_available():
            return ""

        try:
            raw_image = Image.open(io.BytesIO(image_bytes))
            processed = cls.preprocess_image(raw_image)
            text = pytesseract.image_to_string(processed, lang="eng", config="--psm 6")
            return text.strip()
        except Exception as e:
            logger.error(f"Error during raw image OCR: {e}")
            return ""
