import re

from app.schemas.kk_response import AnggotaKeluarga
from app.utils.normalizer import normalize_text

from app.fuzzy.blood_type_matcher import match_blood_type
from app.fuzzy.education_matcher import match_education
from app.fuzzy.family_relation_matcher import match_family_relation
from app.fuzzy.gender_matcher import match_gender
from app.fuzzy.marital_status_matcher import match_marital_status
from app.fuzzy.nationality_matcher import match_nationality
from app.fuzzy.occupation_matcher import match_occupation
from app.fuzzy.religion_matcher import match_religion


def group_rows(boxes, tolerance=8):
    rows = []
    sorted_boxes = sorted(boxes, key=lambda box: (box["y"], box["x"]))

    for box in sorted_boxes:
        y = box["y"]
        found = False

        for row in rows:
            avg_y = sum(item["y"] for item in row) / len(row)
            if abs(avg_y - y) <= tolerance:
                row.append(box)
                found = True
                break

        if not found:
            rows.append([box])

    result = {}
    for row in rows:
        avg_y = int(sum(item["y"] for item in row) / len(row))
        result[avg_y] = sorted(row, key=lambda item: item["x"])

    return result


def join_row_text(row):
    if not row:
        return ""
    cols = sorted(row, key=lambda x: x["x"])
    return " ".join(item["text"].strip() if item.get("text") else "" for item in cols)


def find_row_by_keywords(rows, keywords):
    for y in sorted(rows):
        row_text = normalize_text(join_row_text(rows[y]).upper())
        if row_text is None:
            continue
        if all(keyword in row_text for keyword in keywords):
            return rows[y]
    return None


def row_has_content(text):
    return bool(text and text.strip() and text.strip() != "-" and text.strip() != ".")


def is_nomor_anggota(text):
    if text is None:
        return False
    return bool(re.match(r'^\d+\s*', text.strip()))


def extract_nomor(text):
    if text is None:
        return None
    match = re.match(r'^(\d+)', text.strip())
    return int(match.group(1)) if match else None


def extract_nik(text):
    if text is None:
        return None
    match = re.search(r'\d{16}', text)
    return match.group() if match else None


def extract_tanggal(text):
    if text is None:
        return None
    match = re.search(r'\d{2}-\d{2}-\d{4}', text)
    return match.group() if match else None


def extract_table1_blocks(boxes):
    if not boxes:
        return []
    max_y = max((box["y"] for box in boxes), default=1300)
    tolerance = max(12, int(max_y * 0.008))
    rows = group_rows(boxes, tolerance=tolerance)
    blocks = []
    current_block = []
    sudah_ada_nik = False
    mulai = False

    for y in sorted(rows):
        row_text = join_row_text(rows[y])
        upper = normalize_text(row_text.upper())
        if upper is None:
            continue

        # Trigger: header bisa dalam satu baris (PDF) ATAU terpecah ke dua baris (gambar).
        # Cukup salah satu kata kunci header hadir untuk mulai membaca data.
        is_header_row = (
            ("NAMA LENGKAP" in upper and "NIK" in upper)  # satu baris (PDF)
            or ("NAMA LENGKAP" in upper and not re.search(r'\d{16}', upper))  # baris pertama header split
            or ("NO" in upper and "NIK" in upper and not re.search(r'\d{16}', upper))  # baris kedua header split
        )
        if is_header_row:
            mulai = True
            continue

        if not mulai:
            continue

        # Abaikan baris header kolom kedua yang mungkin terdeteksi di Table 1
        header_keywords = ["KELAMIN", "LAHIR", "DARAH", "TEMPAT", "AGAMA", "PENDIDIKAN", "PEKERJAAN", "GOLONGAN"]
        if any(kw in upper for kw in header_keywords) and not re.search(r'\d{16}', upper):
            continue

        if "STATUS HUBUNGAN" in upper or "STATUS PERKAWINAN" in upper:
            break

        if re.fullmatch(r'[\d\-\.\(\)\s]+', upper):
            continue

        nik_match = re.search(r'\d{16}', upper)
        if nik_match:
            if sudah_ada_nik and current_block:
                blocks.append(current_block)
                current_block = []
            sudah_ada_nik = True

        current_block.append(row_text)

    if current_block:
        blocks.append(current_block)

    return blocks


def extract_table2_blocks(boxes):
    rows = group_rows(boxes, tolerance=15)
    blocks = []
    current_block = []
    mulai = False

    for y in sorted(rows):
        row_text = join_row_text(rows[y])
        upper = normalize_text(row_text.upper())
        if upper is None:
            continue

        # Menggunakan fuzzy match status perkawinan sebagai trigger pembacaan tabel bawah
        status_perkawinan = match_marital_status(upper)
        if status_perkawinan:
            mulai = True

        if not mulai:
            continue

        if "DIKELUARKAN TANGGAL" in upper or "KEPALA DINAS" in upper:
            break

        if re.fullmatch(r'[\d\-\.\(\)\s]+', upper):
            continue

        if status_perkawinan:
            if current_block:
                blocks.append(current_block)
                current_block = []

        current_block.append(row_text)

    if current_block:
        blocks.append(current_block)

    return blocks


def partition_table_boxes(boxes):
    """Pisahkan boxes secara spasial menjadi Tabel 1 dan Tabel 2
    berdasarkan koordinat Y yang dideteksi secara dinamis dari konten dokumen.
    Ini memastikan data antar-tabel tidak saling mencemari satu sama lain."""
    y_divider = None
    y_header2 = None
    y_footer = None

    for box in boxes:
        text = normalize_text(box.get("text", ""))
        if not text:
            continue
        t = text.upper()

        # Batas atas Tabel 2: baris header status/hubungan/nama orang tua
        if ("STATUS PERKAWINAN" in t or "STATUS HUBUNGAN" in t
                or "NAMA ORANG TUA" in t or "DOKUMEN IMGRASI" in t
                or "DOKUMEN IMIGRASI" in t):
            y = box["y"]
            if y_divider is None or y < y_divider:
                y_divider = y

        # Batas bawah header Tabel 2: baris nomor kolom (10), (11), ..., (17)
        if re.search(r'\(\d+\)', t) or t in ["14)", "15)", "16)", "17)"]:
            y = box["y"]
            if (y_divider is not None and y > y_divider
                    and y < y_divider + 100
                    and (y_header2 is None or y > y_header2)):
                y_header2 = y

        # Batas footer: baris tanda tangan / tanggal dikeluarkan
        if ("DIKELUARKAN TANGGAL" in t or "KEPALA DINAS" in t
                or "LEMBAR" in t or "PENCATATAN SIPIL" in t):
            y = box["y"]
            if y_footer is None or y < y_footer:
                y_footer = y

    # Fallback jika marker tidak ditemukan
    # Gunakan persentase dari Y maksimum dokumen agar scale-invariant
    max_y = max((box["y"] for box in boxes), default=1300)
    if y_divider is None:
        y_divider = int(max_y * 0.58)   # ~58% dari tinggi dokumen
    if y_header2 is None:
        y_header2 = y_divider + int(max_y * 0.06)  # +6% toleransi header
    if y_footer is None:
        y_footer = int(max_y * 0.92)    # ~92% dari tinggi dokumen

    # Tabel 1: semua box DI ATAS baris header Tabel 2
    table1_boxes = [box for box in boxes if box["y"] < y_divider]
    # Tabel 2: box ANTARA baris nomor kolom dan footer
    table2_boxes = [box for box in boxes if y_header2 < box["y"] < y_footer]

    return table1_boxes, table2_boxes


def extract_table1_data(boxes):
    table1_boxes, _ = partition_table_boxes(boxes)
    blocks = extract_table1_blocks(table1_boxes)
    hasil = []
    nomor = 1

    for rows in blocks:
        anggota = AnggotaKeluarga()
        anggota.no = nomor

        text = normalize_text(" ".join(rows))
        if text is None:
            continue

        anggota.nik = extract_nik(text)

        # Menggunakan fuzzy matcher untuk Jenis Kelamin
        anggota.jenis_kelamin = match_gender(text)

        # ======================
        # TEMPAT LAHIR & TANGGAL LAHIR
        # ======================
        anggota.tanggal_lahir = extract_tanggal(text)
        tempat_lahir = None

        if anggota.jenis_kelamin and anggota.tanggal_lahir:
            jk_pos = text.find(anggota.jenis_kelamin)
            tl_pos = text.find(anggota.tanggal_lahir)
            if jk_pos != -1 and tl_pos != -1 and jk_pos < tl_pos:
                middle_text = text[jk_pos + len(anggota.jenis_kelamin) : tl_pos].strip()
                middle_text = re.sub(r'^[\d\s\W]+', '', middle_text)
                if middle_text:
                    tempat_lahir = normalize_text(middle_text)

        anggota.tempat_lahir = tempat_lahir

        # Menggunakan Fuzzy Matchers untuk data entitas
        anggota.agama = match_religion(text)
        anggota.pendidikan = match_education(text)
        anggota.jenis_pekerjaan = match_occupation(text)
        anggota.golongan_darah = match_blood_type(text)

        if anggota.nik:
            nama_match = re.search(rf'([A-Z\s\.]+?)\s*{anggota.nik}', text)
            if nama_match:
                anggota.nama_lengkap = normalize_text(nama_match.group(1))

        hasil.append(anggota)
        nomor += 1

    return hasil


def compute_column_boundaries(boxes):
    """Hitung batas kolom X secara dinamis dari lebar dokumen.
    Ini memastikan parser bekerja di semua resolusi (gambar kamera, scan, PDF rendering).
    
    Batas kolom KK Tabel 2 (dalam persentase lebar dokumen):
    ┌─────────┬───────────┬──────────┬──────────┬──────────┬──────────┬──────────┐
    │ Status  │ Tgl Kaw.  │ Hubungan │   KWN    │ No.Psp   │ No.Kit   │  Ayah   │  Ibu   │
    │  0-13%  │  13-20%   │  20-30%  │  30-38%  │  38-46%  │  46-54%  │  54-72% │  72%+  │
    └─────────┴───────────┴──────────┴──────────┴──────────┴──────────┴──────────┘
    """
    if not boxes:
        return None

    # Lebar dokumen = X maksimum dari seluruh boxes
    max_x = max(box["x"] for box in boxes)
    if max_x == 0:
        return None

    return {
        "max_x": max_x,
        "status_end":    max_x * 0.13,   # 0% – 13%
        "tanggal_start": max_x * 0.13,   # 13% – 20%
        "tanggal_end":   max_x * 0.20,
        "hubungan_start":max_x * 0.20,   # 20% – 30%
        "hubungan_end":  max_x * 0.30,
        "kwn_start":     max_x * 0.30,   # 30% – 38%
        "kwn_end":       max_x * 0.38,
        "paspor_start":  max_x * 0.38,   # 38% – 46%
        "paspor_end":    max_x * 0.46,
        "kitap_start":   max_x * 0.46,   # 46% – 54%
        "kitap_end":     max_x * 0.54,
        "ayah_start":    max_x * 0.54,   # 54% – 72%
        "ayah_end":      max_x * 0.72,
        "ibu_start":     max_x * 0.72,   # 72% ke kanan
    }


def extract_table2_data(boxes):
    """Ekstrak data Tabel 2 (status perkawinan, hubungan keluarga, nama orang tua)
    menggunakan: 
    - Partisi Y dinamis untuk mencegah kontaminasi dari Tabel 1 dan footer.
    - Batas kolom X berbasis PERSENTASE lebar dokumen (scale-invariant),
      sehingga bekerja sama baiknya untuk gambar kamera, scan, maupun PDF."""
    _, table2_boxes = partition_table_boxes(boxes)
    max_y = max((box["y"] for box in boxes), default=1300)
    tolerance = max(15, int(max_y * 0.012))
    rows = group_rows(table2_boxes, tolerance=tolerance)
    hasil = []

    # Hitung batas kolom dari semua boxes (bukan hanya table2) agar
    # lebar dokumen terhitung secara akurat dari elemen paling kanan
    col = compute_column_boundaries(boxes)
    if col is None:
        return []

    for y in sorted(rows):
        row = rows[y]
        row_text = join_row_text(row)
        upper = normalize_text(row_text.upper())
        if not upper:
            continue

        # ==================
        # STATUS PERKAWINAN (kolom kiri, 0% – 13% lebar dokumen)
        # Harus ada untuk dianggap baris data yang valid
        # ==================
        status_boxes = [b for b in row if b["x"] < col["status_end"]]
        status_text = join_row_text(status_boxes)
        status_perkawinan = match_marital_status(status_text)
        if not status_perkawinan:
            continue  # baris kosong / header / footer — lewati

        # ==================
        # TANGGAL PERKAWINAN (13% – 20%)
        # ==================
        tgl_boxes = [b for b in row if col["tanggal_start"] <= b["x"] < col["tanggal_end"]]
        tanggal_perkawinan = normalize_text(join_row_text(tgl_boxes))
        if tanggal_perkawinan in ["-", ""]:
            tanggal_perkawinan = None

        # ==================
        # STATUS HUBUNGAN KELUARGA (20% – 30%)
        # ==================
        hubungan_boxes = [b for b in row if col["hubungan_start"] <= b["x"] < col["hubungan_end"]]
        hubungan_text = join_row_text(hubungan_boxes)
        hubungan_keluarga = match_family_relation(hubungan_text)

        # ==================
        # KEWARGANEGARAAN (30% – 38%)
        # ==================
        kwn_boxes = [b for b in row if col["kwn_start"] <= b["x"] < col["kwn_end"]]
        kewarganegaraan = match_nationality(join_row_text(kwn_boxes))

        # ==================
        # NO. PASPOR (38% – 46%)
        # ==================
        paspor = normalize_text(join_row_text([b for b in row if col["paspor_start"] <= b["x"] < col["paspor_end"]]))
        if paspor in ["-", ""]:
            paspor = None

        # ==================
        # NO. KITAP (46% – 54%)
        # ==================
        kitap = normalize_text(join_row_text([b for b in row if col["kitap_start"] <= b["x"] < col["kitap_end"]]))
        if kitap in ["-", ""]:
            kitap = None

        # ==================
        # NAMA AYAH (54% – 72%)
        # ==================
        ayah = normalize_text(join_row_text([b for b in row if col["ayah_start"] <= b["x"] < col["ayah_end"]]))
        if ayah in ["-", ""]:
            ayah = None

        # ==================
        # NAMA IBU (72% ke kanan)
        # ==================
        ibu = normalize_text(join_row_text([b for b in row if b["x"] >= col["ibu_start"]]))
        if ibu in ["-", ""]:
            ibu = None

        hasil.append({
            "status_perkawinan": status_perkawinan,
            "tanggal_perkawinan": tanggal_perkawinan,
            "hubungan_keluarga": hubungan_keluarga,
            "kewarganegaraan": kewarganegaraan,
            "no_paspor": paspor,
            "no_kitap": kitap,
            "ayah": ayah,
            "ibu": ibu,
        })

    return hasil


def merge_anggota_dan_detail(boxes):
    anggota_list = extract_table1_data(boxes)
    detail_list = extract_table2_data(boxes)

    for i, anggota in enumerate(anggota_list):
        if i >= len(detail_list):
            break

        detail = detail_list[i]
        anggota.status_perkawinan  = detail.get("status_perkawinan")
        anggota.tanggal_perkawinan = detail.get("tanggal_perkawinan")
        anggota.hubungan_keluarga  = detail.get("hubungan_keluarga")
        anggota.kewarganegaraan    = detail.get("kewarganegaraan")
        anggota.no_paspor          = detail.get("no_paspor")
        anggota.no_kitap           = detail.get("no_kitap")
        anggota.ayah               = detail.get("ayah")
        anggota.ibu                = detail.get("ibu")

    return anggota_list