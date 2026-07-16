"""
app/services/ai_prompt_builder.py
===================================
Build the system and user prompts sent to AI Vision models (DeepSeek, Qwen).

Design goals:
- Treat the AI model as a pure OCR engine, NOT a chatbot.
- Strictly instruct the model to read the page as-is without any
  hallucination, translation, correction, or gap-filling.
- Output must be valid JSON only — no markdown, no explanation.

The prompts are intentionally verbose to maximize extraction accuracy
and minimize model "helpfulness" that would corrupt the data.
"""

from __future__ import annotations

SYSTEM_PROMPT = """\
Kamu adalah mesin OCR (Optical Character Recognition) untuk raport sekolah Indonesia.
Tugasmu adalah HANYA membaca teks yang ada di gambar dan mengekstrak datanya ke format JSON.

ATURAN WAJIB:
1. Baca SEMUA teks di halaman secara menyeluruh, termasuk tabel, header, dan catatan kecil.
2. Pertahankan nilai PERSIS seperti yang tertulis di gambar. Jangan diubah, jangan diperbaiki.
3. DILARANG menerjemahkan teks ke bahasa lain.
4. DILARANG memperbaiki typo atau salah ketik.
5. DILARANG memperbaiki angka yang tampak salah.
6. DILARANG mengisi nilai yang kosong atau tidak terbaca. Gunakan null.
7. DILARANG berhalusinasi — jika tidak yakin, gunakan null.
8. JANGAN tambahkan penjelasan, komentar, atau teks di luar JSON.
9. Output HARUS berupa JSON valid. TANPA markdown, TANPA code block, TANPA prefix.
10. Pertahankan layout tabel — urutan baris mata pelajaran harus sesuai urutan di gambar.
"""

USER_PROMPT_TEMPLATE = """\
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
- Semua field yang tidak ditemukan di gambar → gunakan null (bukan string kosong).
- Nilai angka (nilai, kkm, sakit, izin, alpa) HARUS berupa number, bukan string.
- Jika ada beberapa halaman, ekstrak semua mata pelajaran yang ditemukan.
- Output hanya JSON. Tidak ada teks lain sebelum atau sesudah JSON.
"""


def build_messages(model_name: str = "") -> list[dict]:
    """
    Build the messages array for the AI chat completion API.

    Args:
        model_name: Optional model identifier for logging context (not used in prompt).

    Returns:
        List of message dicts: [{"role": "system", ...}, {"role": "user", ...}]
    """
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_PROMPT_TEMPLATE},
    ]


def build_vision_messages(image_base64: str, mime_type: str = "image/png") -> list[dict]:
    """
    Build the messages array for vision-capable models.
    The image is embedded as a base64 data URL in the user message.

    Args:
        image_base64: Base64-encoded image bytes (no data URI prefix).
        mime_type:    MIME type of the image (default: "image/png").

    Returns:
        List of message dicts with image content.
    """
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
                    "text": USER_PROMPT_TEMPLATE,
                },
            ],
        },
    ]
