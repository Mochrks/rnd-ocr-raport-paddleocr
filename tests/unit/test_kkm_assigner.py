"""
tests/unit/test_kkm_assigner.py
================================
Unit tests for assign_kkm_score() with explicit KKM column detection.
"""

import pytest
from app.services.kkm_assigner import assign_kkm_score


def _cols(has_kkm=False, kkm_x=None, score_x=None):
    return {"has_kkm": has_kkm, "kkm_x": kkm_x, "score_x": score_x}


class TestHasKKMTrue:
    def test_two_cands_both_positions_known(self):
        cands = [
            {"value": 70.0, "x": 690.0, "conf": 0.9},
            {"value": 80.0, "x": 890.0, "conf": 0.9},
        ]
        kkm, score = assign_kkm_score(cands, _cols(has_kkm=True, kkm_x=700.0, score_x=900.0))
        assert kkm == 70.0
        assert score == 80.0

    def test_single_cand_closer_to_score(self):
        cands = [{"value": 80.0, "x": 890.0, "conf": 0.9}]
        kkm, score = assign_kkm_score(cands, _cols(has_kkm=True, kkm_x=700.0, score_x=900.0))
        assert kkm is None
        assert score == 80.0

    def test_single_cand_closer_to_kkm(self):
        cands = [{"value": 70.0, "x": 710.0, "conf": 0.9}]
        kkm, score = assign_kkm_score(cands, _cols(has_kkm=True, kkm_x=700.0, score_x=900.0))
        assert kkm == 70.0
        assert score is None


class TestHasKKMFalse:
    def test_empty_candidates(self):
        kkm, score = assign_kkm_score([], _cols())
        assert kkm is None
        assert score is None

    def test_single_value(self):
        cands = [{"value": 80.0, "x": 800.0, "conf": 0.9}]
        kkm, score = assign_kkm_score(cands, _cols())
        assert kkm is None
        assert score == 80.0

    def test_infer_kkm_wide_spread(self):
        cands = [
            {"value": 65.0, "x": 600.0, "conf": 0.9},
            {"value": 80.0, "x": 850.0, "conf": 0.9},
        ]
        kkm, score = assign_kkm_score(cands, _cols())
        assert kkm == 65.0
        assert score == 80.0
