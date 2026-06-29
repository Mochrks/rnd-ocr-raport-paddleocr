"""
Text Normalizer Helper
======================
Normalisasi teks OCR sebelum dilakukan mapping / fuzzy matching.

Operasi:
- lowercase
- trim whitespace
- hapus multiple spaces
- hapus dots, comma, dash berlebihan
- hapus simbol tidak perlu
- Pertahankan "B." prefix (B. Inggris, B. Indonesia)

Digunakan oleh mapping_engine dan ocr_service.
"""

import re


def normalize_text(text: str) -> str:
    """
    Normalisasi teks OCR untuk keperluan matching.
    
    Args:
        text: raw OCR text
        
    Returns:
        teks yang sudah dinormalisasi
    """
    if not text:
        return ""

    # 1. Lowercase
    t = text.lower()

    # 2. Hapus prefix nomor urut seperti "1.", "1.1.", "II.", "III."
    t = re.sub(r'^\s*(\d+\.)+\s*', '', t)
    t = re.sub(r'^\s*[ivxlcdm]+\.\s*', '', t)  # roman numeral prefix

    # 3. Hapus simbol tidak perlu: |, {, }, [, ], (, ), _, *, #, @, ^, ~, `
    t = re.sub(r'[|{}\[\]()_*#@^~`]', ' ', t)

    # 4. Preserve "b." prefix (for "B. Inggris", "B. Indonesia", etc.)
    # Replace "b." followed by space+letter with "b " (keep the intent)
    t = re.sub(r'\bb\.\s*(?=[a-z])', 'b ', t)

    # 5. Hapus dots lainnya
    t = re.sub(r'\.', ' ', t)

    # 6. Hapus comma dan dash berlebihan
    t = re.sub(r'[,\-]', ' ', t)

    # 7. Normalize & dan "dan" 
    t = re.sub(r'\s*&\s*', ' dan ', t)

    # 8. Hapus multiple spaces
    t = re.sub(r'\s+', ' ', t)

    # 9. Strip leading/trailing whitespace
    t = t.strip()

    return t


def normalize_for_score(text: str) -> str:
    """
    Normalisasi khusus untuk parsing angka score / KKM.
    Hapus semua karakter non-numerik kecuali titik dan koma.
    """
    if not text:
        return ""
    t = text.strip()
    # Ganti koma ke titik untuk desimal
    t = t.replace(',', '.')
    # Hapus karakter selain digit dan titik
    t = re.sub(r'[^\d.]', '', t)
    return t


def is_likely_subject_name(text: str) -> bool:
    """
    Cek apakah sebuah teks kemungkinan adalah nama mata pelajaran.
    Bukan angka murni, bukan simbol, mengandung huruf minimal 3 karakter.
    """
    if not text or len(text) < 3:
        return False
    # Harus mengandung huruf
    if not re.search(r'[A-Za-z]', text):
        return False
    # Jika hanya angka
    if re.match(r'^\d+$', text.strip()):
        return False
    return True
