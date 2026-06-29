"""
tests/unit/test_mapping_engine.py
===================================
Unit tests for get_best_match() in mapping_engine.

No PaddleOCR dependency required — pure fuzzy matching logic.
Converted from root-level test_mapping_v2.py into proper pytest format.

Run: pytest tests/unit/test_mapping_engine.py -v
"""

import pytest
from app.services.mapping_engine import get_best_match

# Subset of MASTER_SUBJECTS for fast unit testing
# (Does not need to stay in sync with constants.py — tests the matching logic,
#  not the data itself.)
_TEST_SUBJECTS = [
    {"id": 1, "subject_name": "Agama", "category": "Umum",
     "aliases": ["Agama", "Pendidikan Agama", "Pendidikan Agama Islam", "Agama Islam", "PAI"]},
    {"id": 2, "subject_name": "PKN", "category": "Umum",
     "aliases": ["PKN", "PKn", "PPKN", "PPKn", "Pendidikan Kewarganegaraan", "Kewarganegaraan"]},
    {"id": 3, "subject_name": "Bahasa Indonesia", "category": "Umum",
     "aliases": ["Bahasa Indonesia", "Indonesia", "Bhs Indonesia", "B. Indonesia"]},
    {"id": 4, "subject_name": "Matematika", "category": "Umum",
     "aliases": ["Matematika", "Matematik", "Matika", "Matemathika", "Math", "MTK"]},
    {"id": 5, "subject_name": "IPA", "category": "Umum",
     "aliases": ["IPA", "Ilmu Pengetahuan Alam", "Fisika", "Kimia", "Biologi", "Ilmu Alam"]},
    {"id": 6, "subject_name": "IPS", "category": "Umum",
     "aliases": ["IPS", "Ilmu Pengetahuan Sosial", "Ilmu Sosial", "Sejarah", "Geografi", "Ekonomi"]},
    {"id": 7, "subject_name": "Bahasa Inggris", "category": "Umum",
     "aliases": ["Bahasa Inggris", "B. Inggris", "Bhs Inggris", "English", "B Inggris"]},
    {"id": 8, "subject_name": "Seni Budaya", "category": "Umum",
     "aliases": ["Seni", "Seni Budaya", "Seni dan Budaya", "Kesenian", "SBK"]},
    {"id": 9, "subject_name": "Olahraga", "category": "Umum",
     "aliases": ["Olahraga", "PJOK", "Pendidikan Jasmani", "Pendidikan Jasmani & Olah Raga"]},
    {"id": 10, "subject_name": "Prakarya", "category": "Umum",
     "aliases": ["Prakarya", "Prakarya dan Kewirausahaan", "Kewirausahaan", "Wirausaha", "PKK"]},
    {"id": 11, "subject_name": "Bahasa Jawa", "category": "Umum",
     "aliases": ["Bahasa Jawa", "Bhs Jawa", "B. Jawa", "Bahasa Daerah"]},
    {"id": 12, "subject_name": "TIK", "category": "Umum",
     "aliases": ["TIK", "KKPI", "Ketrampilan Komputer dan Pengolahan Informasi",
                 "Pengolahan Informasi", "Informatika", "Simulasi Digital"]},
    {"id": 13, "subject_name": "Lain - Lain 1", "category": "Umum",
     "aliases": ["Desain Grafis", "Muatan Lokal", "Desain", "Animasi"]},
    {"id": 14, "subject_name": "Lain - Lain 2", "category": "Umum",
     "aliases": ["Bahasa Arab", "Bahasa Asing", "Bahasa Mandarin"]},
    {"id": 15, "subject_name": "Lain - Lain 3", "category": "Umum",
     "aliases": ["Muatan Lokal 3", "Ekstra"]},
]


def _match_id(raw_name: str, threshold: int = 60) -> int | None:
    """Helper: get the matched subject ID or None."""
    result = get_best_match(raw_name, _TEST_SUBJECTS, threshold=threshold)
    return result["id"] if result else None


class TestExactMatches:
    def test_full_alias_agama(self):
        assert _match_id("Pendidikan Agama Islam") == 1

    def test_full_alias_pkn(self):
        assert _match_id("Pendidikan Kewarganegaraan") == 2

    def test_full_alias_bahasa_indonesia(self):
        assert _match_id("Bahasa Indonesia") == 3

    def test_acronym_ipa(self):
        assert _match_id("IPA") == 5

    def test_acronym_ips(self):
        assert _match_id("IPS") == 6

    def test_exact_seni_budaya(self):
        assert _match_id("Seni Budaya") == 8

    def test_exact_bahasa_inggris(self):
        assert _match_id("Bahasa Inggris") == 7


class TestAliasMatches:
    def test_fisika_maps_to_ipa(self):
        assert _match_id("Fisika") == 5

    def test_kimia_maps_to_ipa(self):
        assert _match_id("Kimia") == 5

    def test_kewirausahaan_maps_to_prakarya(self):
        assert _match_id("Kewirausahaan") == 10

    def test_kkpi_maps_to_tik(self):
        assert _match_id("Ketrampilan Komputer dan Pengolahan Informasi") == 12

    def test_olahraga_via_pjok(self):
        assert _match_id("Pendidikan Jasmani & Olah Raga") == 9


class TestFuzzyMatches:
    def test_truncation_matematik(self):
        assert _match_id("Matematik") == 4

    def test_typo_matemathika(self):
        assert _match_id("Matemathika") == 4

    def test_duplicate_ocr_agama(self):
        assert _match_id("Pendidikan Agama Agama Islam") == 1


class TestLainLainMatches:
    def test_desain_grafis(self):
        assert _match_id("Desain Grafis") == 13

    def test_bahasa_arab(self):
        # Bahasa Arab appears in multiple Lain-Lain; should match first available
        result = get_best_match("Bahasa Arab", _TEST_SUBJECTS, threshold=60)
        assert result is not None
        assert "Lain" in result["subject_name"]


class TestNoMatch:
    def test_empty_string(self):
        assert _match_id("") is None

    def test_single_char(self):
        assert _match_id("X") is None

    def test_none_like(self):
        assert get_best_match("", _TEST_SUBJECTS) is None
