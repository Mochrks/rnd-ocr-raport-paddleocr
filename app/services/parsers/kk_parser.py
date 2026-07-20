import re

from app.schemas.kk_response import (
    KkResponse
)

from app.services.extractors.kk_table_extractor import (
    merge_anggota_dan_detail,
    group_rows,
    join_row_text
)

from app.utils.normalizer import (
    normalize_text
)

from app.services.extractors.kk_header_extractor import (
    extract_header_data
)

def extract_field(
        text,
        keyword
):
    
    if text is None:
        return None

    # Match pattern: keyword followed by colon and value
    match = re.search(

        rf'{keyword}\s*:\s*([^:]+?)(?:\s+(?:' + '|'.join(['Nama', 'Alamat', 'RT', 'RW', 'Kode', 'Desa', 'Kecamatan', 'Kabupaten', 'Provinsi', 'Kelurahan']) + r'))?$',

        text,

        flags=re.IGNORECASE

    )

    if match:
        
        group_val = match.group(1)
        
        if group_val is None:
            return None

        return group_val.strip()
    
    # Fallback: try to extract value after keyword (without colon requirement)
    match2 = re.search(
        rf'{keyword}\s*:?\s*([^:]+)$',
        text,
        flags=re.IGNORECASE
    )
    
    if match2:
        group_val = match2.group(1)
        
        if group_val is None:
            return None
            
        value = group_val.strip()
        
        # Remove known labels
        labels = ['Alamat', 'Kecamaian', 'Kecamatan', 'Provinsi', 'Kabupaten', 'Kota', 'Desa', 'Kelurahan', 'RT', 'RW', 'Kode', 'Pos']
        for label in labels:
            if value.upper().startswith(label.upper()):
                value = value[len(label):].strip()
                if value.startswith(':'):
                    value = value[1:].strip()
        
        return value if value else None

    return None

def clean_value(
        value
):

    if value is None:

        return None

    return (
        value
        .replace(":", "")
        .strip()
    )

def set_if_empty(
        obj,
        field_name,
        value
):

    if value is None:

        return

    if getattr(
            obj,
            field_name
    ) is None:

        setattr(
            obj,
            field_name,
            value
        )

def parse_kk(boxes):

    data = KkResponse()
    
    header = extract_header_data(
        boxes
    )

    data.kepala_keluarga = header.get(
        "kepala_keluarga"
    )

    data.alamat = header.get(
        "alamat"
    )

    data.rt_rw = header.get(
        "rt_rw"
    )

    data.kode_pos = header.get(
        "kode_pos"
    )

    data.desa_kelurahan = header.get(
        "desa_kelurahan"
    )

    data.kecamatan = header.get(
        "kecamatan"
    )

    data.kabupaten_kota = header.get(
        "kabupaten_kota"
    )

    data.provinsi = header.get(
        "provinsi"
    )

    rows = group_rows(
        boxes,
        tolerance=40
    )

    for y in sorted(rows):

        row = rows[y]
        row_text = join_row_text(row)
        row_upper = normalize_text(row_text.upper())

        if row_upper is None:
            continue

        # ======================
        # NOMOR KK
        # ======================

        if data.nomor_kk is None:
            nomor_kk = re.search(
                r"\d{16}",
                row_text
            )
            if nomor_kk:
                data.nomor_kk = nomor_kk.group()

        if "DIKELUARKAN TANGGAL" in row_upper:
            tanggal = re.search(
                r"\d{2}-\d{2}-\d{4}",
                row_text
            )
            if tanggal:
                data.tanggal_dikeluarkan = tanggal.group()

    data.anggota_keluarga = (
        merge_anggota_dan_detail(
            boxes
        )
    )

    return data
