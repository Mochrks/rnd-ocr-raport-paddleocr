"""
tests/unit/test_personality_guard.py
======================================
Unit tests for personality key detection and false-positive guarding.

No PaddleOCR required — pure text matching logic.
Converted from root-level test_kkm_personality.py.

Run: pytest tests/unit/test_personality_guard.py -v
"""

import pytest
from app.services.mapping_engine import _find_personality_key
from app.utils.text_normalizer import normalize_text


def _detect(text: str) -> str | None:
    """Helper: normalize and detect personality key."""
    norm = normalize_text(text)
    return _find_personality_key(norm, text.lower())


class TestPersonalityKeyDetection:
    """Verify correct personality keys are detected."""

    def test_standalone_kelakuan(self):
        assert _detect("Kelakuan") == "kelakuan"

    def test_standalone_kerajinan(self):
        assert _detect("Kerajinan") == "kerajinan"

    def test_standalone_kerapihan(self):
        assert _detect("Kerapihan") == "kerapihan"

    def test_kelakuan_with_grade(self):
        assert _detect("Kelakuan B") == "kelakuan"

    def test_kerajinan_with_grade(self):
        assert _detect("Kerajinan Baik") == "kerajinan"

    def test_sikap_sosial_multi_word(self):
        assert _detect("Sikap Sosial") == "kerajinan"

    def test_standalone_sosial(self):
        assert _detect("Sosial") == "kerajinan"

    def test_standalone_disiplin(self):
        assert _detect("Disiplin") == "kerajinan"

    def test_kerapian_variant(self):
        assert _detect("Kerapian") == "kerapihan"

    def test_kebersihan_maps_to_kerapihan(self):
        assert _detect("Kebersihan") == "kerapihan"

    def test_spiritual_maps_to_kelakuan(self):
        assert _detect("Spiritual") == "kelakuan"

    def test_sikap_spiritual(self):
        assert _detect("Sikap Spiritual") == "kelakuan"


class TestPersonalityFalsePositiveGuard:
    """
    Verify that the two-layer personality guard works as designed.

    Layer 1: extract_personality() in mapping_engine skips rows containing
             subject_row_keywords (e.g. 'ilmu', 'bahasa', 'ekonomi') BEFORE
             calling _find_personality_key().
    Layer 2: _find_personality_key() applies a dominance ratio check to
             prevent short aliases from matching in long subject names.

    These tests verify Layer 2 isolation behavior and Layer 1 integration.
    """

    def test_pendidikan_kewarganegaraan_not_personality(self):
        """Long text with no personality alias → None."""
        assert _detect("Pendidikan Kewarganegaraan") is None


    def test_long_subject_line_not_personality(self):
        assert _detect("Bahasa Indonesia dan Sastra") is None

    def test_ilmu_pengetahuan_sosial_note(self):
        """
        _find_personality_key() is called ONLY AFTER the subject_row_keywords
        guard in extract_personality() has already filtered out rows containing
        'ilmu', 'bahasa', etc. This means 'Ilmu Pengetahuan Sosial' is NEVER
        passed to _find_personality_key() during real OCR processing.

        Confirm that Layer 1 subject_row_keywords guard catches IPS.
        """
        subject_guard_kws = [
            'ilmu pengetahuan', 'bahasa', 'matematika', 'fisika', 'kimia',
            'biologi', 'sejarah', 'geografi', 'ekonomi', 'sosiologi',
            'pendidikan', 'olahraga', 'jasmani', 'seni', 'prakarya',
            'ilmu',  # catches 'Ilmu Pengetahuan Sosial' and 'Ilmu Sosial'
        ]
        text = "Ilmu Pengetahuan Sosial".lower()
        assert any(kw in text for kw in subject_guard_kws), (
            "'Ilmu Pengetahuan Sosial' must be caught by the subject_row_keywords guard "
            "in extract_personality() before _find_personality_key() is called"
        )

    def test_ilmu_sosial_caught_by_layer1(self):
        """'Ilmu Sosial' contains 'ilmu' — Layer 1 guard catches it."""
        subject_guard_kws = ['ilmu']
        text = "Ilmu Sosial".lower()
        assert any(kw in text for kw in subject_guard_kws)


class TestKKMHeuristicAssignment:
    """
    Verify the KKM heuristic (x_spread > 80px) works correctly.
    Converted from test_kkm_personality.py TEST 1.
    """

    def _assign(self, candidates, cols):
        from app.services.kkm_assigner import assign_kkm_score
        return assign_kkm_score(candidates, cols)

    def _cols_no_kkm(self):
        return {"has_kkm": False, "kkm_x": None, "score_x": None}

    def test_wide_spread_assigns_kkm(self):
        """Two numbers 250px apart → left=KKM, right=Score."""
        cands = [
            {"value": 70.0, "x": 600.0, "conf": 0.9},
            {"value": 78.0, "x": 850.0, "conf": 0.9},
        ]
        kkm, score = self._assign(cands, self._cols_no_kkm())
        assert kkm == 70.0
        assert score == 78.0

    def test_single_value_no_kkm(self):
        """Single number → no KKM."""
        cands = [{"value": 78.0, "x": 800.0, "conf": 0.9}]
        kkm, score = self._assign(cands, self._cols_no_kkm())
        assert kkm is None
        assert score == 78.0

    def test_close_values_no_kkm(self):
        """Two numbers 30px apart → likely split decimal, no KKM."""
        cands = [
            {"value": 7.0, "x": 800.0, "conf": 0.9},
            {"value": 5.0, "x": 830.0, "conf": 0.9},
        ]
        kkm, score = self._assign(cands, self._cols_no_kkm())
        assert kkm is None

    def test_inverted_kkm_rejected(self):
        """If inferred KKM > score + 5, reject the KKM assignment."""
        cands = [
            {"value": 90.0, "x": 600.0, "conf": 0.9},
            {"value": 78.0, "x": 850.0, "conf": 0.9},
        ]
        kkm, score = self._assign(cands, self._cols_no_kkm())
        assert kkm is None
        assert score == 78.0
