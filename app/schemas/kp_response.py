from pydantic import BaseModel


class KpResponse(BaseModel):
    """
    Response schema for Student ID Card (Kartu Pelajar) OCR extraction
    """

    # Personal Information
    nama: str | None = None
    tempat_lahir: str | None = None
    tanggal_lahir: str | None = None
    alamat: str | None = None

    # School Information
    nisn: str | None = None
    nis: str | None = None
    nama_sekolah: str | None = None
    alamat_sekolah: str | None = None
    kepala_sekolah: str | None = None

    # Academic Information
    tingkat: str | None = None
    kelas: str | None = None
    program_studi: str | None = None
    tahun_ajaran: str | None = None
    tahun_masuk: str | None = None

    # Additional Information
    jenis_kelamin: str | None = None
    agama: str | None = None
    pekerjaan_orang_tua: str | None = None

    # Card Information
    tanggal_terbit: str | None = None
    tanggal_berlaku_sampai: str | None = None