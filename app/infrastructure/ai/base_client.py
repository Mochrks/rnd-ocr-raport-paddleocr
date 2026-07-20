"""
app/infrastructure/ai/base_client.py
======================================
Abstract base HTTP client for AI Vision services.

Responsibilities:
- Manage httpx.AsyncClient lifecycle (one client per engine instance)
- Inject Authorization: Bearer <token> automatically on every request
- Implement retry logic with exponential backoff for transient errors
- Encode image files as base64 for multipart or vision API payloads
- Map HTTP errors to domain exceptions (401→AIAuthorizationError, etc.)
- Log all relevant metrics: engine, timing, file size, HTTP status, tokens

Subclasses only need to implement:
  - `engine_name` property
  - `_build_request_payload(messages, model)` — produce the request body dict
  - `_parse_response_text(response_json)` — extract the raw text from the response

Usage:
    client = DeepSeekClient()
    raw_text = await client.run_ocr(image_path)
"""

from __future__ import annotations

import base64
import json
import logging
import mimetypes
import os
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings
from app.core.exceptions import (
    AIAuthorizationError,
    AIForbiddenError,
    AIInvalidResponseError,
    AIRequestTimeoutError,
    AIServiceUnavailableError,
)

logger = logging.getLogger(__name__)

# HTTP status codes that are safe to retry
_RETRYABLE_STATUS: frozenset[int] = frozenset({429, 500, 502, 503, 504})


class BaseAIClient(ABC):
    """
    Reusable async HTTP client for AI Vision services.

    Subclass and implement:
      - engine_name (property)
      - _endpoint (property) — full URL including path
      - _model_name (property) — model identifier string
      - _build_request_payload(messages) — dict sent as JSON body
      - _parse_response_text(response_json) — extract assistant text from response
    """

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None

    # ── Abstract interface ────────────────────────────────────────────────

    @property
    @abstractmethod
    def engine_name(self) -> str:
        """Human-readable engine name for logging: 'DeepSeek' or 'Qwen'."""

    @property
    @abstractmethod
    def _endpoint(self) -> str:
        """Full URL of the AI service endpoint (host + path)."""

    @property
    @abstractmethod
    def _model_name(self) -> str:
        """Model identifier sent in the request body."""

    @abstractmethod
    def _build_request_payload(self, messages: list[dict]) -> dict:
        """
        Build the JSON request body for the AI service.

        Args:
            messages: List of role/content message dicts (system + user with image).

        Returns:
            Dict that will be serialized as the JSON request body.
        """

    @abstractmethod
    def _parse_response_text(self, response_json: dict) -> str:
        """
        Extract the assistant's text reply from the AI service response JSON.

        Args:
            response_json: Parsed JSON response from the AI service.

        Returns:
            Raw text string produced by the model (expected to be JSON).

        Raises:
            AIInvalidResponseError: If the expected fields are missing.
        """

    # ── Public API ────────────────────────────────────────────────────────

    async def run_ocr(self, image_path: str, doc_type: str = "raport") -> str:
        """
        Send an image to the AI service for OCR extraction.

        Encodes the image as base64, builds vision messages, calls the API
        with retry logic, and returns the raw text response from the model.

        Args:
            image_path: Absolute path to the image file (PNG/JPG).
            doc_type:   Document type (e.g. "raport", "ktp") for prompt selection.

        Returns:
            Raw text response from the AI model (expected to be valid JSON).

        Raises:
            AIAuthorizationError:    HTTP 401
            AIForbiddenError:        HTTP 403
            AIInvalidResponseError:  Response cannot be parsed
            AIRequestTimeoutError:   Timeout exceeded
            AIServiceUnavailableError: 5xx or connection error after retries
        """
        t_start = time.perf_counter()
        file_size = os.path.getsize(image_path) if os.path.exists(image_path) else 0

        logger.info(
            f"[{self.engine_name}] Starting OCR ({doc_type}) | "
            f"file={os.path.basename(image_path)} | "
            f"size={file_size / 1024:.1f}KB"
        )

        # Encode image to base64
        image_b64, mime_type = _encode_image(image_path)

        # Build vision messages (system + user with embedded image)
        from app.services.ai_prompt_builder import build_vision_messages
        messages = build_vision_messages(image_b64, mime_type, doc_type=doc_type)

        payload = self._build_request_payload(messages)

        # Execute with retry
        raw_text = await self._post_with_retry(payload, t_start)

        elapsed = time.perf_counter() - t_start
        logger.info(
            f"[{self.engine_name}] OCR complete | "
            f"elapsed={elapsed:.2f}s | "
            f"response_len={len(raw_text)}"
        )

        return raw_text

    async def close(self) -> None:
        """Close the underlying httpx client. Call during app shutdown if needed."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # ── Internal helpers ──────────────────────────────────────────────────

    def _get_client(self) -> httpx.AsyncClient:
        """Return (or create) the shared async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=10.0,
                    read=float(settings.request_timeout),
                    write=30.0,
                    pool=5.0,
                ),
                headers=self._default_headers(),
            )
        return self._client

    def _default_headers(self) -> dict[str, str]:
        """
        Build default request headers.
        Authorization header is injected here — never hardcoded.
        """
        api_key = settings.ai_api_key
        if not api_key:
            logger.warning(
                f"[{self.engine_name}] AI_API_KEY is not set in environment!"
            )
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _post_with_retry(self, payload: dict, t_start: float) -> str:
        """
        POST the payload to the AI endpoint with exponential-backoff retry.

        Args:
            payload:  JSON-serializable request body.
            t_start:  Unix timestamp for total elapsed logging.

        Returns:
            Raw text extracted from the AI response.
        """
        max_retry = max(1, settings.max_retry + 1)  # total attempts
        last_exc: Optional[Exception] = None

        for attempt in range(1, max_retry + 1):
            try:
                t_req = time.perf_counter()
                client = self._get_client()

                logger.debug(
                    f"[{self.engine_name}] POST {self._endpoint} "
                    f"(attempt {attempt}/{max_retry})"
                )

                response = await client.post(self._endpoint, json=payload)

                req_elapsed = time.perf_counter() - t_req
                logger.info(
                    f"[{self.engine_name}] HTTP {response.status_code} | "
                    f"response_time={req_elapsed:.2f}s"
                )

                # Handle HTTP errors
                self._handle_http_error(response)

                # Parse and validate response
                response_json = response.json()
                self._log_token_usage(response_json)
                return self._parse_response_text(response_json)

            except (AIAuthorizationError, AIForbiddenError, AIInvalidResponseError):
                # Non-retryable — re-raise immediately
                raise

            except httpx.TimeoutException:
                last_exc = AIRequestTimeoutError(self.engine_name, settings.request_timeout)
                logger.warning(
                    f"[{self.engine_name}] Timeout on attempt {attempt}/{max_retry}"
                )

            except httpx.ConnectError as exc:
                last_exc = AIServiceUnavailableError(
                    self.engine_name, f"Connection error: {exc}"
                )
                logger.warning(
                    f"[{self.engine_name}] Connection error on attempt {attempt}: {exc}"
                )

            except Exception as exc:
                last_exc = AIServiceUnavailableError(self.engine_name, str(exc))
                logger.warning(
                    f"[{self.engine_name}] Unexpected error on attempt {attempt}: {exc}"
                )

            # Exponential backoff before retry (skip on last attempt)
            if attempt < max_retry:
                backoff = 2 ** (attempt - 1)
                logger.info(f"[{self.engine_name}] Retrying in {backoff}s...")
                import asyncio
                await asyncio.sleep(backoff)

        # All retries exhausted
        raise last_exc or AIServiceUnavailableError(self.engine_name, "All retries failed")

    def _handle_http_error(self, response: httpx.Response) -> None:
        """
        Raise domain exceptions for known HTTP error codes.
        Does nothing for 2xx responses.
        """
        status = response.status_code
        if status == 200:
            return
        if status == 401:
            raise AIAuthorizationError(self.engine_name)
        if status == 403:
            raise AIForbiddenError(self.engine_name)
        if status in _RETRYABLE_STATUS:
            raise AIServiceUnavailableError(
                self.engine_name,
                f"HTTP {status}: {response.text[:200]}",
            )
        if status >= 400:
            raise AIServiceUnavailableError(
                self.engine_name,
                f"HTTP {status}: {response.text[:200]}",
            )

    def _log_token_usage(self, response_json: dict) -> None:
        """Log token usage from the response if available."""
        usage = response_json.get("usage")
        if not usage:
            return
        logger.info(
            f"[{self.engine_name}] Token usage | "
            f"prompt={usage.get('prompt_tokens')} | "
            f"completion={usage.get('completion_tokens')} | "
            f"total={usage.get('total_tokens')}"
        )


# ── Image encoding helper ──────────────────────────────────────────────────

def _encode_image(image_path: str) -> tuple[str, str]:
    """
    Encode an image file to base64 string.

    Args:
        image_path: Path to the image file.

    Returns:
        Tuple of (base64_string, mime_type).
    """
    mime_type, _ = mimetypes.guess_type(image_path)
    if not mime_type or not mime_type.startswith("image/"):
        # Default to PNG for preprocessed images
        ext = os.path.splitext(image_path.lower())[1]
        mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
        mime_type = mime_map.get(ext, "image/png")

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    return base64.b64encode(image_bytes).decode("utf-8"), mime_type
