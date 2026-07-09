"""
app/infrastructure/ocr/preprocessor.py
========================================
OpenCV image preprocessing for OCR quality improvement.

Performance-optimized pipeline:
1. Downscale — images exceeding max_pixels are reduced proportionally
2. Upscaling — images narrower than max_width are scaled up for better OCR
3. Grayscale conversion
4. Fast bilateral filter denoising (replaces slow fastNlMeansDenoising)
5. CLAHE (Contrast Limited Adaptive Histogram Equalization)

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
    2. Downscale if too large (> image_max_pixels)
    3. Upscale if too narrow (< image_max_width)
    4. Convert to grayscale
    5. Optionally denoise via bilateral filter (fast, edge-preserving)
    6. Apply CLAHE contrast enhancement
    7. Convert back to BGR for PaddleOCR

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

    img = _maybe_downscale(img)
    img = _maybe_upscale(img)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    if settings.preprocessing_denoise_enabled:
        # bilateralFilter: ~50ms vs fastNlMeansDenoising ~3-8s
        # d=7: diameter of pixel neighborhood
        # sigmaColor=50: filter strength for color similarity
        # sigmaSpace=50: filter strength for coordinate space
        gray = cv2.bilateralFilter(gray, d=7, sigmaColor=50, sigmaSpace=50)

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)


def _maybe_downscale(img: np.ndarray) -> np.ndarray:
    """Downscale the image if its total pixel count exceeds the max threshold."""
    height, width = img.shape[:2]
    total_pixels = height * width
    max_pixels = settings.image_max_pixels

    if total_pixels > max_pixels:
        scale = (max_pixels / total_pixels) ** 0.5
        new_w = int(width * scale)
        new_h = int(height * scale)
        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        logger.info(f"Downscaled image: {width}x{height} → {new_w}x{new_h} ({total_pixels//1000}k → {new_w*new_h//1000}k px)")
    return img


def _maybe_upscale(img: np.ndarray) -> np.ndarray:
    """Upscale the image if its width is below the minimum threshold."""
    height, width = img.shape[:2]
    max_width = settings.image_max_width

    if width < 1000:
        scale = min(max_width / width, 2.0)  # Cap at 2x to prevent oversized images
        new_w = int(width * scale)
        new_h = int(height * scale)
        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        logger.info(f"Upscaled image: {width}x{height} → {new_w}x{new_h}")
    return img

