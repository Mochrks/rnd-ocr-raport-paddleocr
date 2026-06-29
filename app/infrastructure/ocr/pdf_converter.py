"""
app/infrastructure/ocr/pdf_converter.py
=========================================
Convert PDF files to a list of PNG image paths for OCR processing.

Strategy:
1. Try PyMuPDF (fitz) — fast, no system dependency
2. Fall back to pdf2image — requires poppler on PATH
3. Raise PDFConversionError if neither is available

Temp images are written to a caller-supplied directory and cleaned up
by the caller (or via tempfile.TemporaryDirectory context manager).
"""

from __future__ import annotations

import logging
import os
from typing import List

from app.core.config import settings
from app.core.exceptions import PDFConversionError

logger = logging.getLogger(__name__)


def convert_pdf_to_images(pdf_path: str, output_dir: str) -> List[str]:
    """
    Convert every page of a PDF file to a PNG image.

    Args:
        pdf_path:   Path to the source PDF file.
        output_dir: Directory where the PNG files will be saved.
                    The caller is responsible for cleanup.

    Returns:
        List of absolute paths to the generated PNG files, one per page.

    Raises:
        PDFConversionError: If no PDF library is available or conversion fails.
    """
    try:
        return _convert_with_pymupdf(pdf_path, output_dir)
    except ImportError:
        logger.warning(
            "PyMuPDF (fitz) not installed. Falling back to pdf2image..."
        )

    try:
        return _convert_with_pdf2image(pdf_path, output_dir)
    except ImportError:
        raise PDFConversionError(
            pdf_path,
            reason=(
                "Neither PyMuPDF nor pdf2image is installed. "
                "Install one with: pip install pymupdf  (recommended)"
            ),
        )


def _convert_with_pymupdf(pdf_path: str, output_dir: str) -> List[str]:
    """Convert using PyMuPDF — preferred because it has no system dependency."""
    import fitz  # type: ignore[import]

    image_paths: List[str] = []
    doc = fitz.open(pdf_path)
    scale = settings.pdf_render_scale
    matrix = fitz.Matrix(scale, scale)

    try:
        for page_num in range(len(doc)):
            page = doc[page_num]
            pix = page.get_pixmap(matrix=matrix)
            img_path = os.path.join(
                output_dir,
                f"pdf_page_{page_num}_{os.path.basename(pdf_path)}.png",
            )
            pix.save(img_path)
            image_paths.append(img_path)
            logger.info(f"PDF page {page_num} → {img_path}")
    finally:
        doc.close()

    return image_paths


def _convert_with_pdf2image(pdf_path: str, output_dir: str) -> List[str]:
    """Convert using pdf2image (requires poppler on system PATH)."""
    from pdf2image import convert_from_path  # type: ignore[import]

    dpi = int(settings.pdf_render_scale * 100)
    images = convert_from_path(pdf_path, dpi=dpi)
    image_paths: List[str] = []

    for i, img in enumerate(images):
        img_path = os.path.join(
            output_dir,
            f"pdf_page_{i}_{os.path.basename(pdf_path)}.png",
        )
        img.save(img_path, "PNG")
        image_paths.append(img_path)
        logger.info(f"PDF page {i} → {img_path} (via pdf2image)")

    return image_paths
