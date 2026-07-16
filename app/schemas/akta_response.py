from pydantic import BaseModel


class AktaResponse(BaseModel):

    nomor_akta: str | None = None

    nama_anak: str | None = None

    jenis_kelamin: str | None = None

    tempat_lahir: str | None = None

    tanggal_lahir: str | None = None

    nama_ayah: str | None = None

    nama_ibu: str | None = None