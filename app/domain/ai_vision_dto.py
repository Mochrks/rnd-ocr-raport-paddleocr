"""
app/domain/ai_vision_dto.py
============================
Pure-domain Data Transfer Objects for AI Vision engine responses.

These DTOs represent the **raw structured output** that DeepSeek / Qwen
return after reading a report card image. They are model-agnostic — any
AI Vision client produces the same DTO shape.

Design notes:
- Pure Python / Pydantic — no FastAPI, PaddleOCR, or httpx dependency here.
- All fields are Optional so partial results are preserved rather than
  raising validation errors when a model leaves something blank.
- The mapper layer (services/ai_response_mapper.py) converts these DTOs
  into the unified internal pipeline dict expected by the rest of the app.
"""

from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field, model_validator


# ── Subject ────────────────────────────────────────────────────────────────

class AISubjectDTO(BaseModel):
    """A single subject extracted by the AI Vision model."""

    nama: Optional[str] = Field(None, description="Nama mata pelajaran (raw dari AI)")
    nilai: Optional[Any] = Field(None, description="Nilai / score (angka atau null)")
    kkm: Optional[Any] = Field(None, description="KKM (angka atau null)")
    predikat: Optional[str] = Field(None, description="Predikat huruf: A/B/C/D")
    deskripsi: Optional[str] = Field(None, description="Deskripsi capaian")

    @model_validator(mode="before")
    @classmethod
    def normalize_ai_keys(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Normalisasi nama mata pelajaran jika AI menggunakan key lain
            if not data.get("nama"):
                for alt_key in ["mata_pelajaran", "mapel", "subject", "pelajaran", "name", "muatan_pelajaran"]:
                    if data.get(alt_key):
                        data["nama"] = str(data[alt_key])
                        break
            
            # Normalisasi nilai jika AI menggunakan key lain
            if data.get("nilai") is None:
                for alt_key in ["nilai_akhir", "angka", "score", "nilai_pengetahuan", "pengetahuan", "capaian"]:
                    if data.get(alt_key) is not None:
                        data["nilai"] = data[alt_key]
                        break
        return data


# ── Attendance ─────────────────────────────────────────────────────────────

class AIAttendanceDTO(BaseModel):
    """Attendance block extracted by the AI Vision model."""

    sakit: Optional[Any] = None
    izin: Optional[Any] = None
    alpa: Optional[Any] = None


# ── Personality ────────────────────────────────────────────────────────────

class AIPersonalityDTO(BaseModel):
    """Personality / sikap block extracted by the AI Vision model."""

    kelakuan: Optional[str] = None
    kerajinan: Optional[str] = None
    kerapihan: Optional[str] = None


# ── Student Info ───────────────────────────────────────────────────────────

class AIStudentInfoDTO(BaseModel):
    """Student identity block extracted by the AI Vision model."""

    nama: Optional[str] = None
    nis: Optional[str] = None
    nisn: Optional[str] = None
    kelas: Optional[str] = None
    semester: Optional[str] = None
    tahun_ajaran: Optional[str] = None
    sekolah: Optional[str] = None


# ── Root Response ──────────────────────────────────────────────────────────

class AIVisionRawResponse(BaseModel):
    """
    Root DTO for the complete AI Vision model output.

    The AI model is instructed to return exactly this JSON structure.
    All fields are Optional so partial raport can still be processed.
    """

    siswa: Optional[AIStudentInfoDTO] = None
    mata_pelajaran: Optional[List[AISubjectDTO]] = Field(default_factory=list)
    absensi: Optional[AIAttendanceDTO] = None
    kepribadian: Optional[AIPersonalityDTO] = None
    catatan_wali: Optional[Any] = None
    naik_kelas: Optional[Any] = None


# ── Token Usage (for logging) ──────────────────────────────────────────────

class AITokenUsage(BaseModel):
    """Token usage statistics from the AI service response (if available)."""

    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
