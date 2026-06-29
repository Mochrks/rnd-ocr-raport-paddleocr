"""
app/infrastructure/ocr/result_flattener.py
============================================
Flatten the diverse PaddleOCR output formats into a uniform list of word dicts.

PaddleOCR has changed its output format across versions. This module handles all
known formats robustly so the rest of the codebase can rely on a single stable
representation:

    [
        {
            'text':  str,    # recognized text
            'x':     float,  # left edge x-coordinate
            'y':     float,  # vertical center y-coordinate
            'width': float,  # bounding box width
            'conf':  float,  # recognition confidence (0.0 – 1.0)
        },
        ...
    ]
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def flatten_ocr_result(ocr_result: Any) -> List[Dict]:
    """
    Flatten any PaddleOCR output into a list of word dicts.

    Supports:
    - Nested list format (classic PaddleOCR): [[[bbox, (text, conf)], ...]]
    - Dict format (newer paddlex/PaddleOCR 3.x): {rec_texts, rec_scores, rec_boxes}

    Args:
        ocr_result: Raw output from PaddleOCR.ocr()

    Returns:
        List of word dicts with keys: text, x, y, width, conf
    """
    if ocr_result is None:
        return []

    words: List[Dict] = []

    if isinstance(ocr_result, list):
        _flatten_list_format(ocr_result, words)
    elif isinstance(ocr_result, dict):
        _flatten_dict_format(ocr_result, words)
    else:
        logger.error(f"Unknown OCR output format: {type(ocr_result)}")

    return words


# ── Internal helpers ──────────────────────────────────────────────────────

def _parse_bbox(bbox: Any) -> Optional[Tuple[float, float, float]]:
    """
    Parse a bounding box into (x_left, y_center, width).

    Handles:
    - Polygon: [[x1,y1],[x2,y2],...]
    - Flat 4-element: [x_min, y_min, x_max, y_max]
    - 2-element fallback: [x, y]
    """
    try:
        if bbox is None:
            return None
        if hasattr(bbox, "tolist"):
            bbox = bbox.tolist()
        if not bbox:
            return None

        first = bbox[0]
        if hasattr(first, "__iter__") and not isinstance(first, str):
            # Polygon format
            pts = list(bbox)
            if len(pts) < 2:
                return None
            xs = [float(p[0]) for p in pts if len(p) >= 2]
            ys = [float(p[1]) for p in pts if len(p) >= 2]
            if not xs or not ys:
                return None
            return min(xs), (min(ys) + max(ys)) / 2, max(xs) - min(xs)

        # Flat format
        if len(bbox) < 4:
            if len(bbox) >= 2:
                return float(bbox[0]), float(bbox[1]), 50.0
            return None

        x0, y0, x2, y2 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
        return x0, (y0 + y2) / 2, max(0.0, x2 - x0)

    except Exception:
        return None


def _flatten_list_format(ocr_result: list, words: List[Dict]) -> None:
    """Handle the classic nested-list PaddleOCR output."""
    if not ocr_result:
        return

    first = ocr_result[0]

    if isinstance(first, list):
        # Format: [page_lines] where page_lines = [[bbox, (text, conf)], ...]
        page = first
        for line in page:
            try:
                if not line or not isinstance(line, (list, tuple)) or len(line) < 2:
                    continue
                bbox_data, text_data = line[0], line[1]
                coords = _parse_bbox(bbox_data)
                if coords is None:
                    continue
                x, y, w = coords

                if isinstance(text_data, (list, tuple)) and len(text_data) >= 2:
                    text_str = str(text_data[0])
                    conf = float(text_data[1])
                elif isinstance(text_data, str):
                    text_str = text_data
                    conf = 0.5
                else:
                    continue

                words.append({"text": text_str, "x": x, "y": y, "width": w, "conf": conf})
            except Exception as exc:
                logger.debug(f"Skip OCR line (list format): {exc}")

    elif isinstance(first, dict):
        # Format: [{rec_texts, rec_scores, rec_boxes}, ...]
        _flatten_dict_format(first, words)


def _flatten_dict_format(result: dict, words: List[Dict]) -> None:
    """Handle the newer paddlex / PaddleOCR 3.x dict output."""
    texts = result.get("rec_texts", [])
    scores = result.get("rec_scores", [])
    boxes = result.get("rec_boxes", result.get("dt_polys", []))

    has_boxes = False
    if boxes is not None:
        try:
            has_boxes = len(boxes) > 0
        except Exception:
            has_boxes = True

    n = (
        min(len(texts), len(scores), len(boxes))
        if has_boxes
        else min(len(texts), len(scores))
    )

    for i in range(n):
        try:
            if has_boxes and i < len(boxes):
                coords = _parse_bbox(boxes[i])
            else:
                coords = (i * 100.0, 0.0, 100.0)
            if coords is None:
                continue
            x, y, w = coords
            words.append(
                {
                    "text": str(texts[i]),
                    "x": x,
                    "y": y,
                    "width": w,
                    "conf": float(scores[i]),
                }
            )
        except Exception as exc:
            logger.debug(f"Skip OCR entry {i} (dict format): {exc}")
