"""
app/schemas/ocr_schemas.py
===========================
Pydantic request and response schemas for the OCR API.

All schemas are preserved exactly as before — no changes to field names,
types, or optionality, ensuring full backward compatibility with the frontend.
"""

from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel


# ── Response Sub-models ────────────────────────────────────────────────────

class SubjectScore(BaseModel):
    """A single recognised subject with its extracted score."""

    subjectId: Optional[int] = None
    subjectName: str
    originalText: Optional[str] = None     # Raw OCR text before mapping (for debugging)
    category: Optional[str] = "Umum"
    kkm: Optional[float] = None
    score: float
    accuracy: Optional[float] = None


class PersonalityGrade(BaseModel):
    """Grade for a single personality dimension (Kelakuan / Kerajinan / Kerapihan)."""

    grade: Optional[str] = None            # A / B / C / D, angka, or description
    accuracy: Optional[float] = None


class AttendanceValue(BaseModel):
    """Value for a single attendance dimension (Sakit / Ijin / Alpa)."""

    value: Optional[Any] = None            # Integer days or string (e.g. "-")
    accuracy: Optional[float] = None


class PersonalityData(BaseModel):
    """Complete personality block from the report card."""

    kelakuan: Optional[PersonalityGrade] = None
    kerajinan: Optional[PersonalityGrade] = None
    kerapihan: Optional[PersonalityGrade] = None


class AttendanceData(BaseModel):
    """Complete attendance block from the report card."""

    sakit: Optional[AttendanceValue] = None
    ijin: Optional[AttendanceValue] = None
    alpa: Optional[AttendanceValue] = None


# ── Primary Response ───────────────────────────────────────────────────────

class OCRUploadResponse(BaseModel):
    """Response returned immediately after upload (202 Accepted)."""
    documentId: str
    status: str = "PROCESSING"
    message: str = "Document uploaded successfully and queued for OCR processing."


class OCRResultResponse(BaseModel):
    """
    Full OCR extraction result — the main response body for POST /report/upload.
    Backward-compatible: all existing fields are preserved.
    """

    documentId: str
    status: str
    accuracy: Optional[float] = None
    processingTime: Optional[float] = None
    subjects: Optional[List[SubjectScore]] = []
    personality: Optional[PersonalityData] = None
    attendance: Optional[AttendanceData] = None


# ── Request / Admin Models ─────────────────────────────────────────────────
# These are retained from the original schemas.py for completeness.
# They are not used by the current two endpoints but may be needed by
# future features (confirmation flow, bulk save).

class SubjectScoreConfirm(BaseModel):
    subjectId: int
    score: float


class ConfirmRequest(BaseModel):
    documentId: str
    subjects: List[SubjectScoreConfirm]


class FinalSaveRequest(BaseModel):
    studentId: str
    academicData: List[SubjectScoreConfirm]


class MasterSubjectCreate(BaseModel):
    subject_name: str
    aliases: List[str] = []
