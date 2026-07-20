"""
app/services/kkm_assigner.py
==============================
Determine which numeric candidate is the KKM and which is the student score.

Report cards come in two layouts:
1. With KKM column — header "KKM", "Kriteria Ketuntasan", "SKBM", etc.
2. Without KKM column — only student score per row.

In both cases the OCR row may produce multiple numeric candidates from the
right (value) zone. This module assigns them using column position heuristics.

Rules (in priority order):
1. has_kkm=True + column positions known → assign by nearest X to column header
2. has_kkm=True + column positions unknown → leftmost = KKM, rightmost = Score
3. has_kkm=False + 2+ candidates with X spread > 80px → infer KKM from left
4. has_kkm=False + single candidate → no KKM, take the value as Score
5. has_kkm=False + candidates close together → take max as Score
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Threshold (pixels) to infer an implicit KKM column when no header was detected
_KKM_INFER_X_SPREAD: float = 80.0


def assign_kkm_score(
    candidates: List[Dict],   # [{'value': float, 'x': float, 'conf': float}]
    cols: Dict,
) -> Tuple[Optional[float], Optional[float]]:
    """
    Determine KKM and Score from a list of numeric candidates in an OCR row.

    Args:
        candidates: Numeric values found in the score zone, with their X positions.
        cols:       Column layout dict from column_detector.detect_column_positions().

    Returns:
        (kkm_value, score_value) — either may be None.
    """
    if not candidates:
        return None, None

    has_kkm: bool = cols.get("has_kkm", False)
    kkm_x: Optional[float] = cols.get("kkm_x")
    score_x: Optional[float] = cols.get("score_x")

    x_spread = _x_spread(candidates)

    if not has_kkm:
        return _assign_without_kkm_header(candidates, x_spread)

    return _assign_with_kkm_header(candidates, x_spread, kkm_x, score_x)


# ── Internal helpers ──────────────────────────────────────────────────────

def _x_spread(candidates: List[Dict]) -> float:
    if len(candidates) >= 2:
        xs = [c["x"] for c in candidates]
        return max(xs) - min(xs)
    return 0.0


def _assign_without_kkm_header(
    candidates: List[Dict], x_spread: float
) -> Tuple[Optional[float], Optional[float]]:
    """Assign when no KKM column header was detected."""
    if len(candidates) == 1:
        return None, candidates[0]["value"]

    # Rule 3: has_kkm=False + 2+ candidates with X spread > 80px -> infer KKM from left
    if x_spread > _KKM_INFER_X_SPREAD:
        sorted_x = sorted(candidates, key=lambda c: c["x"])
        kkm_val = sorted_x[0]["value"]
        score_val = sorted_x[-1]["value"]
        
        # Rule 5 (implicit): sanity check, KKM shouldn't exceed score + 5
        if kkm_val > score_val + 5:
            return None, score_val
            
        return kkm_val, score_val

    # Take the maximum value as the score
    best = max(candidates, key=lambda c: c["value"])
    return None, best["value"]


def _assign_with_kkm_header(
    candidates: List[Dict],
    x_spread: float,
    kkm_x: Optional[float],
    score_x: Optional[float],
) -> Tuple[Optional[float], Optional[float]]:
    """Assign when a KKM column header was detected."""
    if kkm_x is not None and score_x is not None:
        best_kkm = None
        best_score = None
        min_kkm_dist = float('inf')
        min_score_dist = float('inf')

        for c in candidates:
            dist_to_kkm = abs(c["x"] - kkm_x)
            dist_to_score = abs(c["x"] - score_x)

            if dist_to_kkm < dist_to_score:
                if dist_to_kkm < min_kkm_dist:
                    min_kkm_dist = dist_to_kkm
                    best_kkm = c
            else:
                if dist_to_score < min_score_dist:
                    min_score_dist = dist_to_score
                    best_score = c

        # Tolerance: must be within 100px of the column header to be considered part of it
        TOLERANCE = 100.0
        kkm_val = best_kkm["value"] if best_kkm and min_kkm_dist < TOLERANCE else None
        score_val = best_score["value"] if best_score and min_score_dist < TOLERANCE else None

        # Fallback if tolerance strictly failed both (rare, usually means columns are severely misaligned)
        if kkm_val is None and score_val is None:
            kkm_val = best_kkm["value"] if best_kkm else None
            score_val = best_score["value"] if best_score else None

        # Sanity check: KKM should not significantly exceed score (if both are present)
        if kkm_val is not None and score_val is not None and kkm_val > score_val + 5:
            kkm_val, score_val = score_val, kkm_val

        return kkm_val, score_val

    # If only kkm_x is known but score_x is not
    if kkm_x is not None:
        return _fallback_sort_assign_with_kkm_only(candidates, kkm_x)

    return _fallback_sort_assign(candidates)


def _fallback_sort_assign_with_kkm_only(
    candidates: List[Dict], kkm_x: float
) -> Tuple[Optional[float], Optional[float]]:
    """Assign when only KKM column header is known."""
    best_kkm = None
    min_dist = float('inf')
    for c in candidates:
        dist = abs(c["x"] - kkm_x)
        if dist < min_dist:
            min_dist = dist
            best_kkm = c

    TOLERANCE = 100.0
    kkm_val = best_kkm["value"] if best_kkm and min_dist < TOLERANCE else None

    # Remaining candidates: take the max as the score
    rem_candidates = [c for c in candidates if c != best_kkm] if kkm_val is not None else candidates
    
    score_val = None
    if rem_candidates:
        score_val = max(rem_candidates, key=lambda c: c["value"])["value"]

    if kkm_val is not None and score_val is not None and kkm_val > score_val + 5:
        kkm_val, score_val = score_val, kkm_val

    return kkm_val, score_val


def _fallback_sort_assign(
    candidates: List[Dict],
) -> Tuple[Optional[float], Optional[float]]:
    """Fallback: leftmost = KKM, rightmost = Score (only when headers are totally unknown)."""
    if len(candidates) == 1:
        return None, candidates[0]["value"]
    sorted_x = sorted(candidates, key=lambda c: c["x"])
    kkm_val = sorted_x[0]["value"]
    score_val = sorted_x[-1]["value"]
    if kkm_val > score_val + 5:
        kkm_val, score_val = score_val, kkm_val
    return kkm_val, score_val
