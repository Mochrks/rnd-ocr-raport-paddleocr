"""
app/core/logging.py
====================
Structured logging configuration for the OCR service.

Features:
- Log level configurable from settings
- Optional file handler for production
- Consistent format with timestamp, level, module, and message
- Per-request context helpers (doc_id tagging)
"""

from __future__ import annotations

import logging
import sys
from typing import Optional

from app.core.config import settings


def configure_logging() -> None:
    """
    Apply the application logging configuration.
    Call this once during app startup (in main.py lifespan).
    """
    log_format = (
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )
    date_format = "%Y-%m-%d %H:%M:%S"

    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stdout),
    ]

    if settings.log_file:
        file_handler = logging.FileHandler(settings.log_file, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))
        handlers.append(file_handler)

    logging.basicConfig(
        level=settings.log_level,
        format=log_format,
        datefmt=date_format,
        handlers=handlers,
        force=True,  # Override any pre-existing basicConfig
    )

    # Quiet down noisy third-party loggers
    logging.getLogger("paddleocr").setLevel(logging.WARNING)
    logging.getLogger("ppocr").setLevel(logging.WARNING)
    logging.getLogger("paddle").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        f"Logging configured | level={settings.log_level} | "
        f"file={'yes (' + settings.log_file + ')' if settings.log_file else 'no'}"
    )


def get_logger(name: str) -> logging.Logger:
    """
    Convenience wrapper — use instead of logging.getLogger() for consistency.

    Usage:
        logger = get_logger(__name__)
    """
    return logging.getLogger(name)


class PhaseLogger:
    """
    Context-aware logger for timing individual OCR pipeline phases.

    Usage:
        phase = PhaseLogger(logger, doc_id="DOC1A2B3C4")
        with phase.time("preprocessing"):
            img = preprocess_image(path)
        # Logs: "DOC1A2B3C4 | preprocessing | elapsed=0.23s"
    """

    def __init__(self, logger: logging.Logger, doc_id: str = "") -> None:
        self._logger = logger
        self._doc_id = doc_id

    def time(self, phase_name: str) -> "_PhaseTimer":
        return _PhaseTimer(self._logger, self._doc_id, phase_name)


class _PhaseTimer:
    """Internal context manager for PhaseLogger.time()."""

    def __init__(
        self, logger: logging.Logger, doc_id: str, phase_name: str
    ) -> None:
        import time as _time
        self._logger = logger
        self._doc_id = doc_id
        self._phase = phase_name
        self._time = _time
        self._start: Optional[float] = None

    def __enter__(self) -> "_PhaseTimer":
        self._start = self._time.perf_counter()
        prefix = f"[{self._doc_id}] " if self._doc_id else ""
        self._logger.info(f"{prefix}▶ {self._phase} starting...")
        return self

    def __exit__(self, *_) -> None:
        elapsed = self._time.perf_counter() - self._start  # type: ignore[operator]
        prefix = f"[{self._doc_id}] " if self._doc_id else ""
        self._logger.info(
            f"{prefix}✓ {self._phase} done | elapsed={elapsed:.3f}s"
        )
