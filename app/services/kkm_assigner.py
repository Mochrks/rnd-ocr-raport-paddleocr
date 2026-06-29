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

    if x_spread > _KKM_INFER_X_SPREAD:
        # Wide spread → most likely an undetected KKM column
        sorted_x = sorted(candidates, key=lambda c: c["x"])
        kkm_val = sorted_x[0]["value"]
        score_val = sorted_x[-1]["value"]
        if kkm_val > score_val + 5:
            # Sanity: KKM should not exceed score significantly
            logger.debug(
                f"  [KKM-Infer] Skipped: kkm={kkm_val} > score={score_val}"
            )
            return None, score_val
        logger.debug(
            f"  [KKM-Infer] x_spread={x_spread:.0f} → KKM={kkm_val}, Score={score_val}"
        )
        return kkm_val, score_val

    # Close together → likely a split decimal; take max as score
    best = max(candidates, key=lambda c: c["value"])
    return None, best["value"]


def _assign_with_kkm_header(
    candidates: List[Dict],
    x_spread: float,
    kkm_x: Optional[float],
    score_x: Optional[float],
) -> Tuple[Optional[float], Optional[float]]:
    """Assign when a KKM column header was detected."""
    if len(candidates) == 1:
        c = candidates[0]
        if kkm_x is not None and score_x is not None:
            if abs(c["x"] - kkm_x) < abs(c["x"] - score_x):
                return c["value"], None
        return None, c["value"]

    # 2+ candidates with both column X positions known
    if kkm_x is not None and score_x is not None:
        kkm_bucket, score_bucket = [], []
        for c in candidates:
            if abs(c["x"] - kkm_x) <= abs(c["x"] - score_x):
                kkm_bucket.append(c)
            else:
                score_bucket.append(c)

        if not kkm_bucket or not score_bucket:
            return _fallback_sort_assign(candidates)

        kkm_val = sorted(kkm_bucket, key=lambda c: c["x"])[0]["value"]
        score_val = sorted(score_bucket, key=lambda c: c["x"])[-1]["value"]
        if kkm_val > score_val + 5:
            kkm_val, score_val = score_val, kkm_val
        return kkm_val, score_val

    return _fallback_sort_assign(candidates)


def _fallback_sort_assign(
    candidates: List[Dict],
) -> Tuple[Optional[float], Optional[float]]:
    """Fallback: leftmost = KKM, rightmost = Score."""
    sorted_x = sorted(candidates, key=lambda c: c["x"])
    kkm_val = sorted_x[0]["value"]
    score_val = sorted_x[-1]["value"]
    if kkm_val > score_val + 5:
        kkm_val, score_val = score_val, kkm_val
    return kkm_val, score_val
