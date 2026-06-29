"""
app/infrastructure/ocr/column_detector.py
==========================================
Detect the X-positions of table columns in a report card image.

The report card table typically has columns:
  [Mata Pelajaran] [KKM] [Nilai Angka] [Predikat/Huruf]

This module detects those column headers from the OCR word rows and
returns their X-coordinates. The `score_zone_start` value derived here
is the key boundary used throughout the extraction pipeline to separate
subject-name text (left zone) from numeric values (right zone).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.utils.text_normalizer import normalize_text

logger = logging.getLogger(__name__)


def detect_column_positions(rows: List[List[Dict]]) -> Dict[str, Any]:
    """
    Detect X-coordinates of report card table column headers.

    Scans the first 35 rows (top portion of the image where headers appear)
    and matches words against known column header keywords.

    Args:
        rows: Word rows from Y-clustering (sorted top-to-bottom).

    Returns:
        Dict with keys:
          - subject_x   : X position of "Mata Pelajaran" column (or None)
          - kkm_x       : X position of "KKM" column (or None)
          - score_x     : X position of "Nilai Angka" column (or None)
          - grade_x     : X position of "Predikat" column (or None)
          - has_kkm     : True if a KKM column was detected
          - score_zone_start : computed via compute_score_zone_start()
    """
    cols: Dict[str, Any] = {
        "subject_x": None,
        "kkm_x": None,
        "score_x": None,
        "grade_x": None,
        "has_kkm": False,
        "score_zone_start": None,
    }

    # IMPORTANT: keywords must be SPECIFIC multi-word phrases or unique acronyms.
    # Single common words like 'nilai', 'pelajaran', 'kriteria' cause false positives
    # against school info headers (e.g. "Tahun Pelajaran", "Nilai Ulangan").
    header_map: Dict[str, List[str]] = {
        "subject_x": [
            "mata pelajaran", "mapel", "bidang studi",
            "muatan pelajaran", "muatan lokal",
        ],
        "kkm_x": [
            "kkm",
            "kriteria ketuntasan",
            "kriteria ketuntasan minimal",
            "standar ketuntasan",
            "standar kelulusan",
            "skbm", "skm",
            "batas lulus",
        ],
        "score_x": [
            "angka",
            "nilai angka",
            "nilai rapor",
            "nilai tulis",
            "pencapaian",
            "capaian kompetensi",
            "rata rata",
            "perolehan",
        ],
        "grade_x": ["huruf", "predikat"],
    }

    # Step 1: find subject_x to anchor the Y search window
    anchor_y: Optional[float] = None
    for row in rows[:30]:
        if not row:
            continue
        row_y = row[0]["y"]
        for word in row:
            wn = normalize_text(word["text"])
            for kw in header_map["subject_x"]:
                if kw in wn and len(wn) <= len(kw) + 20:
                    cols["subject_x"] = float(word["x"])
                    anchor_y = float(word["y"])
                    logger.info(
                        f"  📐 Col 'subject_x' @ x={word['x']:.0f}, y={anchor_y:.0f}"
                        f" ('{word['text']}')"
                    )
                    break
            if anchor_y is not None:
                break
        if anchor_y is not None:
            break

    # Step 2: find remaining columns near the anchor Y
    for row in rows[:35]:
        for word in row:
            if anchor_y is not None and abs(word["y"] - anchor_y) > 80:
                continue
            wn = normalize_text(word["text"])
            for col_key in ("kkm_x", "score_x", "grade_x"):
                if cols[col_key] is not None:
                    continue
                for kw in header_map[col_key]:
                    if kw in wn and len(wn) <= len(kw) + 15:
                        cols[col_key] = float(word["x"])
                        logger.info(
                            f"  📐 Col '{col_key}' @ x={word['x']:.0f}"
                            f" ('{word['text']}')"
                        )
                        break

    cols["has_kkm"] = cols["kkm_x"] is not None
    return cols


def compute_score_zone_start(cols: Dict[str, Any], img_width: float) -> float:
    """
    Compute the left boundary of the numeric value zone.

    Priority:
    1. KKM column detected → zone starts 50px left of KKM header
    2. Score column detected → zone starts 50px left of score header
    3. Fallback → 35% of image width (configurable via settings)

    A sanity check prevents false-positive subject_x values (> 50% width)
    from pushing the zone too far right.

    Args:
        cols:      Output of detect_column_positions()
        img_width: Total pixel width of the image

    Returns:
        X-coordinate (float) of the score zone left boundary
    """
    base: float
    if cols.get("kkm_x") is not None:
        base = cols["kkm_x"] - 50.0
    elif cols.get("score_x") is not None:
        base = cols["score_x"] - 50.0
    else:
        base = img_width * settings.score_zone_fallback_ratio

    subject_x: Optional[float] = cols.get("subject_x")
    if subject_x is not None:
        if subject_x > img_width * 0.50:
            logger.warning(
                f"  ⚠️  subject_x={subject_x:.0f} > 50% width ({img_width * 0.50:.0f})"
                f" — likely false positive, using fallback"
            )
        else:
            return max(base, subject_x + 100.0)

    return max(0.0, base)
