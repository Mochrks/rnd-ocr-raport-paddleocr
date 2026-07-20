import re
from rapidfuzz import fuzz

from app.schemas.kp_response import KpResponse
from app.utils.text_utils import normalize_text, clean_value

KP_FIELD_ORDER = [
    "NAMA",
    "NIS",
    "NISN",
    "TEMPAT/TGL LAHIR",
    "JENIS KELAMIN",
    "ALAMAT",
    "TINGKAT",
    "KELAS",
    "PROGRAM STUDI",
    "TAHUN AJARAN",
    "TAHUN MASUK",
    "AGAMA",
    "PEKERJAAN ORANG TUA",
    "KEPALA SEKOLAH",
]

KP_FIELD_ALIASES = {
    "NAMA": ["NAMA", "NAMA LENGKAP"],
    "NIS": ["NIS", "NOMOR INDUK SISWA", "NOMOR INDUK"],
    "NISN": ["NISN", "NISN/NIS", "NIS/NISN"],
    "TEMPAT/TGL LAHIR": [
        "TEMPAT/TGL LAHIR",
        "TEMPAT/TGL. LAHIR",
        "TEMPAT/TGL.LAHIR",
        "TEMPAT, TGL LAHIR",
        "TEMPAT TGL LAHIR",
        "TEMPAT,TGL.LAHIR",
        "TEMPAT,TGL. LAHIR",
    ],
    "JENIS KELAMIN": ["JENIS KELAMIN", "KELAMIN", "JNS KELAMIN", "JNS. KELAMIN"],
    "ALAMAT": ["ALAMAT", "ALAMAT RUMAH", "TEMPAT TINGGAL"],
    "TINGKAT": ["TINGKAT"],
    "KELAS": ["KELAS"],
    "PROGRAM STUDI": ["PROGRAM STUDI", "PROGRAM", "JURUSAN", "KOMPETENSI KEAHLIAN", "KOMPETENSI"],
    "TAHUN AJARAN": ["TAHUN AJARAN", "TH. AJARAN", "TH AJARAN"],
    "TAHUN MASUK": ["TAHUN MASUK", "TH. MASUK", "TH MASUK"],
    "AGAMA": ["AGAMA"],
    "PEKERJAAN ORANG TUA": ["PEKERJAAN ORANG TUA", "PEKERJAAN ORTU", "PEKERJAAN WALI"],
    "KEPALA SEKOLAH": ["KEPALA SEKOLAH", "KEPALA", "KEPALA MADRASAH", "MENGETAHUI"],
}

_LABEL_STRIP_PATTERN = re.compile(
    r"^(?:"
    r"NAMA|NISN|NIS|TEMPAT.*?LAHIR|JENIS\s*KELAMIN|ALAMAT|"
    r"TINGKAT|KELAS|PROGRAM\s*STUDI|JURUSAN|TAHUN\s*AJARAN|TAHUN\s*MASUK|"
    r"AGAMA|PEKERJAAN\s*ORANG\s*TUA|KEPALA\s*SEKOLAH"
    r")[\s:./]*",
    re.IGNORECASE,
)

_DATE_OR_WORD_DATE_PATTERN = re.compile(
    r"(\d{1,2}(?:\s+[a-zA-Z]+|\s*[-/]\s*\d{1,2})\s*[-/,\s]*\d{4})",
    re.IGNORECASE,
)


def _norm(text: str) -> str:
    return normalize_text(text)


def _is_any_label(text: str) -> bool:
    norm_text = _norm(text)
    for field, aliases in KP_FIELD_ALIASES.items():
        for alias in aliases:
            if len(norm_text) >= 2 and fuzz.partial_ratio(alias.upper(), norm_text) >= 85:
                return True
    return False


def _find_label_box(boxes, aliases, threshold=72):
    best_score = 0
    best_box = None

    for item in boxes:
        text = _norm(item["text"])
        if not text:
            continue
        for alias in aliases:
            min_len = 4 if len(alias) >= 6 else 2
            if len(text) < min_len:
                continue

            if "NISN" in alias.upper() and "NISN" not in text.upper():
                continue

            if len(text) >= len(alias):
                score = fuzz.partial_ratio(alias.upper(), text)
            else:
                score = fuzz.ratio(alias.upper(), text)

            if alias.upper() == "AGAMA" and ("NAM" in text or "ALAM" in text):
                continue
            if alias.upper() == "KELAS" and "KELAMIN" in text:
                continue

            if score > best_score:
                best_score = score
                best_box = item

    if best_score >= threshold:
        return best_box
    return None


def _collect_value_tokens(boxes, label_box, y_tolerance=18, x_min_ratio=0.25):
    label_y = label_box["y"]
    label_x = label_box["x"]

    image_width_estimate = max(item["x"] for item in boxes) if boxes else 600
    x_threshold = max(label_x + 60, image_width_estimate * x_min_ratio)

    candidates = []
    for item in boxes:
        if item["x"] < x_threshold:
            continue
        if abs(item["y"] - label_y) > y_tolerance:
            continue
        if _is_any_label(item["text"]):
            continue
        candidates.append(item)

    candidates.sort(key=lambda b: b["x"])
    return candidates


def _find_multi_row_value(boxes, label_box, next_label_y, y_tolerance=18):
    label_y = label_box["y"]
    label_x = label_box["x"]

    image_width_estimate = max(item["x"] for item in boxes) if boxes else 600
    x_threshold = max(label_x + 60, image_width_estimate * 0.25)

    candidates = []
    for item in boxes:
        if item["x"] < x_threshold:
            continue
        if item["y"] < label_y - y_tolerance:
            continue
        if next_label_y is not None and item["y"] > next_label_y - y_tolerance:
            continue
        if next_label_y is None and item["y"] > label_y + 80:
            continue
        if _is_any_label(item["text"]):
            continue
        candidates.append(item)

    candidates.sort(key=lambda b: (b["y"], b["x"]))
    return candidates


def _get_sorted_label_ys(boxes):
    label_ys = {}
    for field, aliases in KP_FIELD_ALIASES.items():
        box = _find_label_box(boxes, aliases)
        if box:
            label_ys[field] = box["y"]
    return label_ys


def _strip_known_labels(text: str) -> str:
    text = _LABEL_STRIP_PATTERN.sub("", text.strip())
    return text.strip().lstrip(":. ").strip()


def _extract_inline_value(text_upper: str, keyword: str) -> str | None:
    idx = text_upper.find(keyword)
    if idx == -1:
        return None
    after = text_upper[idx + len(keyword):]
    after = after.lstrip(" :./")
    return after.strip() if after.strip() else None


def parse_kp(boxes):
    data = KpResponse()
    label_ys = _get_sorted_label_ys(boxes)

    kp_title_box = _find_label_box(boxes, ["KARTU PELAJAR", "KARTU TANDA PELAJAR"])
    kp_title_y = kp_title_box["y"] if kp_title_box else 250

    header_boxes = [b for b in boxes if b["y"] < kp_title_y - 20]
    
    alamat_sekolah_tokens = []
    for b in header_boxes:
        txt = b["text"].upper()
        if "JL" in txt or "JALAN" in txt or "TELEPON" in txt or "TELP" in txt or "FAX" in txt or re.search(r"\b\d{5}\b", txt):
            alamat_sekolah_tokens.append(b)
            
    if alamat_sekolah_tokens:
        alamat_sekolah_tokens.sort(key=lambda x: (x["y"], x["x"]))
        data.alamat_sekolah = clean_value(" ".join(t["text"] for t in alamat_sekolah_tokens))
        
    nama_sekolah_tokens = []
    for b in header_boxes:
        if b in alamat_sekolah_tokens:
            continue
        txt = b["text"].upper()
        if any(w in txt for w in ["PEMERINTAH", "DINAS", "KEMENTERIAN", "UPTD", "KABUPATEN"]):
            continue
        if any(w in txt for w in ["SEKOLAH", "SMP", "SMA", "SMK", "SD", "MADRASAH", "MTS", "MA", "MI"]):
            nama_sekolah_tokens.append(b)
            
    if nama_sekolah_tokens:
        nama_sekolah_tokens.sort(key=lambda x: (x["y"], x["x"]))
        data.nama_sekolah = clean_value(" ".join(t["text"] for t in nama_sekolah_tokens))

    nama_box = _find_label_box(boxes, KP_FIELD_ALIASES["NAMA"])
    if nama_box:
        nama_candidates = _collect_value_tokens(boxes, nama_box, y_tolerance=18)
        if nama_candidates:
            data.nama = clean_value(_norm(" ".join(i["text"] for i in nama_candidates)))

    nis_box = _find_label_box(boxes, KP_FIELD_ALIASES["NIS"])
    if nis_box:
        nis_candidates = _collect_value_tokens(boxes, nis_box, y_tolerance=18)
        if nis_candidates:
            data.nis = clean_value(_norm(" ".join(i["text"] for i in nis_candidates)))

    nisn_box = _find_label_box(boxes, KP_FIELD_ALIASES["NISN"])
    if nisn_box:
        nisn_candidates = _collect_value_tokens(boxes, nisn_box, y_tolerance=18)
        if nisn_candidates:
            data.nisn = clean_value(_norm(" ".join(i["text"] for i in nisn_candidates)))

    ttl_box = _find_label_box(boxes, KP_FIELD_ALIASES["TEMPAT/TGL LAHIR"])
    if ttl_box:
        ttl_norm = _norm(ttl_box["text"])
        date_in_label = _DATE_OR_WORD_DATE_PATTERN.search(ttl_norm)
        if date_in_label:
            data.tanggal_lahir = date_in_label.group().upper()
            before_date = ttl_norm[:date_in_label.start()]
            before_date = _strip_known_labels(before_date)
            before_date = before_date.replace(",", "").strip()
            if before_date:
                data.tempat_lahir = before_date
        else:
            ttl_candidates = _collect_value_tokens(boxes, ttl_box, y_tolerance=18)
            if ttl_candidates:
                ttl_val = _norm(" ".join(i["text"] for i in ttl_candidates))
                date_match = _DATE_OR_WORD_DATE_PATTERN.search(ttl_val)
                if date_match:
                    data.tanggal_lahir = date_match.group().upper()
                    tempat = ttl_val[:date_match.start()].replace(",", "").strip()
                    tempat = _strip_known_labels(tempat)
                    if tempat:
                        data.tempat_lahir = tempat

    jk_box = _find_label_box(boxes, KP_FIELD_ALIASES["JENIS KELAMIN"])
    if jk_box:
        jk_norm = _norm(jk_box["text"])
        jk_candidates = _collect_value_tokens(boxes, jk_box, y_tolerance=18)
        jk_combined = jk_norm + " " + _norm(" ".join(i["text"] for i in jk_candidates))
        jk_combined = jk_combined.upper()
        if "LAKI" in jk_combined or "LK" in jk_combined:
            data.jenis_kelamin = "LAKI-LAKI"
        elif "PEREM" in jk_combined or "PREM" in jk_combined or "PR" in jk_combined:
            data.jenis_kelamin = "PEREMPUAN"

    alamat_box = _find_label_box(boxes, KP_FIELD_ALIASES["ALAMAT"])
    if alamat_box:
        next_ys = [y for f, y in label_ys.items() if y > alamat_box["y"]]
        next_y = min(next_ys) if next_ys else None
        alamat_candidates = _find_multi_row_value(boxes, alamat_box, next_label_y=next_y, y_tolerance=18)
        if alamat_candidates:
            data.alamat = clean_value(_norm(" ".join(i["text"] for i in alamat_candidates)))

    tingkat_box = _find_label_box(boxes, KP_FIELD_ALIASES["TINGKAT"])
    if tingkat_box:
        candidates = _collect_value_tokens(boxes, tingkat_box, y_tolerance=18)
        if candidates:
            data.tingkat = clean_value(_norm(" ".join(i["text"] for i in candidates)))

    kelas_box = _find_label_box(boxes, KP_FIELD_ALIASES["KELAS"])
    if kelas_box:
        candidates = _collect_value_tokens(boxes, kelas_box, y_tolerance=18)
        if candidates:
            data.kelas = clean_value(_norm(" ".join(i["text"] for i in candidates)))

    program_box = _find_label_box(boxes, KP_FIELD_ALIASES["PROGRAM STUDI"])
    if program_box:
        candidates = _collect_value_tokens(boxes, program_box, y_tolerance=18)
        if candidates:
            data.program_studi = clean_value(_norm(" ".join(i["text"] for i in candidates)))

    tahun_ajaran_box = _find_label_box(boxes, KP_FIELD_ALIASES["TAHUN AJARAN"])
    if tahun_ajaran_box:
        candidates = _collect_value_tokens(boxes, tahun_ajaran_box, y_tolerance=18)
        if candidates:
            data.tahun_ajaran = clean_value(_norm(" ".join(i["text"] for i in candidates)))

    tahun_masuk_box = _find_label_box(boxes, KP_FIELD_ALIASES["TAHUN MASUK"])
    if tahun_masuk_box:
        candidates = _collect_value_tokens(boxes, tahun_masuk_box, y_tolerance=18)
        if candidates:
            data.tahun_masuk = clean_value(_norm(" ".join(i["text"] for i in candidates)))

    agama_box = _find_label_box(boxes, KP_FIELD_ALIASES["AGAMA"])
    if agama_box:
        candidates = _collect_value_tokens(boxes, agama_box, y_tolerance=18)
        if candidates:
            data.agama = clean_value(_norm(" ".join(i["text"] for i in candidates)))

    pekerjaan_ortu_box = _find_label_box(boxes, KP_FIELD_ALIASES["PEKERJAAN ORANG TUA"])
    if pekerjaan_ortu_box:
        candidates = _collect_value_tokens(boxes, pekerjaan_ortu_box, y_tolerance=18)
        if candidates:
            data.pekerjaan_orang_tua = clean_value(_norm(" ".join(i["text"] for i in candidates)))

    kepala_box = _find_label_box(boxes, KP_FIELD_ALIASES["KEPALA SEKOLAH"])
    if kepala_box:
        kepala_candidates = []
        for item in boxes:
            if item["y"] > kepala_box["y"] and abs(item["x"] - kepala_box["x"]) < 200:
                text_clean = item["text"].upper()
                if any(w in text_clean for w in ["NIP", "NIDN", "EMAIL", "BLOG", "WEBSITE", "E-MAIL"]):
                    continue
                if len(text_clean) < 4:
                    continue
                kepala_candidates.append(item)
        if kepala_candidates:
            kepala_candidates.sort(key=lambda x: x["y"])
            data.kepala_sekolah = clean_value(kepala_candidates[0]["text"])

    for item in boxes:
        text = _norm(item["text"])
        if "BERLAKU" in text and "SISWA" in text:
            data.tanggal_berlaku_sampai = "SEBANYAK MENJADI SISWA"
        elif "BERLAKU" in text:
            date_m = _DATE_OR_WORD_DATE_PATTERN.search(text)
            if date_m:
                data.tanggal_berlaku_sampai = date_m.group().upper()

    for item in boxes:
        if item["y"] > kp_title_y + 100:
            text = _norm(item["text"])
            if "LAHIR" in text:
                continue
            if any(w in text for w in ["SURABAYA", "JAKARTA", "BANDUNG", "MEDAN", "SEMARANG"]):
                date_m = _DATE_OR_WORD_DATE_PATTERN.search(text)
                if date_m:
                    data.tanggal_terbit = date_m.group().upper()
                    break

    return data