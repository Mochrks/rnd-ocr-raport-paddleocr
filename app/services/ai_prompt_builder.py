"""
app/services/ai_prompt_builder.py
===================================
Build the system and user prompts sent to AI Vision models (DeepSeek, Qwen).

Design goals:
- Treat the AI model as a pure OCR engine, NOT a chatbot.
- Strictly instruct the model to read the page as-is without any hallucination.
- Output must be valid JSON only.
"""

from __future__ import annotations

SYSTEM_PROMPT = """\
Kamu adalah mesin OCR (Optical Character Recognition) untuk dokumen Indonesia.
Tugasmu adalah HANYA membaca teks yang ada di gambar dan mengekstrak datanya ke format JSON.

ATURAN WAJIB:
1. Baca SEMUA teks di halaman secara menyeluruh.
2. Pertahankan nilai PERSIS seperti yang tertulis di gambar. Jangan diubah, jangan diperbaiki.
3. DILARANG menerjemahkan teks ke bahasa lain.
4. DILARANG mengisi nilai yang kosong atau tidak terbaca. Gunakan null.
5. DILARANG berhalusinasi — jika tidak yakin, gunakan null.
6. JANGAN tambahkan penjelasan, komentar, atau teks di luar JSON.
7. Output HARUS berupa JSON valid. TANPA markdown, TANPA code block, TANPA prefix.
"""

USER_PROMPT_RAPORT = """\
Ekstrak data dari gambar raport sekolah Indonesia ini.

Output JSON WAJIB mengikuti struktur berikut PERSIS:
{
  "siswa": {
    "nama": "...",
    "nis": "...",
    "nisn": "...",
    "kelas": "...",
    "semester": "...",
    "tahun_ajaran": "...",
    "sekolah": "..."
  },
  "mata_pelajaran": [
    {
      "nama": "...",
      "nilai": <angka atau null>,
      "kkm": <angka atau null>,
      "predikat": "...",
      "deskripsi": "..."
    }
  ],
  "absensi": {
    "sakit": <angka atau null>,
    "izin": <angka atau null>,
    "alpa": <angka atau null>
  },
  "kepribadian": {
    "kelakuan": "...",
    "kerajinan": "...",
    "kerapihan": "..."
  },
  "catatan_wali": "...",
  "naik_kelas": "..."
}

PENTING:
- Semua field yang tidak ditemukan di gambar -> gunakan null.
- Nilai angka (nilai, kkm, sakit, izin, alpa) HARUS berupa number.
- Output hanya JSON.
"""

USER_PROMPT_KTP = """\
Ekstrak data dari gambar Kartu Tanda Penduduk (KTP) ini.

Output JSON WAJIB mengikuti struktur berikut PERSIS:
{
  "nik": "...",
  "nama": "...",
  "tempat_lahir": "...",
  "tanggal_lahir": "...",
  "jenis_kelamin": "...",
  "gol_darah": "...",
  "alamat": "...",
  "rt_rw": "...",
  "kelurahan": "...",
  "kecamatan": "...",
  "agama": "...",
  "status_perkawinan": "...",
  "pekerjaan": "...",
  "kewarganegaraan": "...",
  "berlaku_hingga": "..."
}

PENTING:
- Semua field yang tidak ditemukan di gambar -> gunakan null.
- Output hanya JSON.
"""

USER_PROMPT_KK = """\
Ekstrak data dari gambar Kartu Keluarga (KK) ini.

Output JSON WAJIB mengikuti struktur berikut PERSIS:
{
  "nomor_kk": "...",
  "kepala_keluarga": "...",
  "alamat": "...",
  "rt_rw": "...",
  "desa_kelurahan": "...",
  "kecamatan": "...",
  "kabupaten_kota": "...",
  "provinsi": "...",
  "kode_pos": "...",
  "tanggal_dikeluarkan": "...",
  "anggota_keluarga": [
    {
      "no": 1,
      "nama_lengkap": "...",
      "nik": "...",
      "jenis_kelamin": "...",
      "tempat_lahir": "...",
      "tanggal_lahir": "...",
      "agama": "...",
      "pendidikan": "...",
      "jenis_pekerjaan": "...",
      "golongan_darah": "...",
      "status_perkawinan": "...",
      "tanggal_perkawinan": "...",
      "hubungan_keluarga": "...",
      "kewarganegaraan": "...",
      "no_paspor": "...",
      "no_kitap": "...",
      "ayah": "...",
      "ibu": "..."
    }
  ]
}

PENTING:
- Ekstrak seluruh anggota keluarga di dalam tabel.
- Semua field yang tidak ditemukan di gambar -> gunakan null.
- Output hanya JSON.
"""

USER_PROMPT_AKTA = """\
Ekstrak data dari gambar Kutipan Akta Kelahiran ini.

Output JSON WAJIB mengikuti struktur berikut PERSIS:
{
  "nomor_akta": "...",
  "nama_anak": "...",
  "jenis_kelamin": "...",
  "tempat_lahir": "...",
  "tanggal_lahir": "...",
  "nama_ayah": "...",
  "nama_ibu": "..."
}

PENTING:
- Semua field yang tidak ditemukan di gambar -> gunakan null.
- Output hanya JSON.
"""

USER_PROMPT_KP = """\
Ekstrak data dari gambar Kartu Pelajar ini.

Output JSON WAJIB mengikuti struktur berikut PERSIS:
{
  "nama": "...",
  "tempat_lahir": "...",
  "tanggal_lahir": "...",
  "alamat": "...",
  "nisn": "...",
  "nis": "...",
  "nama_sekolah": "...",
  "alamat_sekolah": "...",
  "kepala_sekolah": "...",
  "tingkat": "...",
  "kelas": "...",
  "program_studi": "...",
  "tahun_ajaran": "...",
  "tahun_masuk": "...",
  "jenis_kelamin": "...",
  "agama": "...",
  "pekerjaan_orang_tua": "...",
  "tanggal_terbit": "...",
  "tanggal_berlaku_sampai": "..."
}

PENTING:
- Semua field yang tidak ditemukan di gambar -> gunakan null.
- Output hanya JSON.
"""

PROMPTS = {
    "raport": USER_PROMPT_RAPORT,
    "ktp": USER_PROMPT_KTP,
    "kk": USER_PROMPT_KK,
    "akta": USER_PROMPT_AKTA,
    "kp": USER_PROMPT_KP,
}


def build_messages(doc_type: str = "raport") -> list[dict]:
    user_prompt = PROMPTS.get(doc_type.lower(), USER_PROMPT_RAPORT)
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def build_vision_messages(
    image_base64: str,
    mime_type: str = "image/png",
    doc_type: str = "raport",
) -> list[dict]:
    user_prompt = PROMPTS.get(doc_type.lower(), USER_PROMPT_RAPORT)
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{image_base64}",
                    },
                },
                {
                    "type": "text",
                    "text": user_prompt,
                },
            ],
        },
    ]
