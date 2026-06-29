"""
app/services/score_parser.py
==============================
Parse numeric score and KKM values from raw OCR text.

Design:
- Pure functions — no I/O, no external dependencies beyond stdlib.
- The OCR engine often misreads digits as letters (L→6, O→0) or produces
  Indonesian decimal notation (8,60 instead of 86.0). This module handles
  all known OCR artefacts while rejecting invalid values (> 100, dates, etc.).
- Easy to unit-test in isolation (no PaddleOCR required).
"""

from __future__ import annotations

import re
from typing import Optional

# ── OCR letter-to-digit substitution map ─────────────────────────────────
# Applied ONLY when the text matches a known mixed letter+digit pattern.
_OCR_FIXES: dict[str, str] = {
    "L": "6", "l": "6",
    "I": "1",
    "O": "0",
    "S": "5", "s": "5",
    "Z": "2", "z": "2",
    "B": "8",
}

# Precompiled patterns for performance
_PATTERN_7O = re.compile(r"(\d)[oO]")          # "7o" / "7O" → "70"
_PATTERN_LEAD_LETTER_DIGIT = re.compile(r"^[A-Za-z]\d+$")
_PATTERN_TRAIL_DIGIT_LETTER = re.compile(r"^\d+[A-Za-z]$")
_PATTERN_PURE_NUMERIC = re.compile(r"^\d+\.?\d*$")
_PATTERN_DECIMAL_X_YZ = re.compile(r"^\d\.\d{2}$")  # "8.60" style


def parse_score(text: str) -> Optional[float]:
    """
    Parse a score or KKM value from a raw OCR text token.

    Valid output range: 0–100 (inclusive).

    Handles common OCR artefacts:
    - "8,60"  → 86.0   (Indonesian decimal comma)
    - "7o"    → 70.0   (letter O misread as digit 0)
    - "L9"    → 69.0   (letter L misread as digit 6)
    - "750"   → 75.0   (missed decimal point)
    - "7.5"   → 75.0   (scale from 0–10 to 0–100)
    - "101"   → None   (out of range, rejected)
    - "1/2"   → None   (contains slash, likely a date)

    Args:
        text: A single OCR word / cell value.

    Returns:
        Float score in range [0, 100], or None if the text is not a valid score.
    """
    if not text:
        return None
    text = text.strip()

    # Reject obvious non-scores early
    if len(text) > 6:
        return None
    if "/" in text or ".." in text or ":" in text:
        return None

    # Fix "7o" / "7O" → "70"
    text = _PATTERN_7O.sub(r"\g<1>0", text)

    # Fix single leading/trailing letter in a digit string (e.g. "L9", "7B")
    if _PATTERN_LEAD_LETTER_DIGIT.match(text) or _PATTERN_TRAIL_DIGIT_LETTER.match(text):
        text = "".join(_OCR_FIXES.get(ch, ch) for ch in text)

    # Normalize decimal separator
    text = text.replace(",", ".")
    # Remove noise character
    text = text.replace("#", "")

    if not _PATTERN_PURE_NUMERIC.match(text):
        return None

    try:
        value = float(text)
    except ValueError:
        return None

    # "8.60" style Indonesian decimal → multiply by 10
    if _PATTERN_DECIMAL_X_YZ.match(text):
        candidate = round(value * 10, 1)
        if 0 <= candidate <= 100:
            value = candidate

    # "750" style missed decimal → divide by 10
    if 100 < value <= 999 and value == int(value):
        candidate = round(value / 10, 1)
        if 10 <= candidate <= 100 and len(str(int(value))) == 3:
            value = candidate

    # Scale 0–10 decimals to 0–100
    if 0 < value < 10 and value != int(value):
        value = round(value * 10, 1)

    return round(value, 1) if 0 <= value <= 100 else None


def is_valid_score(value: float) -> bool:
    """
    Return True if value is a valid score in the range [0, 100].

    Args:
        value: A numeric value to validate.
    """
    return isinstance(value, (int, float)) and 0 <= value <= 100
