from app.services.extractors.kk_table_extractor import (
    group_rows,
    join_row_text
)
from app.utils.normalizer import (
    normalize_text
)
import re

def clean_header_value(value):
    if value is None:
        return None
    value = value.replace(":", "").strip()
    if value in ["-", "-/", "/", ""]:
        return None
    return value

def extract_header_data(boxes):

    result = {
        "kepala_keluarga": None,
        "alamat": None,
        "rt_rw": None,
        "kode_pos": None,
        "desa_kelurahan": None,
        "kecamatan": None,
        "kabupaten_kota": None,
        "provinsi": None
    }
    
    if not boxes:
        return result

    # Hitung lebar dokumen maksimum secara dinamis
    max_x = max(box["x"] for box in boxes)
    mid_x = max_x / 2.0

    # Gunakan toleransi dinamis untuk grouping baris header
    max_y = max(box["y"] for box in boxes)
    tolerance = max(10, int(max_y * 0.008))

    rows = group_rows(boxes, tolerance=tolerance)

    for y in sorted(rows):
        row = rows[y]
        row_text = join_row_text(row)
        upper = normalize_text(row_text.upper())

        if upper is None:
            continue

        # Bagi box pada baris ini menjadi kolom kiri dan kanan secara spasial
        left_boxes = sorted([b for b in row if b["x"] < mid_x], key=lambda b: b["x"])
        right_boxes = sorted([b for b in row if b["x"] >= mid_x], key=lambda b: b["x"])

        left_text = join_row_text(left_boxes)
        right_text = join_row_text(right_boxes)

        left_upper = normalize_text(left_text.upper()) if left_text else ""
        right_upper = normalize_text(right_text.upper()) if right_text else ""

        # ============================================================
        # KOLOM KIRI (Kepala Keluarga, Alamat, RT/RW, Kode Pos)
        # ============================================================
        
        if "NAMA KEPALA KELUARGA" in left_upper:
            # Cari kata kunci dan ambil semua box setelah kata kunci tersebut di kolom kiri
            for idx, box in enumerate(left_boxes):
                box_txt = normalize_text(box["text"].upper())
                if "NAMA KEPALA KELUARGA" in box_txt or "KEPALA KELUARGA" in box_txt:
                    val_boxes = left_boxes[idx+1:]
                    val = join_row_text(val_boxes)
                    result["kepala_keluarga"] = clean_header_value(normalize_text(val))
                    break

        elif "ALAMAT" in left_upper:
            for idx, box in enumerate(left_boxes):
                box_txt = normalize_text(box["text"].upper())
                if "ALAMAT" in box_txt:
                    val_boxes = left_boxes[idx+1:]
                    val = join_row_text(val_boxes)
                    result["alamat"] = clean_header_value(normalize_text(val))
                    break

        elif "RT/RW" in left_upper:
            for idx, box in enumerate(left_boxes):
                box_txt = normalize_text(box["text"].upper())
                if "RT/RW" in box_txt or "RT" in box_txt:
                    val_boxes = left_boxes[idx+1:]
                    val = join_row_text(val_boxes)
                    result["rt_rw"] = clean_header_value(normalize_text(val))
                    break

        elif "KODE POS" in left_upper:
            for idx, box in enumerate(left_boxes):
                box_txt = normalize_text(box["text"].upper())
                if "KODE POS" in box_txt or "KODE" in box_txt or "POS" in box_txt:
                    val_boxes = left_boxes[idx+1:]
                    val = join_row_text(val_boxes)
                    result["kode_pos"] = clean_header_value(normalize_text(val))
                    break

        # ============================================================
        # KOLOM KANAN (Desa/Kelurahan, Kecamatan, Kabupaten/Kota, Provinsi)
        # ============================================================
        
        if "DESA/KELURAHAN" in right_upper or "KELURAHAN" in right_upper:
            for idx, box in enumerate(right_boxes):
                box_txt = normalize_text(box["text"].upper())
                if "DESA/KELURAHAN" in box_txt or "KELURAHAN" in box_txt or "DESA" in box_txt:
                    val_boxes = right_boxes[idx+1:]
                    val = join_row_text(val_boxes)
                    result["desa_kelurahan"] = clean_header_value(normalize_text(val))
                    break

        elif "KECAMATAN" in right_upper or "KECAMAIAN" in right_upper:
            for idx, box in enumerate(right_boxes):
                box_txt = normalize_text(box["text"].upper())
                if "KECAMATAN" in box_txt or "KECAMAIAN" in box_txt or "KEC" in box_txt:
                    val_boxes = right_boxes[idx+1:]
                    val = join_row_text(val_boxes)
                    result["kecamatan"] = clean_header_value(normalize_text(val))
                    break

        elif "KABUPATEN/KOTA" in right_upper or "KABUPATEN" in right_upper or "KOTA" in right_upper:
            for idx, box in enumerate(right_boxes):
                box_txt = normalize_text(box["text"].upper())
                if "KABUPATEN" in box_txt or "KOTA" in box_txt or "KAB" in box_txt:
                    val_boxes = right_boxes[idx+1:]
                    val = join_row_text(val_boxes)
                    result["kabupaten_kota"] = clean_header_value(normalize_text(val))
                    break

        elif "PROVINSI" in right_upper:
            for idx, box in enumerate(right_boxes):
                box_txt = normalize_text(box["text"].upper())
                if "PROVINSI" in box_txt or "PROV" in box_txt:
                    val_boxes = right_boxes[idx+1:]
                    val = join_row_text(val_boxes)
                    result["provinsi"] = clean_header_value(normalize_text(val))
                    break

    return result
