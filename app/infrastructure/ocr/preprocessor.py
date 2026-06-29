"""
app/infrastructure/ocr/preprocessor.py
========================================
OpenCV image preprocessing for OCR quality improvement.

Applies:
1. Upscaling — images narrower than 1000px are scaled up for better OCR
2. Grayscale conversion
3. CLAHE (Contrast Limited Adaptive Histogram Equalization)
4. Optional fast denoising — disable for high-quality digital PDFs via config

The preprocessed image is returned as a BGR numpy array ready for PaddleOCR.
"""

from __future__ import annotations

import logging

import cv2
import numpy as np

from app.core.config import settings
from app.core.exceptions import ImageReadError

logger = logging.getLogger(__name__)


def preprocess_image(image_path: str) -> np.ndarray:
    """
    Load and preprocess an image file for OCR.

    Steps:
    1. Read from disk
    2. Upscale if too narrow (< 1000px wide)
    3. Convert to grayscale
    4. Optionally denoise (controlled by settings.preprocessing_denoise_enabled)
    5. Apply CLAHE contrast enhancement
    6. Convert back to BGR for PaddleOCR

    Args:
        image_path: Absolute or relative path to the image file.

    Returns:
        Preprocessed BGR numpy array.

    Raises:
        ImageReadError: If OpenCV cannot read the file.
    """
    img = cv2.imread(image_path)
    if img is None:
        raise ImageReadError(image_path)

    img = _maybe_upscale(img)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    if settings.preprocessing_denoise_enabled:
        gray = cv2.fastNlMeansDenoising(
            gray, h=10, templateWindowSize=7, searchWindowSize=21
        )

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)


def _maybe_upscale(img: np.ndarray) -> np.ndarray:
    """Upscale the image if its width is below the minimum threshold."""
    height, width = img.shape[:2]
    if width < 1000:
        scale = 1500 / width
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        new_h, new_w = img.shape[:2]
        logger.info(f"Upscaled image: {width}x{height} → {new_w}x{new_h}")
    return img
