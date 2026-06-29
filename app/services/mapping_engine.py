"""
Mapping Engine — Subject, Personality, Attendance Matching
===========================================================
Enhancement v2:
- Migrasi dari thefuzz ke rapidfuzz (lebih cepat, lebih akurat)
- Normalisasi teks sebelum matching (lowercase, trim, hapus simbol)
- Threshold 65% untuk fuzzy matching (cukup toleran untuk OCR noise)
- Personality: handle "Amat Baik", "Kelakuan/Spiritual", "Kerajinan & Kedisiplinan"
- Attendance: handle "2 hari", "Tanpa Keterangan", "- Hari"
- Tetap backward compatible: get_best_match() interface tidak berubah
"""

import re
import logging
from typing import List, Optional, Dict, Tuple, Any

from rapidfuzz import process as rf_process, fuzz as rf_fuzz

from app.utils.text_normalizer import normalize_text

logger = logging.getLogger(__name__)


# ============================================================
# MASTER DATA — Personality & Attendance Mapping
# ============================================================

# Mapping kepribadian: normalized_alias → canonical_key
PERSONALITY_ALIASES: Dict[str, str] = {
    # Kelakuan / Spiritual / Sikap Spiritual
    "kelakuan": "kelakuan",
    "spiritual": "kelakuan",
    "sikap spiritual": "kelakuan",
    "sikap spritual": "kelakuan",
    "kelakuan spiritual": "kelakuan",
    "kelakuan/spiritual": "kelakuan",
    "tingkah laku": "kelakuan",
    "perilaku": "kelakuan",
    # Kerajinan / Sosial / Sikap Sosial
    "kerajinan": "kerajinan",
    "sosial": "kerajinan",
    "sikap sosial": "kerajinan",
    "kedisiplinan": "kerajinan",
    "disiplin": "kerajinan",
    "kerajinan sosial": "kerajinan",
    "kerajinan/sosial": "kerajinan",
    "kerajinan kedisiplinan": "kerajinan",
    "kerajinan & kedisiplinan": "kerajinan",
    # Kerapihan / Kebersihan
    "kerapihan": "kerapihan",
    "kerapian": "kerapihan",
    "kebersihan": "kerapihan",
    "kebersihan dan kerapihan": "kerapihan",
    "kebersihan dan kerapian": "kerapihan",
    "kerapian kebersihan": "kerapihan",
    "kerapian & kebersihan": "kerapihan",
    "kebersihan & kerapihan": "kerapihan",
    "kebersihan kerapihan": "kerapihan",
}

# Mapping absensi: normalized_alias → canonical_key
ATTENDANCE_ALIASES: Dict[str, str] = {
    "sakit": "sakit",
    "ijin": "ijin",
    "izin": "ijin",
    "isin": "ijin",
    "alpa": "alpa",
    "alpha": "alpa",
    "alfa": "alpa",
    "tidak hadir": "alpa",
    "tanpa keterangan": "alpa",
    "tanpa ket": "alpa",
}


# ============================================================
# SUBJECT FUZZY MATCHING
# ============================================================

def get_best_match(
    raw_name: str,
    master_subjects: List[Dict],
    threshold: int = 65,
) -> Optional[Dict]:
    """
    Cari MasterSubject terbaik untuk raw_name dari OCR.
    
    Enhancement:
    - Normalisasi teks sebelum matching
    - Prioritas: exact word match → Lain-Lain exact alias → fuzzy match (RapidFuzz)
    - Threshold default 65 (bisa override), spec merekomendasikan 85 untuk fuzzy
    - Lain-Lain HANYA bisa match via exact alias (tidak lewat fuzzy)

    Args:
        raw_name: teks hasil OCR (belum dinormalisasi)
        master_subjects: list master subject dengan id, subject_name, aliases
        threshold: minimum similarity score (0-100) untuk fuzzy match

    Returns:
        Dict master subject yang cocok, atau None
    """
    if not master_subjects or not raw_name:
        return None

    # Normalisasi input
    raw_normalized = normalize_text(raw_name)

    if len(raw_normalized) < 2:
        return None

    raw_words = set(re.findall(r'\w+', raw_normalized))

    # ── Pass 1: Exact substring / word match untuk mapel utama (skip Lain-Lain) ──
    for ms in master_subjects:
        # Skip "Lain - Lain" di pass 1 — dihandle di pass 1.5
        if 'Lain' in ms['subject_name']:
            continue

        subj_norm = normalize_text(ms["subject_name"])
        if subj_norm and subj_norm in raw_normalized:
            logger.debug(f"  [Exact-Subject] '{raw_name}' → '{ms['subject_name']}'")
            return ms

        for alias in ms.get("aliases", []):
            alias_norm = normalize_text(alias)
            if not alias_norm:
                continue
            alias_words = set(re.findall(r'\w+', alias_norm))
            # Untuk alias pendek (akronim: PKN, IPA, IPS, TIK) → exact word match
            if len(alias_norm) <= 4:
                if alias_words.issubset(raw_words) and alias_words:
                    logger.debug(f"  [Exact-Acronym] '{raw_name}' → '{ms['subject_name']}' via '{alias}'")
                    return ms
            else:
                if alias_norm in raw_normalized:
                    logger.debug(f"  [Exact-Alias] '{raw_name}' → '{ms['subject_name']}' via '{alias}'")
                    return ms

    # ── Pass 1.5: Exact alias match untuk Lain-Lain ──
    # (HARUS exact — Lain-Lain tidak pernah lewat fuzzy)
    for ms in master_subjects:
        if 'Lain' not in ms['subject_name']:
            continue
        for alias in ms.get("aliases", []):
            alias_norm = normalize_text(alias)
            if not alias_norm:
                continue
            # Exact substring match
            if alias_norm in raw_normalized or raw_normalized in alias_norm:
                logger.debug(f"  [Exact-LainLain] '{raw_name}' → '{ms['subject_name']}' via '{alias}'")
                return ms
            # Exact word set match untuk alias panjang
            alias_words = set(re.findall(r'\w+', alias_norm))
            if len(alias_words) >= 2 and alias_words.issubset(raw_words):
                logger.debug(f"  [Word-LainLain] '{raw_name}' → '{ms['subject_name']}' via '{alias}'")
                return ms

    # ── Pass 2: Fuzzy match (RapidFuzz) — HANYA untuk mapel utama ──
    # Bangun choices: normalized_alias/name → master_subject
    choices: Dict[str, Dict] = {}
    for ms in master_subjects:
        # Skip Lain-Lain dari fuzzy matching (sudah dihandle di Pass 1.5)
        if 'Lain' in ms['subject_name']:
            continue
        subj_norm = normalize_text(ms["subject_name"])
        if subj_norm:
            choices[subj_norm] = ms
        for alias in ms.get("aliases", []):
            alias_norm = normalize_text(alias)
            if alias_norm:
                choices[alias_norm] = ms

    if not choices:
        return None

    # Gunakan WRatio untuk toleransi OCR noise
    result = rf_process.extractOne(
        raw_normalized,
        list(choices.keys()),
        scorer=rf_fuzz.WRatio,
        score_cutoff=threshold,
    )

    if result:
        match_str, score, _ = result
        logger.debug(f"  [Fuzzy] '{raw_name}' → '{choices[match_str]['subject_name']}' (score={score:.1f})")
        return choices[match_str]

    return None


def compute_combined_accuracy(
    ocr_confidence: float,
    match_similarity: float,
    score_valid: bool,
    position_valid: bool = True,
) -> float:
    """
    Hitung accuracy gabungan dari berbagai sumber.
    
    Formula:
        accuracy = (ocr_conf * 0.4) + (similarity * 0.35) + (score_valid * 0.15) + (pos_valid * 0.10)
    
    Args:
        ocr_confidence: rata-rata confidence dari OCR engine (0.0 - 1.0)
        match_similarity: similarity score dari fuzzy matching (0 - 100)
        score_valid: apakah nilai angka valid (0-100)
        position_valid: apakah posisi koordinat masuk akal

    Returns:
        accuracy dalam persen (0.0 - 100.0)
    """
    # Normalisasi ke 0-1
    ocr_conf_norm = max(0.0, min(1.0, ocr_confidence))
    similarity_norm = max(0.0, min(100.0, match_similarity)) / 100.0
    score_factor = 1.0 if score_valid else 0.5
    pos_factor = 1.0 if position_valid else 0.7

    combined = (
        ocr_conf_norm * 0.40
        + similarity_norm * 0.35
        + score_factor * 0.15
        + pos_factor * 0.10
    ) * 100.0

    return round(combined, 1)


# ============================================================
# PERSONALITY EXTRACTION
# ============================================================

def extract_personality(rows: List[List[Dict]], score_zone_start: float) -> Optional[Dict]:
    """
    Ekstrak data kepribadian (kelakuan, kerajinan, kerapihan) dari OCR rows.
    
    Mencari baris yang mengandung kata kunci kepribadian,
    lalu ambil nilai grade (A/B/C/D, angka, atau deskripsi) dari kolom nilai.

    Args:
        rows: list of OCR word rows (sudah di-cluster by Y)
        score_zone_start: batas X kolom nilai (untuk menemukan grade)

    Returns:
        dict {kelakuan: {grade, accuracy}, kerajinan: ..., kerapihan: ...}
        atau None jika tidak ditemukan
    """
    found: Dict[str, Dict] = {}

    # Kata kunci header seksi kepribadian
    personality_section_keywords = [
        'kepribadian', 'sikap', 'karakter', 'afektif',
        'penilaian sikap', 'aspek kepribadian', 'kepribadi',
    ]

    # Kata kunci yang menandakan baris ini adalah baris mata pelajaran (bukan kepribadian)
    subject_row_keywords = [
        'ilmu pengetahuan', 'bahasa', 'matematika', 'fisika', 'kimia',
        'biologi', 'sejarah', 'geografi', 'ekonomi', 'sosiologi',
        'pendidikan', 'olahraga', 'jasmani', 'seni', 'prakarya',
        'kewirausahaan', 'komputer', 'informatika', 'teknologi',
        'normatif', 'adaptif', 'produktif', 'muatan lokal',
        'ilmu',       # Ilmu Pengetahuan Alam/Sosial, Ilmu Sosial
        'agama',      # Pendidikan Agama
        'geografi', 'sosiologi', 'ekonomi',
        'kewarganegaraan', 'jaringan', 'desain',
    ]

    in_personality_section = False

    for row in rows:
        row_text = " ".join(w['text'] for w in row).strip()
        row_text_lower = row_text.lower()
        row_norm = normalize_text(row_text)

        # Deteksi masuk seksi kepribadian
        if any(kw in row_text_lower for kw in personality_section_keywords):
            in_personality_section = True

        # Deteksi keluar dari seksi
        if in_personality_section:
            exit_keywords = ['mata pelajaran', 'bidang studi', 'jumlah', 'peringkat',
                             'absensi', 'absen', 'kehadiran', 'ketidak hadiran',
                             'catatan', 'keputusan', 'mengetahui']
            if any(kw in row_text_lower for kw in exit_keywords):
                in_personality_section = False

        # Guard: jika baris jelas merupakan baris mata pelajaran, skip
        if any(kw in row_text_lower for kw in subject_row_keywords):
            continue

        # Cari personality alias di row
        # Hanya cari jika:
        # (a) sedang di seksi kepribadian, ATAU
        # (b) baris sangat pendek (label kepribadian standalone, mis. "Kelakuan", "Kerajinan")
        row_is_short = len(row_norm.strip()) <= 35
        if not in_personality_section and not row_is_short:
            continue

        personality_key = _find_personality_key(row_norm, row_text_lower)
        if personality_key and personality_key not in found:
            grade_val, grade_conf = _extract_grade_from_row(row, score_zone_start)
            if grade_val is not None:
                ocr_conf = sum(w['conf'] for w in row) / len(row) if row else 0.0
                found[personality_key] = {
                    "grade": grade_val,
                    "accuracy": round(ocr_conf * 100 * 0.9, 1),
                }
                logger.info(f"  📋 Personality '{personality_key}': grade={grade_val}")

    if not found:
        return None

    return {
        "kelakuan": found.get("kelakuan"),
        "kerajinan": found.get("kerajinan"),
        "kerapihan": found.get("kerapihan"),
    }


def _find_personality_key(normalized_text: str, raw_lower: str = "") -> Optional[str]:
    """
    Temukan canonical personality key dari teks yang sudah dinormalisasi.
    Support combined labels: "Kelakuan/Spiritual", "Kerajinan & Kedisiplinan",
    "Kerapian & Kebersihan"

    Guard penting: alias pendek seperti 'sosial', 'disiplin' harus DOMINAN
    dalam teks (bukan sekadar substring kecil di nama mata pelajaran panjang).
    Contoh: 'sosial' di 'ilmu pengetahuan sosial' → TIDAK cocok (hanya 27%).
    """
    search_text = normalized_text or raw_lower
    text_len = len(search_text)

    # Pass 1: Substring match dengan dominance check
    for alias, canonical in PERSONALITY_ALIASES.items():
        if alias not in search_text:
            continue
        # Dominance check: alias harus ≥ 40% panjang teks
        # Ini mencegah 'sosial' match di 'ilmu pengetahuan sosial'
        alias_ratio = len(alias) / text_len if text_len > 0 else 0
        if alias_ratio >= 0.40:
            return canonical
        # Untuk alias panjang (multi-word ≥ 2 kata), longgarkan sedikit
        if len(alias.split()) >= 2 and alias_ratio >= 0.25:
            return canonical

    # Pass 1b: Check raw_lower juga
    if raw_lower and raw_lower != search_text:
        raw_len = len(raw_lower)
        for alias, canonical in PERSONALITY_ALIASES.items():
            if alias not in raw_lower:
                continue
            alias_ratio = len(alias) / raw_len if raw_len > 0 else 0
            if alias_ratio >= 0.40:
                return canonical
            if len(alias.split()) >= 2 and alias_ratio >= 0.25:
                return canonical

    # Pass 2: Fuzzy match — hanya untuk teks pendek (kemungkinan label kepribadian)
    if len(normalized_text) > 40:
        return None

    result = rf_process.extractOne(
        normalized_text,
        list(PERSONALITY_ALIASES.keys()),
        scorer=rf_fuzz.WRatio,
        score_cutoff=80,
    )
    if result:
        match_str, score, _ = result
        return PERSONALITY_ALIASES[match_str]

    return None


def _extract_grade_from_row(row: List[Dict], score_zone_start: float) -> Tuple[Optional[str], float]:
    """
    Ambil nilai grade dari sebuah row OCR.
    Grade bisa berupa:
    - Huruf: A/B/C/D
    - Deskripsi: "Amat Baik", "Baik", "Cukup", "Kurang"
    - Angka: 75, 80, dll
    Prioritas: nilai di kolom kanan (x >= score_zone_start).
    """
    # Kumpulkan semua teks di kolom kanan
    right_values = [w for w in row if w['x'] >= score_zone_start]
    # Jika tidak ada nilai di kanan, cari di seluruh baris
    all_values = right_values if right_values else row

    # Gabungkan semua teks kanan menjadi satu string untuk cek deskripsi multi-word
    right_text = " ".join(w['text'] for w in all_values).strip()
    right_text_lower = right_text.lower()

    # Check deskripsi multi-word dulu: "Amat Baik", "Sangat Baik", etc.
    desc_patterns = [
        ('amat baik', 'Amat Baik'),
        ('sangat baik', 'Sangat Baik'),
        ('baik sekali', 'Baik Sekali'),
        ('baik', 'Baik'),
        ('cukup baik', 'Cukup Baik'),
        ('cukup', 'Cukup'),
        ('kurang', 'Kurang'),
    ]
    for pattern, label in desc_patterns:
        if pattern in right_text_lower:
            conf = max((w['conf'] for w in all_values), default=0.0)
            return label, conf

    # Check per-word
    for w in all_values:
        t = w['text'].strip()
        # Grade huruf: A, B, C, D
        grade_match = re.match(r'^([ABCD])$', t, re.IGNORECASE)
        if grade_match:
            return grade_match.group(1).upper(), w['conf']

    # Check angka
    for w in all_values:
        t = w['text'].strip()
        try:
            val = float(t.replace(',', '.'))
            if 0 <= val <= 100:
                return str(int(val)) if val == int(val) else str(val), w['conf']
        except ValueError:
            pass

    return None, 0.0


# ============================================================
# ATTENDANCE EXTRACTION
# ============================================================

def extract_attendance(rows: List[List[Dict]], score_zone_start: float) -> Optional[Dict]:
    """
    Ekstrak data absensi (sakit, ijin, alpa) dari OCR rows.

    Args:
        rows: list of OCR word rows (sudah di-cluster by Y)
        score_zone_start: batas X kolom nilai

    Returns:
        dict {sakit: {value, accuracy}, ijin: ..., alpa: ...}
        atau None jika tidak ditemukan
    """
    found: Dict[str, Dict] = {}

    # Kata kunci header seksi absensi
    attendance_section_keywords = [
        'absensi', 'absen', 'kehadiran', 'ketidakhadiran',
        'ketidak hadiran', 'rekap kehadiran', 'tidak hadiran',
    ]

    in_attendance_section = False

    for row in rows:
        row_text = " ".join(w['text'] for w in row).strip()
        row_text_lower = row_text.lower()
        row_norm = normalize_text(row_text)

        # Deteksi masuk seksi absensi
        if any(kw in row_text_lower for kw in attendance_section_keywords):
            in_attendance_section = True
            # Jangan skip — mungkin ada data di baris yang sama

        # Deteksi keluar seksi absensi
        if in_attendance_section:
            exit_keywords = ['kepribadian', 'mata pelajaran', 'peringkat',
                             'mengetahui', 'wali', 'catatan', 'keputusan',
                             'di berikan', 'diberikan']
            if any(kw in row_text_lower for kw in exit_keywords):
                in_attendance_section = False

        # Cari attendance alias
        attendance_key = _find_attendance_key(row_norm, row_text_lower)
        if attendance_key and attendance_key not in found:
            value, conf = _extract_attendance_value_from_row(row, row_text, score_zone_start)
            if value is not None:
                ocr_conf = sum(w['conf'] for w in row) / len(row) if row else 0.0
                found[attendance_key] = {
                    "value": value,
                    "accuracy": round(ocr_conf * 100 * 0.95, 1),
                }
                logger.info(f"  📅 Attendance '{attendance_key}': value={value}")

    if not found:
        return None

    return {
        "sakit": found.get("sakit"),
        "ijin": found.get("ijin"),
        "alpa": found.get("alpa"),
    }


def _find_attendance_key(normalized_text: str, raw_lower: str = "") -> Optional[str]:
    """
    Temukan canonical attendance key dari teks yang sudah dinormalisasi.
    Exact match dulu, fuzzy hanya untuk teks pendek.
    """
    search_text = normalized_text or raw_lower

    for alias, canonical in ATTENDANCE_ALIASES.items():
        if alias in search_text:
            return canonical

    # Check raw_lower juga
    if raw_lower and raw_lower != search_text:
        for alias, canonical in ATTENDANCE_ALIASES.items():
            if alias in raw_lower:
                return canonical

    # Fuzzy hanya untuk teks pendek (<= 30 char)
    if len(normalized_text) > 30:
        return None

    result = rf_process.extractOne(
        normalized_text,
        list(ATTENDANCE_ALIASES.keys()),
        scorer=rf_fuzz.WRatio,
        score_cutoff=85,
    )
    if result:
        match_str, score, _ = result
        return ATTENDANCE_ALIASES[match_str]

    return None


def _extract_attendance_value_from_row(
    row: List[Dict], row_text: str, score_zone_start: float
) -> Tuple[Optional[Any], float]:
    """
    Ambil nilai absensi (angka hari) dari sebuah row OCR.
    Nilai biasanya angka kecil 0-99 di kolom kanan.
    Handle: "2 hari", "- Hari", "2", "-", "–"
    """
    # Cari nilai di kolom kanan
    right_values = [w for w in row if w['x'] >= score_zone_start]
    all_values = right_values if right_values else row

    # Gabungkan teks kanan
    right_text = " ".join(w['text'] for w in all_values).strip().lower()

    # Check "X hari" pattern
    hari_match = re.search(r'(\d+)\s*hari', right_text)
    if hari_match:
        return int(hari_match.group(1)), max((w['conf'] for w in all_values), default=0.0)

    # Check "- Hari" atau "– Hari" → 0
    if re.search(r'[-–—]\s*hari', right_text):
        return 0, max((w['conf'] for w in all_values), default=0.0)

    for w in all_values:
        t = w['text'].strip()
        # Coba parse angka
        try:
            val = int(float(t.replace(',', '.')))
            if 0 <= val <= 999:  # absensi bisa sampai ratusan hari
                return val, w['conf']
        except ValueError:
            pass
        # Cek dash/strip sebagai "0 hari"
        if t in ['-', '–', '—', '0']:
            return 0, w['conf']

    return None, 0.0
