"""
app/domain/constants.py
========================
MASTER_SUBJECTS — the authoritative list of recognised Indonesian school subjects.

Design notes:
- This is pure domain data. It has no dependency on FastAPI, PaddleOCR, or any
  infrastructure library.
- Each entry contains a canonical subject_name plus a list of aliases, including
  common OCR typos, abbreviations, and regional/Madrasah variants.
- The 'Lain - Lain' slots (13–15) catch subjects not matched by fuzzy search.
  They are handled by exact alias matching only (not fuzzy) to avoid false positives.
- To add a new subject or alias: edit this file only. No other file needs changing.
"""

from __future__ import annotations

from typing import TypedDict


class MasterSubject(TypedDict):
    id: int
    subject_name: str
    category: str
    aliases: list[str]


MASTER_SUBJECTS: list[MasterSubject] = [
    {
        "id": 1,
        "subject_name": "Agama",
        "category": "Umum",
        "aliases": [
            "Agama",
            "Pendidikan Agama",
            "Pendidikan Agama Islam",
            "Agama Islam",
            # Uncomment variants for Madrasah / multi-religion schools:
            # "Agama Kristen", "Agama Katolik", "Agama Hindu", "Agama Budha",
            # "Agama Buddha", "Pendidikan Agama Buddha", "PAI", "PAK",
            # "Al-Qur'an Hadits", "Akidah Akhlak", "Fikih", "Fiqih",
            # "Sejarah Kebudayaan Islam", "SKI",
            # "Normatif Agama",  # SMK normatif format
        ],
    },
    {
        "id": 2,
        "subject_name": "PKN",
        "category": "Umum",
        "aliases": [
            "PKN", "PKn", "PPKN", "PPKn",
            "Pendidikan Kewarganegaraan",
            "Pendidikan Pancasila",
            "Civic Education",
            "Kewarganegaraan",
            "Pend Kewarganegaraan",
            "Pend. Kewarganegaraan",
            "Pendidikan Pancasila dan Kewarganegaraan",
            "Pancasila dan Kewarganegaraan",
            "P. Kewarganegaraan",
        ],
    },
    {
        "id": 3,
        "subject_name": "Bahasa Indonesia",
        "category": "Umum",
        "aliases": [
            "Bahasa Indonesia",
            "Indonesia",
            "Bhs Indonesia",
            "B. Indonesia",
            "B Indonesia",
            "Bahasa Indonesi",    # OCR truncation
            "Bahsa Indonesia",   # OCR typo
            "Bhs. Indonesia",
            "Bhs Ind",
        ],
    },
    {
        "id": 4,
        "subject_name": "Matematika",
        "category": "Umum",
        "aliases": [
            "Matematika",
            "Matematika Wajib",
            "Matematika Peminatan",
            "Matematik",          # OCR truncation
            "Matemathika",        # OCR typo
            "Matematiks",         # OCR typo
            "Matika",             # OCR short form
            "Math",
            "MTK",
            "Mtk",
        ],
    },
    {
        "id": 5,
        "subject_name": "IPA",
        "category": "Umum",
        "aliases": [
            "IPA",
            "Ilmu Pengetahuan Alam",
            "Ilmu Alam",
            "Science",
            "Sains",
            "Fisika",             # SMK: Fisika maps to IPA
            "Kimia",              # SMK: Kimia maps to IPA
            "Biologi",            # SMK: Biologi maps to IPA
            "Ilmu Peng Alam",
            "Ilmu Peng. Alam",
        ],
    },
    {
        "id": 6,
        "subject_name": "IPS",
        "category": "Umum",
        "aliases": [
            "IPS",
            "Ilmu Pengetahuan Sosial",
            "Ilmu Sosial",
            "Social Science",
            "Sejarah",
            "Geografi",
            "Ekonomi",
            "Sosiologi",
            "Ilmu Peng Sosial",
            "Ilmu Peng. Sosial",
        ],
    },
    {
        "id": 7,
        "subject_name": "Bahasa Inggris",
        "category": "Umum",
        "aliases": [
            "Bahasa Inggris",
            "B. Inggris",
            "Bhs Inggris",
            "English",
            "Bahasa Inggris Wajib",
            "Bahasa Inggris Peminatan",
            "B Inggris",
            "Bahasa Ingris",     # OCR typo
            "Bhs Ingris",        # OCR typo
            "Bhs. Inggris",
            "B. Ingris",
        ],
    },
    {
        "id": 8,
        "subject_name": "Seni Budaya",
        "category": "Umum",
        "aliases": [
            "Seni",
            "Seni Budaya",
            "Seni dan Budaya",
            "Kesenian",
            "Seni Rupa",
            "Seni Musik",
            "Seni Tari",
            "Seni Teater",
            "Seni Budaya dan Keterampilan",
            "Seni Budaya dan Prakarya",
            "Seni Budaya & Keterampilan",
            "SBK",
            "SBdP",
        ],
    },
    {
        "id": 9,
        "subject_name": "Olahraga",
        "category": "Umum",
        "aliases": [
            "Olahraga",
            "PJOK",
            "Penjas",
            "Pendidikan Jasmani",
            "Pendidikan Jasmani Olahraga",
            "Pendidikan Jasmani Olahraga dan Kesehatan",
            "Pendidikan Jasmani Olahraga & Kesehatan",
            "Olah Raga",
            "Pendidikan Jasmani & Olah Raga",
            "Pend Jasmani",
            "Jasmani",
            "Penjas Olah Raga",
            "Penjas Olah Raga & Kesehatan",
            "Pend Jasmani OR dan Kesehatan",
            "Pendidikan Jasmani OR",
            "Pend Jasmani Olahraga",
        ],
    },
    {
        "id": 10,
        "subject_name": "Prakarya",
        "category": "Umum",
        "aliases": [
            "Prakarya",
            "Prakarya dan Kewirausahaan",
            "Prakarya & Kewirausahaan",
            "Prakarya dan/atau Informatika",
            "Keterampilan",
            "Kewirausahaan",             # SMK: maps to Prakarya
            "Wirausaha",
            "PKK",                       # Produk Kreatif dan Kewirausahaan
            "Produk Kreatif",
            "Produk Kreatif dan Kewirausahaan",
        ],
    },
    {
        "id": 11,
        "subject_name": "Bahasa Jawa",
        "category": "Umum",
        "aliases": [
            "Bahasa Jawa",
            "Bhs Jawa",
            "B. Jawa",
            "B Jawa",
            "Bahasa Daerah",
            "Mulok Bahasa Jawa",
            "Bahasa Sunda",
            "Bhs Sunda",
            "B. Sunda",
            "Bahasa Madura",
            "Bhs Daerah",
            "Muatan Lokal Bahasa Jawa",
        ],
    },
    {
        "id": 12,
        "subject_name": "TIK",
        "category": "Umum",
        "aliases": [
            "TIK",
            "Teknologi Informasi",
            "Informatika",
            "Komputer",
            "KKPI",
            "Teknologi Informasi dan Komunikasi",
            "Teknologi Informasi & Komunikasi",
            "Teknologi & Komunikasi",
            "Ketrampilan Komputer dan Pengolahan Informasi",
            "Ketrampilan Komputer & Pengolahan Informasi",
            "Keterampilan Komputer dan Pengelolaan Informasi",
            "Simulasi Digital",
            "Simdig",
            "Pengolahan Informasi",
        ],
    },
    {
        "id": 13,
        "subject_name": "Lain - Lain 1",
        "category": "Umum",
        "aliases": [
            "Bahasa Arab", "B Arab", "B. Arab",
            "Muatan Lokal", "Mulok",
            "Desain Grafis",              # SMK Muatan Lokal
            "Desain Gravis",              # OCR typo
            "Design Grafis",
            "Desain",
            "Grafis",
            "Animasi",
            "Teknik Komputer",
            "Teknik Jaringan",
            "Produktif",
        ],
    },
    {
        "id": 14,
        "subject_name": "Lain - Lain 2",
        "category": "Umum",
        "aliases": [
            "Bahasa Arab", "B Arab", "B. Arab",
            "Muatan Lokal 2", "Mulok 2",
            "Bahasa Asing",
            "Bahasa Mandarin",
            "Bahasa Jepang",
            "Bahasa Korea",
            "Bahasa Prancis",
            "Bahasa Jerman",
        ],
    },
    {
        "id": 15,
        "subject_name": "Lain - Lain 3",
        "category": "Umum",
        "aliases": [
            "Bahasa Arab", "B Arab", "B. Arab",
            "Muatan Lokal 3", "Mulok 3",
            "Ekstra", "Ekstrakurikuler",
        ],
    },
]
