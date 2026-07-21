"""
app/core/config.py
==================
Centralized application configuration using Pydantic Settings.
All values are loaded from environment variables / .env file.
No hardcoded defaults — every setting must be explicitly provided.
"""

from __future__ import annotations

from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded strictly from environment variables or .env file.
    All fields are required — the app will fail on startup if any value is missing.
    """

    # ── Application ────────────────────────────────────────────────────────
    app_title: str
    app_description: str
    app_version: str
    debug: bool

    # ── CORS ───────────────────────────────────────────────────────────────
    cors_origins: list[str]
    cors_allow_credentials: bool
    cors_allow_methods: list[str]
    cors_allow_headers: list[str]

    # ── File Upload ────────────────────────────────────────────────────────
    upload_dir: str
    max_upload_size_mb: int
    allowed_extensions: list[str]

    # ── OCR Engine ─────────────────────────────────────────────────────────
    ocr_lang: str
    ocr_det_thresh: float
    ocr_box_thresh: float
    ocr_use_textline_orientation: bool
    ocr_warmup_on_startup: bool
    ocr_use_mkldnn: bool
    ocr_cpu_threads: int
    ocr_use_gpu: bool

    # ── Image Processing ───────────────────────────────────────────────────
    preprocessing_denoise_enabled: bool
    pdf_render_scale: float
    image_max_width: int
    image_max_pixels: int

    # ── Subject Matching ───────────────────────────────────────────────────
    fuzzy_match_threshold: int
    y_cluster_tolerance: int
    score_zone_fallback_ratio: float

    # ── AI Models ──────────────────────────────────────────────────────────
    ai_host: str
    ai_api_key: str
    qwen_endpoint: str
    qwen_model: str
    minicpm_endpoint: str
    minicpm_model: str
    minicpm_use_prefix: bool = True  # Toggle assistant prefix injection '{' for MiniCPM
    request_timeout: int
    max_retry: int

    # ── Redis / Celery Task Queue ──────────────────────────────────────────
    redis_url: Optional[str] = None

    # ── PostgreSQL Database (for dynamic flags) ────────────────────────────
    db_host: str = "127.0.0.1"
    db_port: int = 5432
    db_name: str = "postgres"
    db_user: str = "postgres"
    db_password: str = ""

    # ── Logging ────────────────────────────────────────────────────────────
    log_level: str
    log_file: Optional[str] = None

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


# Module-level singleton — import this everywhere
settings = Settings()
