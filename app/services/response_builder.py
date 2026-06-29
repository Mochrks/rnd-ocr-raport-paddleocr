"""
app/services/response_builder.py
==================================
Build Pydantic response objects from raw OCR extraction dicts.

These helpers convert the internal dict representation produced by the
OCR pipeline into the typed Pydantic models expected by the API response.

Previously located in endpoints.py — moved here so the API layer contains
zero business or transformation logic.
"""

from __future__ import annotations

from typing import Dict, Optional

from app.schemas.ocr_schemas import (
    AttendanceData,
    AttendanceValue,
    PersonalityData,
    PersonalityGrade,
)


def build_personality_response(
    personality_raw: Optional[Dict],
) -> Optional[PersonalityData]:
    """
    Convert the raw personality dict from the OCR pipeline to PersonalityData.

    Returns None if the input is empty or all three fields are absent.

    Args:
        personality_raw: Dict with optional keys: kelakuan, kerajinan, kerapihan.
                         Each value is a dict with 'grade' and 'accuracy' keys.

    Returns:
        PersonalityData Pydantic model, or None if no data.
    """
    if not personality_raw:
        return None

    def _make_grade(data: Optional[Dict]) -> Optional[PersonalityGrade]:
        if not data:
            return None
        grade = data.get("grade")
        if grade is None:
            return None
        return PersonalityGrade(grade=str(grade), accuracy=data.get("accuracy"))

    kelakuan = _make_grade(personality_raw.get("kelakuan"))
    kerajinan = _make_grade(personality_raw.get("kerajinan"))
    kerapihan = _make_grade(personality_raw.get("kerapihan"))

    if kelakuan is None and kerajinan is None and kerapihan is None:
        return None

    return PersonalityData(
        kelakuan=kelakuan,
        kerajinan=kerajinan,
        kerapihan=kerapihan,
    )


def build_attendance_response(
    attendance_raw: Optional[Dict],
) -> Optional[AttendanceData]:
    """
    Convert the raw attendance dict from the OCR pipeline to AttendanceData.

    Returns None if the input is empty or all three fields are absent.

    Args:
        attendance_raw: Dict with optional keys: sakit, ijin, alpa.
                        Each value is a dict with 'value' and 'accuracy' keys.

    Returns:
        AttendanceData Pydantic model, or None if no data.
    """
    if not attendance_raw:
        return None

    def _make_att(data: Optional[Dict]) -> Optional[AttendanceValue]:
        if not data:
            return None
        value = data.get("value")
        if value is None:
            return None
        return AttendanceValue(value=value, accuracy=data.get("accuracy"))

    sakit = _make_att(attendance_raw.get("sakit"))
    ijin = _make_att(attendance_raw.get("ijin"))
    alpa = _make_att(attendance_raw.get("alpa"))

    if sakit is None and ijin is None and alpa is None:
        return None

    return AttendanceData(sakit=sakit, ijin=ijin, alpa=alpa)
