"""
app/services/ocr_orchestrator.py
==================================
Slim orchestrator that coordinates the two OCR extraction modes.

Responsibilities (and nothing more):
- Decide whether to process a PDF or a single image
- Run Mode 1 (Table) and Mode 2 (Raw OCR)
- Select the better result
- Provide the debug helper

All heavy lifting is delegated to:
  - infrastructure/ocr/         (engine, preprocessing, PDF conversion)
  - services/table_extractor    (Mode 1)
  - services/row_extractor      (Mode 2)
"""

from __future__ import annotations

import logging
import os
import tempfile
from typing import Any, Dict, List

from app.infrastructure.ocr.column_detector import (
    compute_score_zone_start,
    detect_column_positions,
)
from app.infrastructure.ocr.engine import _get_ocr_engine
from app.infrastructure.ocr.pdf_converter import convert_pdf_to_images
from app.infrastructure.ocr.preprocessor import preprocess_image
from app.infrastructure.ocr.result_flattener import flatten_ocr_result
from app.services.row_extractor import cluster_words_by_y, extract_via_raw_ocr
from app.services.score_parser import parse_score
from app.services.table_extractor import extract_via_table_structure

logger = logging.getLogger(__name__)


# ── Backward-compatible thin wrapper ─────────────────────────────────────

def perform_ocr_and_extract(image_path: str, master_subjects: List[Dict]) -> List[Dict]:
    """Backward-compatible wrapper — returns subjects list only."""
    return perform_ocr_and_extract_full(image_path, master_subjects).get("subjects", [])


# ── Main orchestrator ─────────────────────────────────────────────────────

def perform_ocr_and_extract_full(
    image_path: str, master_subjects: List[Dict]
) -> Dict:
    """
    Run the complete OCR pipeline on a single image or PDF.

    Strategy:
    1. If PDF → convert pages to images, process each, merge results.
    2. For each image:
       a. Mode 1: PPStructure table recognition (more accurate for digital PDFs)
       b. Mode 2: Raw OCR + Y-clustering (fallback for scanned/handwritten)
       c. Use whichever mode returns more subjects (≥ 3 to prefer Mode 1)

    Args:
        image_path:      Path to the uploaded image or PDF file.
        master_subjects: MASTER_SUBJECTS list.

    Returns:
        Dict: { subjects, personality, attendance }
    """
    logger.info(f"=== OCR start: {image_path} ===")

    if image_path.lower().endswith(".pdf"):
        return _process_pdf(image_path, master_subjects)

    return _process_single_image(image_path, master_subjects)


def _process_pdf(pdf_path: str, master_subjects: List[Dict]) -> Dict:
    """Process a PDF by converting pages to images and merging results."""
    import time as _time

    all_subjects: List[Dict] = []
    personality = None
    attendance = None
    seen_ids: set = set()

    t0 = _time.perf_counter()

    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            image_paths = convert_pdf_to_images(pdf_path, output_dir=tmp_dir)
        except Exception as exc:
            logger.error(f"PDF conversion failed: {exc}")
            return {"subjects": [], "personality": None, "attendance": None}

        if not image_paths:
            logger.error("No images extracted from PDF")
            return {"subjects": [], "personality": None, "attendance": None}

        t1 = _time.perf_counter()
        logger.info(f"  ⏱ PDF → {len(image_paths)} pages in {t1 - t0:.2f}s")

        # Process pages sequentially. 
        # (PaddlePaddle C++ inference is not thread-safe for a singleton engine)
        for idx, img_path in enumerate(image_paths):
            try:
                result = _process_single_image(img_path, master_subjects)
                for subj in result.get("subjects", []):
                    if subj["subjectId"] not in seen_ids:
                        seen_ids.add(subj["subjectId"])
                        all_subjects.append(subj)
                if personality is None and result.get("personality"):
                    personality = result["personality"]
                if attendance is None and result.get("attendance"):
                    attendance = result["attendance"]
            except Exception as exc:
                logger.warning(f"Error processing PDF page {idx}: {exc}")

    t2 = _time.perf_counter()
    logger.info(f"  ⏱ PDF total: {t2 - t0:.2f}s ({len(image_paths)} pages)")

    return {"subjects": all_subjects, "personality": personality, "attendance": attendance}


def _process_single_image(image_path: str, master_subjects: List[Dict]) -> Dict:
    """Run extraction modes (Raw OCR first, fallback to Table)."""
    # Mode 2: Raw OCR (Fast and accurate)
    raw_result: Dict = {"subjects": [], "personality": None, "attendance": None}
    try:
        raw_result = extract_via_raw_ocr(image_path, master_subjects)
        logger.info(f"Mode 2 (Raw): {len(raw_result.get('subjects', []))} subjects")
    except Exception as exc:
        logger.warning(f"Mode 2 failed: {exc}")

    raw_subjects = raw_result.get("subjects", [])

    # If Raw OCR succeeded, return immediately
    if len(raw_subjects) >= 3:
        logger.info(f"=== Using Raw results ({len(raw_subjects)} subjects) ===")
        return raw_result

    # Mode 1: Table structure (Slow fallback)
    table_subjects: List[Dict] = []
    try:
        logger.info("Raw OCR found < 3 subjects, falling back to Mode 1 (Table)...")
        table_subjects = extract_via_table_structure(image_path, master_subjects)
        logger.info(f"Mode 1 (Table): {len(table_subjects)} subjects")
    except Exception as exc:
        logger.warning(f"Mode 1 failed: {exc}")

    if len(table_subjects) >= len(raw_subjects) and len(table_subjects) >= 3:
        logger.info(f"=== Using Table results ({len(table_subjects)} subjects) ===")
        return {
            "subjects": table_subjects,
            "personality": raw_result.get("personality"),
            "attendance": raw_result.get("attendance"),
        }

    if raw_subjects:
        logger.info(f"=== Using Raw results ({len(raw_subjects)} subjects) ===")
        return raw_result

    logger.warning("=== Both modes returned 0 subjects ===")
    return {
        "subjects": table_subjects or [],
        "personality": raw_result.get("personality"),
        "attendance": raw_result.get("attendance"),
    }


# ── Debug helper ──────────────────────────────────────────────────────────

def debug_ocr_raw_text(image_path: str) -> Dict[str, Any]:
    """
    Return raw OCR detections, Y-clustered rows, and detected column layout.
    Used by the GET /report/{documentId}/debug endpoint.
    """
    try:
        engine = _get_ocr_engine()
        preprocessed = preprocess_image(image_path)
        result = engine.ocr(preprocessed)

        if not result or (isinstance(result, list) and (not result[0] or result[0] is None)):
            return {"raw_text": "", "total_detections": 0, "rows": []}

        words = flatten_ocr_result(result)
        if not words:
            return {"raw_text": "", "total_detections": 0, "rows": []}

        words.sort(key=lambda w: (w["y"], w["x"]))
        img_width = max((w["x"] + w["width"] for w in words), default=1000.0)

        rows = cluster_words_by_y(words, tolerance=20)
        cols = detect_column_positions(rows)
        score_zone = compute_score_zone_start(cols, img_width)

        detections = [
            {
                "text": w["text"],
                "x_pos": round(w["x"]),
                "y_pos": round(w["y"]),
                "confidence": round(w["conf"], 3),
                "is_number": parse_score(w["text"]) is not None,
                "number_value": parse_score(w["text"]),
                "in_score_zone": w["x"] >= score_zone,
            }
            for w in words
        ]

        row_details = [
            {
                "row_index": i,
                "full_text": " ".join(w["text"] for w in row),
                "words": [
                    {"text": w["text"], "x": round(w["x"]), "conf": round(w["conf"], 3)}
                    for w in row
                ],
            }
            for i, row in enumerate(rows)
        ]

        return {
            "raw_text": "\n".join(w["text"] for w in words),
            "total_detections": len(detections),
            "total_rows": len(rows),
            "img_width": round(img_width),
            "score_zone_start": round(score_zone),
            "detected_columns": cols,
            "detections": detections,
            "rows": row_details,
        }
    except Exception as exc:
        logger.error(f"Debug OCR error: {exc}", exc_info=True)
        return {"error": str(exc)}
