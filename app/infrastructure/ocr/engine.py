"""
app/infrastructure/ocr/engine.py
=================================
PaddleOCR and PPStructureV3 engine singletons.

Design:
- Both engines are module-level globals, initialised lazily on first use.
- Lazy initialization means the server starts quickly even without OCR libs
  fully warm. Use `warmup_engines()` in the FastAPI lifespan handler to
  pre-initialize them on startup.
- `_get_ocr_engine()` / `_get_table_engine()` are thread-safe enough for
  single-process uvicorn (no GIL contention during PaddleOCR init).
"""

from __future__ import annotations

import logging
from typing import Optional

from paddleocr import PaddleOCR, PPStructureV3

from app.core.config import settings

logger = logging.getLogger(__name__)

_ocr_engine: Optional[PaddleOCR] = None
_table_engine: Optional[PPStructureV3] = None


def _get_ocr_engine() -> PaddleOCR:
    """
    Return the shared PaddleOCR singleton, initialising it on first call.
    Subsequent calls return the already-warm instance immediately.
    """
    global _ocr_engine
    if _ocr_engine is None:
        logger.info("Initializing PaddleOCR engine...")
        _ocr_engine = PaddleOCR(
            lang=settings.ocr_lang,
            text_det_thresh=settings.ocr_det_thresh,
            text_det_box_thresh=settings.ocr_box_thresh,
            enable_mkldnn=settings.ocr_use_mkldnn,
            cpu_threads=settings.ocr_cpu_threads,
            # Performance: disable unnecessary models for report cards
            use_doc_orientation_classify=False,  # report cards are always upright
            use_doc_unwarping=False,             # report cards are flat scans
            use_textline_orientation=False,      # text is always horizontal
            # Limit detection resolution for faster inference
            text_det_limit_side_len=960,
        )
        logger.info(
            f"PaddleOCR engine ready | mkldnn={settings.ocr_use_mkldnn} "
            f"| threads={settings.ocr_cpu_threads}"
        )
    return _ocr_engine


def _get_table_engine() -> PPStructureV3:
    """
    Return the shared PPStructureV3 singleton, initialising it on first call.
    """
    global _table_engine
    if _table_engine is None:
        logger.info("Initializing PPStructure table engine...")
        _table_engine = PPStructureV3(
            use_table_recognition=True,
            lang=settings.ocr_lang,
            enable_mkldnn=settings.ocr_use_mkldnn,
            cpu_threads=settings.ocr_cpu_threads,
        )
        logger.info("PPStructure engine ready.")
    return _table_engine


def warmup_engines() -> None:
    """
    Pre-initialize both engines.

    Call this during the FastAPI lifespan startup event when
    `settings.ocr_warmup_on_startup` is True. This trades server boot
    time for zero first-request latency.
    """
    logger.info("Warming up OCR engines...")
    _get_ocr_engine()
    try:
        _get_table_engine()
    except Exception as exc:
        logger.warning(f"Table engine warmup failed (will retry on demand): {exc}")
    logger.info("OCR engines warmed up and ready.")
