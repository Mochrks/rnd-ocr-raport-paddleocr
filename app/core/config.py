"""
app/core/config.py
==================
Centralized application configuration using Pydantic Settings.
All values are loaded directly from .env.paddle — no hardcoded defaults.
"""

from __future__ import annotations

from typing import Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    # Application
    app_title: str
    app_description: str
    app_version: str
    debug: bool

    # CORS
    cors_origins: list[str]
    cors_allow_credentials: bool
    cors_allow_methods: list[str]
    cors_allow_headers: list[str]

    # File Upload
    upload_dir: str
    max_upload_size_mb: int
    allowed_extensions: list[str]

    # OCR Engine
    ocr_lang: str
    ocr_det_thresh: float
    ocr_box_thresh: float
    ocr_use_textline_orientation: bool
    ocr_warmup_on_startup: bool
    ocr_use_gpu: bool
    ocr_use_mkldnn: bool
    ocr_cpu_threads: int

    # Image Processing
    preprocessing_denoise_enabled: bool
    pdf_render_scale: float
    image_max_width: int
    image_max_pixels: int

    # Subject Matching
    fuzzy_match_threshold: int
    y_cluster_tolerance: int
    score_zone_fallback_ratio: float

    # Redis (optional)
    redis_url: Optional[str] = None

    # Logging
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


settings = Settings()
