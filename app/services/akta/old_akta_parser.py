import re

from app.schemas.akta_response import AktaResponse

from app.services.akta.akta_row_extractor import (
    group_rows,
    join_rows
)

from app.utils.normalizer import normalize_text
from app.utils.text_utils import clean_value


def parse_old_akta(raw_boxes):

    data = AktaResponse()

    rows = group_rows(raw_boxes)
    lines = join_rows(rows)
    text = " ".join(lines)
    text = normalize_text(text)

    #
    # NOMOR AKTA
    #
    nomor_match = re.search(r"\d+\/[A-Z]{2,5}\/\d{4}", text)
    if nomor_match:
        data.nomor_akta = nomor_match.group()

    #
    # JENIS KELAMIN
    #
    if "PEREMPUAN" in text:
        data.jenis_kelamin = "PEREMPUAN"
    elif "LAKI-LAKI" in text:
        data.jenis_kelamin = "LAKI-LAKI"

    #
    # TEMPAT LAHIR
    #
    tempat_patterns = [
        r"TERNYATA.*?DI\s+(.+?)\s+PADA",
        r"BAHWA DI\s+(.+?)\s+PADA",
        r"DI\s+(.+?)\s+PADA TANGGAL",
    ]

    for pattern in tempat_patterns:
        match = re.search(pattern, text)
        if match:
            data.tempat_lahir = clean_value(match.group(1).title())
            break

    #
    # NAMA ANAK
    #
    nama_patterns = [
        r"TELAH LAHIR\s+(.+?)\s+JENIS KELAMIN",
        r"TELAH LAHIR\s+(.+?)\s+ANAK",
        r"TELAH LAHIR\s+(.+?)\s+DARI",
    ]

    for pattern in nama_patterns:
        match = re.search(pattern, text)
        if match:
            nama = clean_value(match.group(1))
            nama = nama.replace(",", "").title()
            data.nama_anak = nama
            break

    #
    # AYAH
    #
    ayah_patterns = [
        r"DARI SUAMI\s+(.+?)\s+DAN ISTRI",
        r"DARI SUAMI\s+(.+?)\s+ISTRI",
        r"DARI SUAMI\s+(.+?)\s+BERNAMA",
    ]

    for pattern in ayah_patterns:
        match = re.search(pattern, text)
        if match:
            ayah = clean_value(match.group(1))
            ayah = ayah.replace(",", "").title()
            data.nama_ayah = ayah
            break

    #
    # IBU
    #
    ibu_patterns = [
        r"DAN ISTRI\s+(.+?)\s+BERDASARKAN",
        r"DAN ISTRI\s+(.+?)\s+TENTANG",
        r"DAN ISTRI\s+(.+?)\s+KUTIPAN",
        r"DAN ISTRI\s+(.+?)\s+SESUAI",
    ]

    for pattern in ibu_patterns:
        match = re.search(pattern, text)
        if match:
            ibu = clean_value(match.group(1))
            ibu = ibu.replace(",", "").title()
            data.nama_ibu = ibu
            break

    #
    # TANGGAL LAHIR
    #
    tanggal_match = re.search(r"PADA TANGGAL\s+(.+?)\s+TELAH LAHIR", text)
    if tanggal_match:
        data.tanggal_lahir = clean_value(tanggal_match.group(1).title())

    return data
