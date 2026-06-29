"""
app/services/table_extractor.py
================================
Extract subjects from the report card using PPStructure table recognition.

This is Mode 1 — it attempts to parse the report card as a structured HTML
table, which is more accurate when the table borders are clear (digital PDFs).

Pipeline:
  raw image + preprocessed image → PPStructureV3 → HTML → pandas DataFrames
  → filter rows → fuzzy match subjects → return subject list
"""

from __future__ import annotations

import logging
import re
from io import StringIO
from typing import Dict, List

import cv2
import pandas as pd

from app.infrastructure.ocr.engine import _get_table_engine
from app.infrastructure.ocr.preprocessor import preprocess_image
from app.services.mapping_engine import compute_combined_accuracy, get_best_match
from app.services.score_parser import is_valid_score, parse_score
from app.utils.text_normalizer import normalize_text

logger = logging.getLogger(__name__)

# Shared skip set — same logic as row_extractor but owned here for table mode
_SKIP_KEYWORDS = frozenset([
    "jumlah", "rata", "kkm", "predikat", "kelompok", "no", "mata pelajaran",
    "nilai", "huruf", "angka", "muatan", "kompetensi", "normatif", "adaptif",
    "produktif", "capaian", "kriteria", "ketuntasan", "peringkat", "sakit",
    "izin", "semester", "kelas", "nama", "nisn", "nis", "tahun", "pelajaran",
    "mengetahui", "kepala", "wali", "nip", "skbm", "pengetahuan", "keterampilan",
])

_INDONESIAN_NUMBERS = frozenset([
    "satu", "dua", "tiga", "empat", "lima", "enam", "tujuh", "delapan",
    "sembilan", "sepuluh", "sebelas", "belas", "puluh", "ratus", "nol",
    "koma", "kosong",
])

_SUBITEM_PREFIX_RE = re.compile(r"^(?:\d+\.\d+|[a-eA-E]\.\s)")
_DIGIT_CLEAN_RE = re.compile(r"[\d,.\-]")


def extract_via_table_structure(
    image_path: str, master_subjects: List[Dict]
) -> List[Dict]:
    """
    Attempt OCR extraction via PPStructure table recognition.

    Tries both the raw and preprocessed versions of the image. Uses whichever
    yields results first. Falls back gracefully to an empty list on any error.

    Args:
        image_path:      Path to the image file.
        master_subjects: MASTER_SUBJECTS list from domain.constants.

    Returns:
        List of subject dicts. Empty list if no table found or parsing fails.
    """
    engine = _get_table_engine()
    raw_img = cv2.imread(image_path)
    if raw_img is None:
        logger.warning(f"Table mode: cannot read image '{image_path}'")
        return []

    preprocessed = preprocess_image(image_path)
    results: List[Dict] = []
    seen: set = set()

    for attempt_img, label in [(raw_img, "raw"), (preprocessed, "preprocessed")]:
        try:
            for block in engine(attempt_img):
                if block.get("type") != "table":
                    continue
                html = block.get("res", {}).get("html", "")
                if not html:
                    continue
                logger.info(f"PPStructure [{label}]: table HTML = {len(html)} chars")
                try:
                    dfs = pd.read_html(StringIO(html))
                except Exception as exc:
                    logger.warning(f"pd.read_html failed [{label}]: {exc}")
                    continue
                for df in dfs:
                    _extract_from_dataframe(df, master_subjects, results, seen)
            if results:
                break
        except Exception as exc:
            logger.warning(f"PPStructure [{label}] error: {exc}")

    logger.info(f"Table mode: {len(results)} subjects found")
    return results


# ── Internal helpers ──────────────────────────────────────────────────────

def _extract_from_dataframe(
    df: pd.DataFrame,
    master_subjects: List[Dict],
    results: List[Dict],
    seen: set,
) -> None:
    """Parse one HTML table DataFrame and append matched subjects to results."""
    for _, row in df.iterrows():
        cells = [
            str(v).strip()
            for v in row.values
            if pd.notna(v) and str(v).strip()
        ]
        if not cells:
            continue

        text_parts: List[str] = []
        nums: List[float] = []

        for cell in cells:
            score_val = parse_score(cell)
            if score_val is not None and score_val >= 10:
                nums.append(score_val)
            else:
                cleaned = _DIGIT_CLEAN_RE.sub(" ", cell).strip()
                if cleaned and re.search(r"[A-Za-z]", cleaned):
                    parts = [
                        p for p in cleaned.split()
                        if p.lower() not in _INDONESIAN_NUMBERS
                    ]
                    if parts:
                        text_parts.append(" ".join(parts))

        if not text_parts or not nums:
            continue

        name = " ".join(text_parts)
        norm = normalize_text(name)
        words = set(re.findall(r"\w+", norm))

        if all(w in _SKIP_KEYWORDS for w in words) or len(name) < 3:
            continue
        if _SUBITEM_PREFIX_RE.match(name):
            continue

        match = get_best_match(name, master_subjects, threshold=60)

        if match and match["id"] not in seen:
            valid = [s for s in nums if is_valid_score(s)]
            if not valid:
                continue
            kkm = float(valid[0]) if len(valid) >= 2 else None
            score = float(valid[1]) if len(valid) >= 2 else float(valid[0])
            seen.add(match["id"])
            results.append({
                "subjectId": match["id"],
                "subjectName": match["subject_name"],
                "originalText": name,
                "category": match.get("category", "Umum"),
                "kkm": kkm,
                "score": score,
                "accuracy": compute_combined_accuracy(0.9, 85.0, True),
            })
            logger.info(
                f"  ✅ [Table] '{name}' → {match['subject_name']} "
                f"KKM={kkm} Score={score}"
            )

        elif not match:
            lain_ids = [ms["id"] for ms in master_subjects if "Lain" in ms["subject_name"]]
            available = [lid for lid in lain_ids if lid not in seen]
            if not available:
                continue
            lid = available[0]
            lain_ms = next(ms for ms in master_subjects if ms["id"] == lid)
            valid = [s for s in nums if is_valid_score(s)]
            if not valid:
                continue
            kkm = float(valid[0]) if len(valid) >= 2 else None
            score = float(valid[1]) if len(valid) >= 2 else float(valid[0])
            seen.add(lid)
            results.append({
                "subjectId": lid,
                "subjectName": lain_ms["subject_name"],
                "originalText": name,
                "category": lain_ms.get("category", "Umum"),
                "kkm": kkm,
                "score": score,
                "accuracy": compute_combined_accuracy(0.9, 40.0, True),
            })
            logger.info(
                f"  🔶 [Table] '{name}' → {lain_ms['subject_name']} (unmatched)"
            )
