"""
app/infrastructure/ai/gemini_client.py
========================================
Google Gemini Vision AI client.

Uses Google's native `google-genai` SDK (not httpx) because Gemini has its
own multimodal API format that differs from OpenAI-compatible endpoints.

Model: gemini-2.5-flash (free tier — 15 RPM, no credit card required)
Docs:  https://ai.google.dev/gemini-api/docs/image-understanding

Configuration (from environment):
  GEMINI_API_KEY  — from Google AI Studio (aistudio.google.com/apikey)
  GEMINI_MODEL    — default: gemini-2.5-flash

How to get API key (FREE, no credit card):
  1. Go to https://aistudio.google.com/apikey
  2. Sign in with Google account
  3. Click "Create API Key"
  4. Copy key → paste to GEMINI_API_KEY in .env

Free tier limits (July 2026):
  - 15 requests per minute (RPM)
  - 1,500 requests per day (RPD)
  - 1M tokens per minute
"""

from __future__ import annotations

import base64
import logging
import mimetypes
import os
import time
from typing import Optional

from app.core.config import settings
from app.core.exceptions import (
    AIAuthorizationError,
    AIInvalidResponseError,
    AIRequestTimeoutError,
    AIServiceUnavailableError,
)
from app.services.ai_prompt_builder import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)


class GeminiClient:
    """
    AI Vision client for Google Gemini.

    Uses the google-genai SDK directly (not httpx) to send image + text
    to the Gemini multimodal API and receive structured JSON back.
    """

    @property
    def engine_name(self) -> str:
        return "Gemini"

    @property
    def _model_name(self) -> str:
        model = getattr(settings, "gemini_model", None)
        if not model:
            raise AIServiceUnavailableError(
                self.engine_name, "GEMINI_MODEL is not set in .env"
            )
        return model

    async def run_ocr(self, image_path: str) -> str:
        """
        Send an image to Gemini for OCR extraction.

        Args:
            image_path: Absolute path to the image file (PNG/JPG).

        Returns:
            Raw text response from Gemini (expected to be valid JSON).

        Raises:
            AIAuthorizationError:     API key invalid / missing
            AIInvalidResponseError:   Response cannot be parsed
            AIRequestTimeoutError:    Timeout exceeded
            AIServiceUnavailableError: Service error after retries
        """
        api_key = settings.gemini_api_key
        if not api_key:
            raise AIAuthorizationError(self.engine_name)

        t_start = time.perf_counter()
        file_size = os.path.getsize(image_path) if os.path.exists(image_path) else 0

        logger.info(
            f"[{self.engine_name}] Starting OCR | "
            f"file={os.path.basename(image_path)} | "
            f"size={file_size / 1024:.1f}KB"
        )

        # Read and encode image
        with open(image_path, "rb") as f:
            image_bytes = f.read()

        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type or not mime_type.startswith("image/"):
            ext = os.path.splitext(image_path.lower())[1]
            mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
            mime_type = mime_map.get(ext, "image/png")

        max_retry = max(1, settings.max_retry + 1)
        last_exc: Optional[Exception] = None

        for attempt in range(1, max_retry + 1):
            try:
                import asyncio
                raw_text = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self._call_gemini(api_key, image_bytes, mime_type),
                )

                elapsed = time.perf_counter() - t_start
                logger.info(
                    f"[{self.engine_name}] OCR complete | "
                    f"elapsed={elapsed:.2f}s | "
                    f"response_len={len(raw_text)}"
                )
                return raw_text

            except (AIAuthorizationError, AIInvalidResponseError):
                raise

            except Exception as exc:
                last_exc = AIServiceUnavailableError(self.engine_name, str(exc))
                logger.warning(
                    f"[{self.engine_name}] Error on attempt {attempt}: {exc}"
                )

            if attempt < max_retry:
                import asyncio
                backoff = 2 ** (attempt - 1)
                logger.info(f"[{self.engine_name}] Retrying in {backoff}s...")
                await asyncio.sleep(backoff)

        raise last_exc or AIServiceUnavailableError(self.engine_name, "All retries failed")

    def _call_gemini(self, api_key: str, image_bytes: bytes, mime_type: str) -> str:
        """
        Synchronous Gemini API call — runs in executor to avoid blocking.
        """
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            raise AIServiceUnavailableError(
                self.engine_name,
                "google-genai package not installed. Run: pip install google-genai",
            )

        try:
            client = genai.Client(api_key=api_key)

            prompt = f"{SYSTEM_PROMPT}\n\n{USER_PROMPT_TEMPLATE}"

            response = client.models.generate_content(
                model=self._model_name,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    types.Part.from_text(text=prompt),
                ],
                config=types.GenerateContentConfig(
                    temperature=0,
                    max_output_tokens=8192,
                    # Force JSON output — no markdown wrapping
                    response_mime_type="application/json",
                ),
            )

            text = response.text
            if not text:
                raise AIInvalidResponseError(self.engine_name, "Empty response from Gemini")

            logger.info(
                f"[{self.engine_name}] Token usage | "
                f"prompt={response.usage_metadata.prompt_token_count} | "
                f"completion={response.usage_metadata.candidates_token_count} | "
                f"total={response.usage_metadata.total_token_count}"
            )

            return text.strip()

        except AIInvalidResponseError:
            raise
        except Exception as exc:
            err = str(exc).lower()
            if "api_key" in err or "invalid" in err or "401" in err or "unauthenticated" in err:
                raise AIAuthorizationError(self.engine_name)
            if "quota" in err or "429" in err or "rate" in err:
                raise AIServiceUnavailableError(
                    self.engine_name, f"Rate limit / quota exceeded: {exc}"
                )
            if "timeout" in err or "deadline" in err:
                raise AIRequestTimeoutError(self.engine_name, settings.request_timeout)
            raise AIServiceUnavailableError(self.engine_name, str(exc))

    async def close(self) -> None:
        """No persistent client to close for Gemini SDK."""
        pass
