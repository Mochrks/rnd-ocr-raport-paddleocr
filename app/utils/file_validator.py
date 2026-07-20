"""
Utilitas validasi file upload untuk semua endpoint OCR.
Memastikan file yang diunggah memenuhi batasan ekstensi dan ukuran.
"""

import os
from fastapi import UploadFile
from app.schemas.generic_response import GenericResponse, ErrorDetail

# Ekstensi yang diizinkan
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp", ".pdf"}

# Batas ukuran file: 2 MB
MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB
MAX_FILE_SIZE_LABEL = "2 MB"


async def validate_upload_file(file: UploadFile) -> GenericResponse | None:
    """
    Validasi file upload: nama, ekstensi, dan ukuran.

    Returns:
        GenericResponse error jika validasi gagal, atau None jika valid.
    """
    # 1. Nama file wajib ada
    if not file.filename:
        return GenericResponse(
            status="error",
            code=400,
            message="Nama file tidak boleh kosong",
            error=ErrorDetail(
                code="INVALID_FILE",
                message="File name cannot be empty"
            )
        )

    # 2. Validasi ekstensi
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        allowed_str = ", ".join(sorted(ALLOWED_EXTENSIONS))
        return GenericResponse(
            status="error",
            code=400,
            message=f"Format file tidak didukung: '{ext}'",
            error=ErrorDetail(
                code="UNSUPPORTED_FORMAT",
                message=f"Hanya format berikut yang diterima: {allowed_str}"
            )
        )

    # 3. Validasi ukuran file (baca seluruh konten lalu kembalikan ke awal)
    contents = await file.read()
    file_size = len(contents)
    await file.seek(0)  # reset pointer agar bisa dibaca ulang oleh handler

    if file_size > MAX_FILE_SIZE_BYTES:
        size_mb = round(file_size / (1024 * 1024), 2)
        return GenericResponse(
            status="error",
            code=413,
            message=f"Ukuran file terlalu besar: {size_mb} MB (maksimal {MAX_FILE_SIZE_LABEL})",
            error=ErrorDetail(
                code="FILE_TOO_LARGE",
                message=f"File size {size_mb} MB exceeds the maximum allowed size of {MAX_FILE_SIZE_LABEL}"
            )
        )

    return None  # valid
