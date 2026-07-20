from pydantic import BaseModel


class KtpResponse(BaseModel):

    nik: str | None = None
    nama: str | None = None
    tempat_lahir: str | None = None
    tanggal_lahir: str | None = None
    jenis_kelamin: str | None = None
    gol_darah: str | None = None
    alamat: str | None = None
    rt_rw: str | None = None
    kelurahan: str | None = None
    kecamatan: str | None = None
    agama: str | None = None
    status_perkawinan: str | None = None
    pekerjaan: str | None = None
    kewarganegaraan: str | None = None
    berlaku_hingga: str | None = None