"""
app/services/row_extractor.py
==============================
Extract subjects, personality and attendance from raw OCR word lists.

Pipeline:
  raw words → Y-cluster into rows → detect multi-line subjects and merge
  → extract subjects → extract personality → extract attendance

This module handles Mode 2 (Raw OCR) extraction. It is called when
PPStructure (Mode 1 / Table mode) returns too few results.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.infrastructure.ocr.column_detector import (
    compute_score_zone_start,
    detect_column_positions,
)
from app.infrastructure.ocr.engine import _get_ocr_engine
from app.infrastructure.ocr.preprocessor import preprocess_image
from app.infrastructure.ocr.result_flattener import flatten_ocr_result
from app.services.kkm_assigner import assign_kkm_score
from app.services.mapping_engine import (
    compute_combined_accuracy,
    extract_attendance,
    extract_personality,
    get_best_match,
)
from app.services.score_parser import is_valid_score, parse_score
from app.utils.text_normalizer import normalize_text

logger = logging.getLogger(__name__)


# ── Keyword sets (module-level constants for performance) ─────────────────

_SKIP_KEYWORDS = frozenset([
    "jumlah", "rata", "kkm", "predikat", "kelompok", "deskripsi",
    "no", "mata pelajaran", "nilai", "huruf", "angka", "keterangan",
    "muatan", "kompetensi", "normatif", "adaptif",
    "capaian", "kriteria", "ketuntasan", "minimum", "peringkat",
    "sakit", "izin", "ijin", "tanpa", "kegiatan", "jenis", "semester",
    "kelas", "nama", "nisn", "nis", "tahun", "pelajaran", "program",
    "mengetahui", "kepala", "wali", "nip", "tabel", "total",
    "menunjukkan", "penguasaan",
    "kelakuan", "kerajinan", "kerapihan", "kepribadian", "sikap",
    "absensi", "absen", "kehadiran",
    "skbm", "ppk", "pra", "ktek",
    "diperoleh", "pada", "format",
])

_SUBITEM_KEYWORDS = frozenset([
    "melakukan", "instalasi", "mendiagnosis", "menguasai", "membuat",
    "jaringan", "berbasis", "interface", "perangkat",
    "graphical", "command", "gui", "cli", "wan",
    "penerapan", "konsep", "akuntansi", "komputerisasi",
    "keamanan", "operasi", "kejuruan",
    "akidah", "akhlak", "fikih", "fiqih",
    "sejarah kebudayaan", "al qur", "aqidah",
])

_INDONESIAN_NUMBERS = frozenset([
    "satu", "dua", "tiga", "empat", "lima", "enam", "tujuh",
    "delapan", "sembilan", "sepuluh", "sebelas", "belas", "puluh",
    "ratus", "nol", "koma", "kosong",
])

_SECTION_HEADERS = [
    "normatif", "adaptif", "produktif", "muatan lokal",
    "kompetensi kejuruan", "kompetensi keahlian",
    "kelompok a", "kelompok b", "kelompok c",
]

# Precompiled patterns
_SUBITEM_PREFIX_RE = re.compile(
    r"^(?:\d+\.\d+|[a-eA-E]\.\s)"
)
_CLEAN_WORD_RE = re.compile(r"[|{}\[\]()_\d,.]")
_CAMEL_SPLIT_RE = re.compile(r"([a-z])([A-Z])")
_MULTI_SPACE_RE = re.compile(r"\s+")
_WORD_RE = re.compile(r"\w+")


# ── Public API ────────────────────────────────────────────────────────────

def extract_via_raw_ocr(image_path: str, master_subjects: List[Dict]) -> Dict:
    """
    Run PaddleOCR on the image and extract subjects, personality, attendance.

    This is Mode 2 (Raw OCR + Y-clustering). It is the fallback when
    PPStructure table mode returns fewer than 3 subjects.

    Args:
        image_path:      Path to the image file (already on disk).
        master_subjects: List of master subject dicts from domain.constants.

    Returns:
        Dict with keys: subjects (list), personality (dict|None), attendance (dict|None)
    """
    engine = _get_ocr_engine()
    preprocessed = preprocess_image(image_path)

    try:
        result = engine.ocr(preprocessed)
    except Exception as exc:
        logger.error(f"PaddleOCR.ocr() error: {exc}", exc_info=True)
        return {"subjects": [], "personality": None, "attendance": None}

    if not result or (isinstance(result, list) and (not result[0] or result[0] is None)):
        logger.warning("PaddleOCR returned no results")
        return {"subjects": [], "personality": None, "attendance": None}

    words = flatten_ocr_result(result)
    if not words:
        logger.warning("No words after flattening OCR result")
        return {"subjects": [], "personality": None, "attendance": None}

    words.sort(key=lambda w: (w["y"], w["x"]))
    img_width = max(w["x"] + w["width"] for w in words)

    rows = cluster_words_by_y(words, tolerance=settings.y_cluster_tolerance)
    logger.info(f"Raw OCR: {len(words)} words → {len(rows)} rows | width={img_width:.0f}")

    cols = detect_column_positions(rows)
    score_zone_start = compute_score_zone_start(cols, img_width)
    logger.info(f"  score_zone_start={score_zone_start:.0f} | has_kkm={cols['has_kkm']}")

    rows = merge_multiline_subject_rows(rows, score_zone_start)

    subjects = extract_subjects_from_rows(rows, master_subjects, cols, score_zone_start, img_width)
    personality = extract_personality(rows, score_zone_start)
    attendance = extract_attendance(rows, score_zone_start)

    logger.info(
        f"Raw mode: {len(subjects)} subjects | "
        f"personality={'yes' if personality else 'no'} | "
        f"attendance={'yes' if attendance else 'no'}"
    )
    return {"subjects": subjects, "personality": personality, "attendance": attendance}


# ── Y-Clustering ──────────────────────────────────────────────────────────

def cluster_words_by_y(
    words: List[Dict], tolerance: int = 20
) -> List[List[Dict]]:
    """
    Group OCR words into horizontal rows based on Y-coordinate proximity.

    Args:
        words:     Sorted list of word dicts (must be pre-sorted by y, x).
        tolerance: Maximum Y distance (px) between words on the same row.

    Returns:
        List of rows, each row is a list of word dicts sorted by X.
    """
    if not words:
        return []

    rows: List[List[Dict]] = []
    current: List[Dict] = [words[0]]

    for word in words[1:]:
        avg_y = sum(w["y"] for w in current) / len(current)
        if abs(word["y"] - avg_y) <= tolerance:
            current.append(word)
        else:
            rows.append(sorted(current, key=lambda w: w["x"]))
            current = [word]

    rows.append(sorted(current, key=lambda w: w["x"]))
    return rows


# ── Multi-line Subject Merging ────────────────────────────────────────────

def merge_multiline_subject_rows(
    rows: List[List[Dict]], score_zone_start: float
) -> List[List[Dict]]:
    """
    Merge two-line subject entries where the name and value are on separate rows.

    Some report card formats put a long subject name on one line and the
    numeric value on the next. This function detects and combines them.

    A "text-only" row (no number in value zone) followed immediately by a
    "number-only" row is merged into one combined row.

    Section headers (Normatif, Adaptif, etc.) are never merged.
    """
    merged: List[List[Dict]] = []
    pending: Optional[List[Dict]] = None

    for row in rows:
        text_full = " ".join(w["text"] for w in row).lower()
        is_header = any(kw in text_full for kw in _SECTION_HEADERS)

        has_score = any(
            parse_score(w["text"].replace("#", "")) is not None
            and w["x"] >= score_zone_start
            for w in row
        )
        has_text_on_left = any(
            bool(_CLEAN_WORD_RE.sub(" ", w["text"]).strip())
            and re.search(r"[A-Za-z]", w["text"])
            and w["x"] < score_zone_start
            for w in row
        )

        if has_text_on_left and not has_score and not is_header:
            pending = row
        elif pending is not None and has_score:
            merged.append(pending + row)
            pending = None
        else:
            if pending:
                merged.append(pending)
                pending = None
            merged.append(row)

    if pending:
        merged.append(pending)

    return merged


# ── Subject Extraction ────────────────────────────────────────────────────

def extract_subjects_from_rows(
    rows: List[List[Dict]],
    master_subjects: List[Dict],
    cols: Dict,
    score_zone_start: float,
    img_width: float,
) -> List[Dict]:
    """
    Extract matched subject records from clustered OCR rows.

    For each row:
    1. Split words into text candidates (left zone) and numeric candidates (right zone)
    2. Skip rows that match known non-subject patterns
    3. Fuzzy-match the text candidate against MASTER_SUBJECTS
    4. Assign KKM and score using kkm_assigner
    5. Return a list of matched subject records

    Args:
        rows:             Y-clustered word rows.
        master_subjects:  MASTER_SUBJECTS list.
        cols:             Column layout from detect_column_positions().
        score_zone_start: Left boundary of the numeric value zone.
        img_width:        Image pixel width (used for fallback calculations).

    Returns:
        List of subject dicts with keys: subjectId, subjectName, originalText,
        category, kkm, score, accuracy.
    """
    results: List[Dict] = []
    seen_ids: set = set()

    for row in rows:
        text_parts: List[str] = []
        num_cands: List[Dict] = []
        confs: List[float] = []
        row_full = " ".join(w["text"] for w in row)

        for word in row:
            raw_word = word["text"].strip()
            x_pos = word["x"]
            confs.append(word["conf"])

            # Try to parse as a number
            cleaned_num = raw_word.replace("#", "").replace(" ", "")
            val = parse_score(cleaned_num)

            if val is not None:
                if x_pos >= score_zone_start:
                    num_cands.append({"value": val, "x": x_pos, "conf": word["conf"]})
                continue  # Numbers in left zone are row numbers — skip as text

            if x_pos >= score_zone_start:
                continue  # Text in right zone (predikat column) — skip

            # Clean word for subject name
            cleaned = _CLEAN_WORD_RE.sub(" ", raw_word)
            cleaned = _CAMEL_SPLIT_RE.sub(r"\1 \2", cleaned)
            cleaned = _MULTI_SPACE_RE.sub(" ", cleaned).strip()

            if cleaned and re.search(r"[A-Za-z]", cleaned):
                for part in cleaned.split():
                    if len(part) == 1 and part.upper() in "ABCDT":
                        continue
                    if len(part) < 2:
                        continue
                    if part.lower() in _INDONESIAN_NUMBERS:
                        continue
                    text_parts.append(part)

        candidate = " ".join(text_parts).strip()

        if not candidate or not num_cands:
            continue

        # Skip known non-subject rows
        cand_norm = normalize_text(candidate)
        cand_words = set(_WORD_RE.findall(cand_norm))
        if all(w in _SKIP_KEYWORDS for w in cand_words):
            continue
        if len(candidate) < 3:
            continue
        if _SUBITEM_PREFIX_RE.match(candidate):
            logger.info(f"  ⏭ sub-item prefix skip: '{candidate}'")
            continue
        if any(kw in cand_norm for kw in _SUBITEM_KEYWORDS):
            logger.info(f"  ⏭ subitem keyword skip: '{candidate}'")
            continue

        # Keep only valid scores
        valid_nums = [c for c in num_cands if is_valid_score(c["value"])]
        if not valid_nums:
            continue

        # Scale 0–15 scores to 0–100 (likely 0–10 scale)
        if all(c["value"] <= 15 for c in valid_nums):
            valid_nums = [{**c, "value": round(c["value"] * 10, 1)} for c in valid_nums]

        kkm_val, score_val = assign_kkm_score(valid_nums, cols)
        if score_val is None or not is_valid_score(score_val):
            continue
        if kkm_val is not None and not is_valid_score(kkm_val):
            kkm_val = None

        avg_conf = sum(confs) / len(confs) if confs else 0.0
        match = get_best_match(candidate, master_subjects, threshold=settings.fuzzy_match_threshold)

        if match and match["id"] not in seen_ids:
            acc = compute_combined_accuracy(avg_conf, 85.0, True)
            seen_ids.add(match["id"])
            results.append(_build_subject_record(match, candidate, kkm_val, score_val, acc))
            logger.info(
                f"  ✅ '{candidate}' → {match['subject_name']} "
                f"KKM={kkm_val} Score={score_val}"
            )

        elif not match:
            lain_record = _assign_to_lain_lain(
                candidate, master_subjects, seen_ids, avg_conf, kkm_val, score_val
            )
            if lain_record:
                seen_ids.add(lain_record["subjectId"])
                results.append(lain_record)

    return results


# ── Private helpers ───────────────────────────────────────────────────────

def _build_subject_record(
    match: Dict,
    original_text: str,
    kkm_val: Optional[float],
    score_val: float,
    accuracy: float,
) -> Dict:
    return {
        "subjectId": match["id"],
        "subjectName": match["subject_name"],
        "originalText": original_text,
        "category": match.get("category", "Umum"),
        "kkm": kkm_val,
        "score": float(score_val),
        "accuracy": accuracy,
    }


def _assign_to_lain_lain(
    candidate: str,
    master_subjects: List[Dict],
    seen_ids: set,
    avg_conf: float,
    kkm_val: Optional[float],
    score_val: float,
) -> Optional[Dict]:
    """Assign an unmatched subject to the next available Lain-Lain slot."""
    lain_ids = [ms["id"] for ms in master_subjects if "Lain" in ms["subject_name"]]
    available = [lid for lid in lain_ids if lid not in seen_ids]
    if not available:
        return None

    lid = available[0]
    lain_ms = next(ms for ms in master_subjects if ms["id"] == lid)
    acc = compute_combined_accuracy(avg_conf, 40.0, True)

    logger.info(
        f"  🔶 '{candidate}' → {lain_ms['subject_name']} (unmatched) "
        f"KKM={kkm_val} Score={score_val}"
    )
    return {
        "subjectId": lid,
        "subjectName": lain_ms["subject_name"],
        "originalText": candidate,
        "category": lain_ms.get("category", "Umum"),
        "kkm": kkm_val,
        "score": float(score_val),
        "accuracy": acc,
    }
