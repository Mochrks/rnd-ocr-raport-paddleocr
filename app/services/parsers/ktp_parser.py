import re

from rapidfuzz import fuzz

from app.schemas.ktp_response import KtpResponse

from app.services.fuzzy.gender_matcher import (
    match_gender
)

from app.services.fuzzy.religion_matcher import (
    match_religion
)

from app.services.fuzzy.marital_status_matcher import (
    match_marital_status
)

from app.services.fuzzy.occupation_matcher import (
    match_occupation
)

from app.services.fuzzy.nationality_matcher import (
    match_nationality
)

from app.utils.text_utils import (
    normalize_text,
    clean_value
)

from app.utils.validator import (
    validate_nik
)


KTP_FIELD_ORDER = [
    "NIK",
    "NAMA",
    "TEMPAT/TGL LAHIR",
    "JENIS KELAMIN",
    "ALAMAT",
    "RT/RW",
    "KEL/DESA",
    "KECAMATAN",
    "AGAMA",
    "STATUS PERKAWINAN",
    "PEKERJAAN",
    "KEWARGANEGARAAN",
    "BERLAKU HINGGA",
]

KTP_FIELD_ALIASES = {
    "NIK": ["NIK", "NOMOR INDUK"],
    "NAMA": ["NAMA"],
    "TEMPAT/TGL LAHIR": [
        "TEMPAT/TGL LAHIR",
        "TEMPAT/TGLLAHIR",
        "TEMPAT TGL LAHIR",
        "TEMPAT/TGL.LAHIR",
    ],
    "JENIS KELAMIN": ["JENIS KELAMIN", "JENISKELAMIN", "JENIS KELAMININ"],
    "ALAMAT": ["ALAMAT"],
    "RT/RW": ["RT/RW", "RTRW", "RT RW"],
    "KEL/DESA": ["KEL/DESA", "KELURAHAN", "KEL DESA", "KELDESA"],
    "KECAMATAN": ["KECAMATAN"],
    "AGAMA": ["AGAMA"],
    "STATUS PERKAWINAN": ["STATUS PERKAWINAN", "STATUSPERKAWINAN"],
    "PEKERJAAN": ["PEKERJAAN", "PEKERJEAN", "PEKERJCAN"],
    "KEWARGANEGARAAN": ["KEWARGANEGARAAN"],
    "BERLAKU HINGGA": ["BERLAKU HINGGA", "BERLAKUHINGGA"],
}

_LABEL_STRIP_PATTERN = re.compile(
    r"^(?:"
    r"NIK|NAMA|TEMPAT/TGL\.?\s*LAHIR|JENIS\s*KELAMIN|GOL\.?\s*DARAH|"
    r"ALAMAT|RT/RW|KEL/DESA|KELURAHAN|KECAMATAN|AGAMA|"
    r"STATUS\s*PERKAWINAN|PEKERJAAN|KEWARGANEGARAAN|BERLAKU\s*HINGGA"
    r")[\s:./]*",
    re.IGNORECASE,
)

_DATE_PATTERN = re.compile(r"\d{2}[-/]\d{2}[-/]\d{4}")
_RTRW_PATTERN = re.compile(r"\d{1,3}\s*/\s*\d{1,3}")


def _norm(text: str) -> str:
    return normalize_text(text)


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

            score = fuzz.partial_ratio(alias.upper(), text)
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
        candidates.append(item)

    candidates.sort(key=lambda b: b["x"])
    return candidates


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


def find_value_by_label(
        boxes,
        labels,
        threshold=72,
        y_tolerance=18,
):
    if isinstance(labels, str):
        labels = [labels]

    label_box = _find_label_box(boxes, labels, threshold=threshold)
    if label_box is None:
        return None

    label_text_norm = _norm(label_box["text"])

    for alias in labels:
        if alias.upper() in label_text_norm:
            inline = _extract_inline_value(label_text_norm, alias.upper())
            if inline:
                stripped = _strip_known_labels(inline)
                if stripped:
                    return clean_value(stripped)

    candidates = _collect_value_tokens(boxes, label_box, y_tolerance=y_tolerance)
    if not candidates:
        return None

    value = " ".join(item["text"] for item in candidates)
    return clean_value(_norm(value))


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
        candidates.append(item)

    candidates.sort(key=lambda b: (b["y"], b["x"]))
    return candidates


def _get_sorted_label_ys(boxes):
    label_ys = {}
    for field, aliases in KTP_FIELD_ALIASES.items():
        box = _find_label_box(boxes, aliases)
        if box:
            label_ys[field] = box["y"]
    return label_ys


def parse_ktp(boxes):

    data = KtpResponse()

    label_ys = _get_sorted_label_ys(boxes)

    def _next_label_y(field_name):
        current_y = label_ys.get(field_name)
        if current_y is None:
            return None
        next_y = None
        for field in KTP_FIELD_ORDER:
            y = label_ys.get(field)
            if y is not None and y > current_y:
                if next_y is None or y < next_y:
                    next_y = y
        return next_y

    for item in boxes:
        text = item["text"]
        nik_match = re.search(r"\d{16}", text)
        if nik_match:
            nik = validate_nik(nik_match.group())
            if nik:
                data.nik = nik
                break

    nama_box = _find_label_box(boxes, KTP_FIELD_ALIASES["NAMA"])
    if nama_box:
        nama_candidates = _collect_value_tokens(boxes, nama_box, y_tolerance=18)
        if nama_candidates:
            data.nama = clean_value(_norm(" ".join(i["text"] for i in nama_candidates)))

    ttl_box = _find_label_box(boxes, KTP_FIELD_ALIASES["TEMPAT/TGL LAHIR"])
    if ttl_box:
        ttl_norm = _norm(ttl_box["text"])

        date_in_label = _DATE_PATTERN.search(ttl_norm)
        if date_in_label:
            data.tanggal_lahir = date_in_label.group()
            before_date = ttl_norm[:date_in_label.start()]
            before_date = _strip_known_labels(before_date)
            before_date = before_date.replace(",", "").strip()
            if before_date:
                data.tempat_lahir = before_date
        else:
            ttl_candidates = _collect_value_tokens(boxes, ttl_box, y_tolerance=18)
            if ttl_candidates:
                ttl_val = _norm(" ".join(i["text"] for i in ttl_candidates))
                date_match = _DATE_PATTERN.search(ttl_val)
                if date_match:
                    data.tanggal_lahir = date_match.group()
                    tempat = ttl_val[:date_match.start()].replace(",", "").strip()
                    tempat = _strip_known_labels(tempat)
                    if tempat:
                        data.tempat_lahir = tempat

    if not data.tempat_lahir or not data.tanggal_lahir:
        for item in boxes:
            text_norm = _norm(item["text"])
            for keyword in ["TEMPAT/TGL LAHIR", "TEMPAT TGL LAHIR", "TEMPATTGL"]:
                if keyword in text_norm:
                    rest = _extract_inline_value(text_norm, keyword)
                    if rest:
                        date_m = _DATE_PATTERN.search(rest)
                        if date_m and not data.tanggal_lahir:
                            data.tanggal_lahir = date_m.group()
                            tempat = rest[:date_m.start()].replace(",", "").strip()
                            if tempat and not data.tempat_lahir:
                                data.tempat_lahir = tempat
                    break

    jk_box = _find_label_box(boxes, KTP_FIELD_ALIASES["JENIS KELAMIN"])
    if jk_box:
        jk_norm = _norm(jk_box["text"])
        jk_candidates = _collect_value_tokens(boxes, jk_box, y_tolerance=18)
        jk_combined = jk_norm + " " + _norm(" ".join(i["text"] for i in jk_candidates))
        jk_combined = jk_combined.upper()

        if "LAKI" in jk_combined:
            data.jenis_kelamin = match_gender("LAKI-LAKI")
        elif "PEREM" in jk_combined:
            data.jenis_kelamin = match_gender("PEREMPUAN")

    for item in boxes:
        text = _norm(item["text"])
        if "GOL" in text and "DARAH" in text:
            gol_match = re.search(r"(AB|A|B|O)\s*$", text)
            if gol_match:
                data.gol_darah = gol_match.group().strip()
                break
        elif re.search(r"GOL\.?\s*DARAH\s*(AB|A|B|O)", text):
            gol_match = re.search(r"GOL\.?\s*DARAH\s*(AB|A|B|O)", text)
            if gol_match:
                data.gol_darah = gol_match.group(1)
                break

    alamat_box = _find_label_box(boxes, KTP_FIELD_ALIASES["ALAMAT"])
    if alamat_box:
        rtrw_y = label_ys.get("RT/RW")
        alamat_candidates = _find_multi_row_value(
            boxes, alamat_box, next_label_y=rtrw_y, y_tolerance=18
        )
        if alamat_candidates:
            data.alamat = clean_value(_norm(" ".join(i["text"] for i in alamat_candidates)))

    rtrw_box = _find_label_box(boxes, KTP_FIELD_ALIASES["RT/RW"])
    if rtrw_box:
        rtrw_candidates = _collect_value_tokens(boxes, rtrw_box, y_tolerance=18)
        if rtrw_candidates:
            rtrw_val = _norm(" ".join(i["text"] for i in rtrw_candidates))
            rt_match = _RTRW_PATTERN.search(rtrw_val)
            if rt_match:
                data.rt_rw = rt_match.group().replace(" ", "")

    kel_box = _find_label_box(boxes, KTP_FIELD_ALIASES["KEL/DESA"])
    if kel_box:
        kec_y = label_ys.get("KECAMATAN")
        kel_candidates = _find_multi_row_value(
            boxes, kel_box, next_label_y=kec_y, y_tolerance=18
        )
        if kel_candidates:
            kel_val = clean_value(_norm(" ".join(i["text"] for i in kel_candidates)))
            data.kelurahan = kel_val

    kec_box = _find_label_box(boxes, KTP_FIELD_ALIASES["KECAMATAN"])
    if kec_box:
        agama_y = label_ys.get("AGAMA")
        kec_candidates = _find_multi_row_value(
            boxes, kec_box, next_label_y=agama_y, y_tolerance=18
        )
        if kec_candidates:
            kec_val = clean_value(_norm(" ".join(i["text"] for i in kec_candidates)))
            data.kecamatan = kec_val

    agama_box = _find_label_box(boxes, KTP_FIELD_ALIASES["AGAMA"])
    if agama_box:
        agama_candidates = _collect_value_tokens(boxes, agama_box, y_tolerance=18)
        if agama_candidates:
            agama_val = _norm(" ".join(i["text"] for i in agama_candidates))
            data.agama = match_religion(agama_val)
        else:
            agama_inline = _extract_inline_value(_norm(agama_box["text"]), "AGAMA")
            if agama_inline:
                data.agama = match_religion(agama_inline)

    status_box = _find_label_box(boxes, KTP_FIELD_ALIASES["STATUS PERKAWINAN"])
    if status_box:
        status_norm = _norm(status_box["text"])
        status_candidates = _collect_value_tokens(boxes, status_box, y_tolerance=18)
        status_combined = status_norm + " " + _norm(" ".join(i["text"] for i in status_candidates))

        status_val = re.sub(r".*PERKAWINAN", "", status_combined, flags=re.IGNORECASE)
        status_val = status_val.replace(":", "").strip()
        if status_val:
            data.status_perkawinan = match_marital_status(status_val)

    pekerjaan_box = _find_label_box(boxes, KTP_FIELD_ALIASES["PEKERJAAN"])
    if pekerjaan_box:
        pek_candidates = _collect_value_tokens(boxes, pekerjaan_box, y_tolerance=18)
        if pek_candidates:
            pek_val = _norm(" ".join(i["text"] for i in pek_candidates))
            data.pekerjaan = match_occupation(pek_val)

    for item in boxes:
        text = _norm(item["text"])
        if "KEWARGANEGARAAN" in text:
            if "WNI" in text:
                data.kewarganegaraan = match_nationality("WNI")
            elif "WNA" in text:
                data.kewarganegaraan = match_nationality("WNA")
            break

    if not data.kewarganegaraan:
        kewarga_box = _find_label_box(boxes, KTP_FIELD_ALIASES["KEWARGANEGARAAN"])
        if kewarga_box:
            kewarga_candidates = _collect_value_tokens(boxes, kewarga_box, y_tolerance=18)
            for candidate in kewarga_candidates:
                val = _norm(candidate["text"])
                if "WNI" in val:
                    data.kewarganegaraan = match_nationality("WNI")
                    break
                elif "WNA" in val:
                    data.kewarganegaraan = match_nationality("WNA")
                    break

    berlaku_box = _find_label_box(boxes, KTP_FIELD_ALIASES["BERLAKU HINGGA"])
    if berlaku_box:
        berlaku_y = berlaku_box["y"]
        berlaku_x = berlaku_box["x"]

        berlaku_candidates = []
        for item in boxes:
            if item["x"] <= berlaku_x:
                continue
            if abs(item["y"] - berlaku_y) > 20:
                continue
            berlaku_candidates.append(item)

        berlaku_norm = _norm(berlaku_box["text"])
        berlaku_candidates_norm = _norm(" ".join(i["text"] for i in berlaku_candidates))
        berlaku_combined = berlaku_norm + " " + berlaku_candidates_norm

        berlaku_upper = berlaku_combined.upper()
        if "SEUMUR HIDUP" in berlaku_upper or "SEUMURHIDUP" in berlaku_upper:
            data.berlaku_hingga = "SEUMUR HIDUP"
        else:
            date_match = _DATE_PATTERN.search(berlaku_combined)
            if date_match:
                data.berlaku_hingga = date_match.group()

    if not data.berlaku_hingga:
        for item in boxes:
            text = _norm(item["text"])
            if "BERLAKU" in text and "HINGGA" in text:
                if "SEUMUR" in text or "HIDUP" in text:
                    data.berlaku_hingga = "SEUMUR HIDUP"
                    break
                date_match = _DATE_PATTERN.search(text)
                if date_match:
                    data.berlaku_hingga = date_match.group()
                    break

    return data
