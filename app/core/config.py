"""
app/core/config.py
==================
Centralized application configuration using Pydantic Settings.
All values can be overridden via environment variables or a .env file.
"""

from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables / .env file.
    All settings have sensible defaults so the app works out-of-the-box.
    """

    # ── Application ────────────────────────────────────────────────────────
    app_title: str = "Doc Report OCR Service (PaddleOCR)"
    app_description: str = (
        "REST API for OCR scanning using PaddleOCR — "
        "supports digital and handwritten Indonesian report cards."
    )
    app_version: str = "2.0.0"
    debug: bool = False

    # ── CORS ───────────────────────────────────────────────────────────────
    cors_origins: list[str] = ["*"]
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = ["*"]
    cors_allow_headers: list[str] = ["*"]

    # ── File Upload ────────────────────────────────────────────────────────
    upload_dir: str = "uploads"
    max_upload_size_mb: int = 20
    allowed_extensions: list[str] = [".png", ".jpg", ".jpeg", ".pdf"]

    # ── OCR Engine ─────────────────────────────────────────────────────────
    ocr_lang: str = "en"
    ocr_det_thresh: float = 0.3
    ocr_box_thresh: float = 0.4
    ocr_use_textline_orientation: bool = True
    # Set to True to initialize OCR engines at server startup (eliminates
    # first-request cold start but adds ~5–15s to boot time).
    ocr_warmup_on_startup: bool = False

    # ── Image Processing ───────────────────────────────────────────────────
    # Set False to skip denoising for high-quality digital PDFs
    preprocessing_denoise_enabled: bool = True
    # DPI multiplier when rendering PDF pages to images
    pdf_render_scale: float = 2.0

    # ── Subject Matching ───────────────────────────────────────────────────
    fuzzy_match_threshold: int = 70
    y_cluster_tolerance: int = 20
    score_zone_fallback_ratio: float = 0.35

    # ── Logging ────────────────────────────────────────────────────────────
    log_level: str = "INFO"
    # If set, logs are also written to this file path
    log_file: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        return upper


# Module-level singleton — import this everywhere instead of instantiating Settings()
settings = Settings()
