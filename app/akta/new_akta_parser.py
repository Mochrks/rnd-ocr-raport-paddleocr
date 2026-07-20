import re

from app.schemas.akta_response import AktaResponse
from app.utils.normalizer import normalize_text


# ============================================================
# KONSTANTA
# ============================================================

MONTH_MAP = {
    "JANUARI": "01",
    "FEBRUARI": "02",
    "MARET": "03",
    "APRIL": "04",
    "MEI": "05",
    "JUNI": "06",
    "JULI": "07",
    "AGUSTUS": "08",
    "SEPTEMBER": "09",
    "OKTOBER": "10",
    "NOVEMBER": "11",
    "DESEMBER": "12",
}

DAY_MAP = {
    "TIGA PULUH SATU": "31",
    "TIGA PULUH": "30",
    "DUA PULUH SEMBILAN": "29",
    "DUA PULUH DELAPAN": "28",
    "DUA PULUH TUJUH": "27",
    "DUA PULUH ENAM": "26",
    "DUA PULUH LIMA": "25",
    "DUA PULUH EMPAT": "24",
    "DUA PULUH TIGA": "23",
    "DUA PULUH DUA": "22",
    "DUA PULUH SATU": "21",
    "DUA PULUH": "20",
    "SEMBILAN BELAS": "19",
    "DELAPAN BELAS": "18",
    "TUJUH BELAS": "17",
    "ENAM BELAS": "16",
    "LIMA BELAS": "15",
    "EMPAT BELAS": "14",
    "TIGA BELAS": "13",
    "DUA BELAS": "12",
    "SEBELAS": "11",
    "SEPULUH": "10",
    "SEMBILAN": "09",
    "DELAPAN": "08",
    "TUJUH": "07",
    "ENAM": "06",
    "LIMA": "05",
    "EMPAT": "04",
    "TIGA": "03",
    "DUA": "02",
    "SATU": "01",
}

BIRTH_MONTH_SECTION_KEYWORDS = list(MONTH_MAP.keys())

_RIBUAN = {"SATU": 1000, "DUA": 2000}
_RATUSAN = {
    "SERATUS": 100, "DUA RATUS": 200, "TIGA RATUS": 300,
    "EMPAT RATUS": 400, "LIMA RATUS": 500, "ENAM RATUS": 600,
    "TUJUH RATUS": 700, "DELAPAN RATUS": 800, "SEMBILAN RATUS": 900,
}
_PULUHAN = {
    "SEMBILAN PULUH": 90, "DELAPAN PULUH": 80, "TUJUH PULUH": 70,
    "ENAM PULUH": 60, "LIMA PULUH": 50, "EMPAT PULUH": 40,
    "TIGA PULUH": 30, "DUA PULUH": 20, "SEPULUH": 10,
    "SEBELAS": 11, "DUA BELAS": 12, "TIGA BELAS": 13, "EMPAT BELAS": 14,
    "LIMA BELAS": 15, "ENAM BELAS": 16, "TUJUH BELAS": 17,
    "DELAPAN BELAS": 18, "SEMBILAN BELAS": 19,
}
_SATUAN = {
    "SATU": 1, "DUA": 2, "TIGA": 3, "EMPAT": 4, "LIMA": 5,
    "ENAM": 6, "TUJUH": 7, "DELAPAN": 8, "SEMBILAN": 9,
}


# ============================================================
# KONVERSI TAHUN TERBILANG → ANGKA
# ============================================================

def terbilang_to_year(text: str) -> str | None:
    text = text.strip().upper()

    ribu_match = re.search(r"(SATU|DUA)\s+RIBU\s*(.*)", text)
    if not ribu_match:
        return None

    base_str = ribu_match.group(1)
    remainder = ribu_match.group(2).strip()
    year_val = _RIBUAN.get(base_str, 0)

    if not remainder:
        return str(year_val)

    for key in sorted(_RATUSAN.keys(), key=len, reverse=True):
        if remainder.startswith(key):
            year_val += _RATUSAN[key]
            remainder = remainder[len(key):].strip()
            break

    matched_puluhan = False
    for key in sorted(_PULUHAN.keys(), key=len, reverse=True):
        if remainder.startswith(key):
            year_val += _PULUHAN[key]
            remainder = remainder[len(key):].strip()
            matched_puluhan = True
            break

    if not matched_puluhan:
        for key in sorted(_SATUAN.keys(), key=len, reverse=True):
            if remainder.startswith(key):
                year_val += _SATUAN[key]
                remainder = remainder[len(key):].strip()
                break

    if matched_puluhan and remainder:
        for key in sorted(_SATUAN.keys(), key=len, reverse=True):
            if remainder.startswith(key):
                year_val += _SATUAN[key]
                break

    if 1000 <= year_val <= 2100:
        return str(year_val)

    return None


# ============================================================
# HELPER
# ============================================================

def group_rows(raw_boxes, tolerance=20):
    boxes = sorted(raw_boxes, key=lambda x: x["y"])
    rows = []

    for box in boxes:
        found = False
        for row in rows:
            if abs(row[0]["y"] - box["y"]) <= tolerance:
                row.append(box)
                found = True
                break
        if not found:
            rows.append([box])

    for row in rows:
        row.sort(key=lambda x: x["x"])

    return rows


def join_rows(rows):
    result = []
    for row in rows:
        text = " ".join(item["text"] for item in row)
        result.append(text.strip())
    return result


# ============================================================
# PARSER
# ============================================================

def parse_new_akta(raw_boxes):

    data = AktaResponse()

    rows = group_rows(raw_boxes)
    lines = join_rows(rows)
    text = " ".join(lines)
    text = normalize_text(text)

    #
    # NOMOR AKTA
    #
    nomor_match = re.search(r"\d{4}-LT-\d{8}-\d+", text)
    if nomor_match:
        data.nomor_akta = nomor_match.group()

    #
    # TEMPAT LAHIR
    #
    tempat_match = re.search(r"BAHWA DI (.+?) PADA", text)
    if tempat_match:
        data.tempat_lahir = tempat_match.group(1).strip().title()

    #
    # JENIS KELAMIN
    #
    if "LAKI-LAKI" in text:
        data.jenis_kelamin = "LAKI-LAKI"
    elif "PEREMPUAN" in text:
        data.jenis_kelamin = "PEREMPUAN"

    #
    # NAMA ANAK
    #
    nama_anak_from_lines = None

    for i, line in enumerate(lines):
        upper = line.upper()
        if upper.startswith("ANAK KE") or upper.startswith("CHILD NO"):
            if i > 0:
                prev = lines[i - 1]
                prev_upper = prev.upper()
                if prev_upper == prev and len(prev.split()) >= 1:
                    nama_anak_from_lines = prev_upper
            break

    if nama_anak_from_lines:
        data.nama_anak = nama_anak_from_lines.title()
    else:
        candidate_names = []

        blacklist = [
            "REPUBLIK", "INDONESIA", "PENCATATAN", "KELAHIRAN",
            "NOVEMBER", "OKTOBER", "SEPTEMBER", "AGUSTUS",
            "JULI", "JUNI", "MEI", "APRIL", "MARET", "FEBRUARI", "JANUARI", "DESEMBER",
            "TAHUN", "DINAS", "NIP", "WARGANEGARA", "REGISTRY", "OFFICE", "CERTIFICATE",
            "NATIONALITY", "EXCERPT", "KUTIPAN", "BERDASARKAN", "BAHWA", "PADA",
            "RIBU", "PULUH",
        ]

        for line in lines:
            upper = line.upper()
            if len(line.split()) < 2:
                continue
            if upper != line:
                continue
            if any(word in upper for word in blacklist):
                continue
            if any(kw in upper for kw in ("AYAH", "IBU", "DAN", "ANAK", "-")):
                continue
            candidate_names.append(line)

        if candidate_names:
            data.nama_anak = max(candidate_names, key=len).title()

    #
    # AYAH & IBU
    #
    for line in lines:
        line_upper = line.upper()
        if "DAN IBU" in line_upper and ("AYAH" in line_upper or "DARI" in line_upper):
            ayah_match = re.search(r"AYAH\s+(.+?)\s+DAN\s+IBU", line_upper)
            if ayah_match:
                data.nama_ayah = ayah_match.group(1).strip().title()
            idx = line_upper.find("DAN IBU")
            if idx != -1:
                ibu_part = line_upper[idx + 7:].strip()
                ibu_part = re.sub(r"[^A-Z\s]", "", ibu_part).strip()
                if ibu_part:
                    data.nama_ibu = ibu_part.title()
            break

    if not data.nama_ayah:
        ayah_match = re.search(r"AYAH\s+(.+?)\s+DAN\s+IBU", text)
        if ayah_match:
            data.nama_ayah = ayah_match.group(1).strip().title()

    if not data.nama_ibu:
        ibu_match = re.search(
            r"DAN IBU\s+([A-Z]+(?:\s+[A-Z]+)*?)\s+(?:KUTIPAN|KUTPAN|DIBLITAR|THE EXCERPT|CHILD|ANAK KE|MOTHER)",
            text,
        )
        if ibu_match:
            data.nama_ibu = ibu_match.group(1).strip().title()

    #
    # TANGGAL LAHIR
    #
    day = None

    lahir_section_match = re.search(
        r"BAHWA DI.+?PADA TANGGAL\s+([A-Z\s]+?)\s+(?:TELAH LAHIR|WES BORN|" +
        "|".join(BIRTH_MONTH_SECTION_KEYWORDS) + r")",
        text,
    )

    if lahir_section_match:
        day_candidate = lahir_section_match.group(1).strip()
        for key in sorted(DAY_MAP.keys(), key=len, reverse=True):
            if day_candidate.startswith(key):
                day = DAY_MAP[key]
                break
        if not day:
            day = DAY_MAP.get(day_candidate)
    else:
        for key in sorted(DAY_MAP.keys(), key=len, reverse=True):
            pattern = rf"PADA TANGGAL {re.escape(key)}\s+(?:{'|'.join(BIRTH_MONTH_SECTION_KEYWORDS)})"
            if re.search(pattern, text):
                day = DAY_MAP[key]
                break

    month = None

    birth_section_match = re.search(r"BAHWA DI.+?(?:ANAK KE|CHILD NO)", text)
    birth_section_text = (
        birth_section_match.group(0)
        if birth_section_match
        else text
    )

    for key, value in MONTH_MAP.items():
        if key in birth_section_text:
            month = value
            break

    year = None

    year_candidate_match = re.search(
        r"((?:SATU|DUA)\s+RIBU\s+[A-Z\s]+?)(?:\s+TELAH LAHIR|\s+WES BORN|$)",
        birth_section_text,
    )

    if year_candidate_match:
        year = terbilang_to_year(year_candidate_match.group(1))

    if not year:
        year_match = re.search(
            r"((?:SATU|DUA)\s+RIBU(?:\s+[A-Z]+){0,6})",
            birth_section_text,
        )
        if year_match:
            year = terbilang_to_year(year_match.group(1))

    if day and month and year:
        data.tanggal_lahir = f"{day}-{month}-{year}"

    return data