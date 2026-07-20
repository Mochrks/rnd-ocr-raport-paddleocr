"""
app/services/ai_response_mapper.py
=====================================
Map the raw AI Vision DTO into the unified internal pipeline dict.

The unified dict is the same format produced by the PaddleOCR pipeline:
  {
    "subjects": [...],    # same shape as row_extractor output
    "personality": {...}, # same shape as mapping_engine.extract_personality()
    "attendance": {...},  # same shape as mapping_engine.extract_attendance()
  }

This mapper ensures the frontend and all downstream code are completely
unaware of which OCR engine was used.

Pipeline:
  AIVisionRawResponse
    → _map_subjects()    — fuzzy-match subject names to MASTER_SUBJECTS
    → _map_personality() — normalize personality grades
    → _map_attendance()  — normalize attendance values
    → unified dict
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.domain.ai_vision_dto import AIVisionRawResponse, AISubjectDTO
from app.domain.constants import MASTER_SUBJECTS
from app.services.mapping_engine import compute_combined_accuracy, get_best_match
from app.services.score_parser import is_valid_score, parse_score

logger = logging.getLogger(__name__)


# ── Public API ─────────────────────────────────────────────────────────────

def map_ai_response_to_pipeline_dict(
    ai_response: AIVisionRawResponse,
    engine_name: str = "AI",
) -> Dict[str, Any]:
    """
    Convert an AI Vision DTO into the unified internal pipeline dict.

    Args:
        ai_response:  Parsed and validated AIVisionRawResponse from the AI service.
        engine_name:  Name of the engine (for logging): "DeepSeek" or "Qwen".

    Returns:
        Dict: { subjects: list, personality: dict|None, attendance: dict|None }
    """
    logger.info(f"[{engine_name}] Mapping AI response → pipeline dict")

    subjects = _map_subjects(
        ai_response.mata_pelajaran or [],
        engine_name,
    )

    personality = _map_personality(ai_response.kepribadian)
    attendance = _map_attendance(ai_response.absensi)

    logger.info(
        f"[{engine_name}] Mapped: {len(subjects)} subjects | "
        f"personality={'yes' if personality else 'no'} | "
        f"attendance={'yes' if attendance else 'no'}"
    )

    return {
        "subjects": subjects,
        "personality": personality,
        "attendance": attendance,
    }


# ── Subject Mapping ────────────────────────────────────────────────────────

def _map_subjects(
    raw_subjects: List[AISubjectDTO],
    engine_name: str,
) -> List[Dict]:
    """
    Map AI-extracted subjects to MASTER_SUBJECTS via fuzzy matching.

    Handles:
    - Score normalization (str → float, 0–10 scale → 0–100)
    - Lain-Lain fallback for unmatched subjects
    - Duplicate detection via seen_ids set
    """
    results: List[Dict] = []
    seen_ids: set = set()
    lain_ids = [ms["id"] for ms in MASTER_SUBJECTS if "Lain" in ms["subject_name"]]

    for dto in raw_subjects:
        if not dto.nama:
            continue

        raw_name = dto.nama.strip()
        score_val = _safe_score(dto.nilai)
        kkm_val = _safe_score(dto.kkm)

        # Validate score
        if score_val is None:
            logger.debug(f"[{engine_name}] Skip '{raw_name}' — invalid score: {dto.nilai!r}")
            continue
        if not is_valid_score(score_val):
            logger.debug(f"[{engine_name}] Skip '{raw_name}' — score out of range: {score_val}")
            continue

        # Validate KKM
        if kkm_val is not None and not is_valid_score(kkm_val):
            kkm_val = None

        # Fuzzy match against MASTER_SUBJECTS
        match = get_best_match(
            raw_name,
            MASTER_SUBJECTS,
            threshold=settings.fuzzy_match_threshold,
        )

        if match and match["id"] not in seen_ids:
            acc = compute_combined_accuracy(
                ocr_confidence=0.95,   # AI Vision models have high confidence
                match_similarity=85.0,
                score_valid=True,
            )
            seen_ids.add(match["id"])
            results.append({
                "subjectId": match["id"],
                "subjectName": match["subject_name"],
                "originalText": raw_name,
                "category": match.get("category", "Umum"),
                "kkm": kkm_val,
                "score": float(score_val),
                "accuracy": acc,
            })
            logger.info(
                f"  [✅ {engine_name}] '{raw_name}' → {match['subject_name']} "
                f"KKM={kkm_val} Score={score_val}"
            )

        elif not match:
            # Assign to Lain-Lain slot
            available_lain = [lid for lid in lain_ids if lid not in seen_ids]
            if not available_lain:
                logger.debug(f"[{engine_name}] All Lain-Lain slots taken, skip '{raw_name}'")
                continue

            lid = available_lain[0]
            lain_ms = next(ms for ms in MASTER_SUBJECTS if ms["id"] == lid)
            acc = compute_combined_accuracy(0.95, 40.0, True)
            seen_ids.add(lid)
            results.append({
                "subjectId": lid,
                "subjectName": lain_ms["subject_name"],
                "originalText": raw_name,
                "category": lain_ms.get("category", "Umum"),
                "kkm": kkm_val,
                "score": float(score_val),
                "accuracy": acc,
            })
            logger.info(
                f"  [🔶 {engine_name}] '{raw_name}' → {lain_ms['subject_name']} (unmatched)"
            )

    return results


# ── Personality Mapping ────────────────────────────────────────────────────

def _map_personality(dto) -> Optional[Dict]:
    """
    Convert AI personality DTO to internal dict format.

    Internal format:
      { kelakuan: {grade, accuracy}, kerajinan: ..., kerapihan: ... }
    """
    if dto is None:
        return None

    def _make(raw_value: Optional[str]) -> Optional[Dict]:
        if raw_value is None:
            return None
        grade = _normalize_grade(str(raw_value).strip())
        if not grade:
            return None
        return {"grade": grade, "accuracy": 90.0}

    kelakuan = _make(dto.kelakuan)
    kerajinan = _make(dto.kerajinan)
    kerapihan = _make(dto.kerapihan)

    if kelakuan is None and kerajinan is None and kerapihan is None:
        return None

    return {
        "kelakuan": kelakuan,
        "kerajinan": kerajinan,
        "kerapihan": kerapihan,
    }


# ── Attendance Mapping ─────────────────────────────────────────────────────

def _map_attendance(dto) -> Optional[Dict]:
    """
    Convert AI attendance DTO to internal dict format.

    Internal format:
      { sakit: {value, accuracy}, ijin: ..., alpa: ... }

    Note: The AI uses 'izin' (baku) but the internal format uses 'ijin'.
    """
    if dto is None:
        return None

    def _make(raw_value: Any) -> Optional[Dict]:
        if raw_value is None:
            return None
        val = _safe_int(raw_value)
        if val is None:
            return None
        return {"value": val, "accuracy": 90.0}

    sakit = _make(dto.sakit)
    # Handle both 'izin' (AI model output) and 'ijin' (internal key)
    ijin = _make(dto.izin)
    alpa = _make(dto.alpa)

    if sakit is None and ijin is None and alpa is None:
        return None

    return {
        "sakit": sakit,
        "ijin": ijin,
        "alpa": alpa,
    }


# ── Private Helpers ────────────────────────────────────────────────────────

def _safe_score(raw: Any) -> Optional[float]:
    """
    Safely convert a raw value from AI to a float score.
    Delegates to parse_score() for all OCR-artefact handling.
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        val = float(raw)
        # Scale 0–10 to 0–100
        if 0 < val <= 10 and val != int(val):
            val = round(val * 10, 1)
        return round(val, 1) if 0 <= val <= 100 else None
    return parse_score(str(raw).strip())


def _safe_int(raw: Any) -> Optional[int]:
    """Safely convert attendance value to int (days)."""
    if raw is None:
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        return int(raw)
    s = str(raw).strip()
    # Handle dash as 0 days
    if s in ("-", "–", "—"):
        return 0
    # Extract leading digits
    m = re.match(r"^(\d+)", s)
    if m:
        return int(m.group(1))
    return None


def _normalize_grade(raw: str) -> Optional[str]:
    """
    Normalize personality grade to canonical form (A/B/C/D or descriptor).
    """
    if not raw:
        return None
    upper = raw.upper().strip()
    if upper in ("A", "B", "C", "D"):
        return upper
    lower = raw.lower().strip()
    desc_map = {
        "amat baik": "A",
        "sangat baik": "A",
        "baik sekali": "A",
        "baik": "B",
        "cukup baik": "C",
        "cukup": "C",
        "kurang": "D",
    }
    for key, grade in desc_map.items():
        if key in lower:
            return grade
    # Return as-is if it's a reasonable short string
    if len(raw) <= 20:
        return raw
    return None
