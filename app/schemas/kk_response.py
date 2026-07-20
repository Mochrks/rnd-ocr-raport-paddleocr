from pydantic import BaseModel, Field
from typing import List


class AnggotaKeluarga(BaseModel):

    no: int | None = None

    nama_lengkap: str | None = None
    nik: str | None = None
    jenis_kelamin: str | None = None

    tempat_lahir: str | None = None
    tanggal_lahir: str | None = None

    agama: str | None = None
    pendidikan: str | None = None
    jenis_pekerjaan: str | None = None
    golongan_darah: str | None = None

    status_perkawinan: str | None = None
    tanggal_perkawinan: str | None = None
    hubungan_keluarga: str | None = None

    kewarganegaraan: str | None = None

    no_paspor: str | None = None
    no_kitap: str | None = None

    ayah: str | None = None
    ibu: str | None = None


class KkResponse(BaseModel):

    nomor_kk: str | None = None

    kepala_keluarga: str | None = None

    alamat: str | None = None
    rt_rw: str | None = None

    desa_kelurahan: str | None = None
    kecamatan: str | None = None
    kabupaten_kota: str | None = None
    provinsi: str | None = None

    kode_pos: str | None = None

    tanggal_dikeluarkan: str | None = None

    anggota_keluarga: List[AnggotaKeluarga] = Field(
        default_factory=list
    )