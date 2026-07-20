"""
app/infrastructure/ai/groq_client.py
======================================
Groq Vision AI client.

Groq uses OpenAI-compatible API format, so this extends BaseAIClient
just like DeepSeek and Qwen — minimal new code needed.

Model: meta-llama/llama-4-scout-17b-16e-instruct
  - Free tier, no credit card required
  - Vision capable (image_url with base64)
  - Fast inference (Groq LPU hardware)

Docs: https://console.groq.com/docs/vision

Configuration (from environment):
  GROQ_API_KEY  — from console.groq.com/keys
  GROQ_MODEL    — default: meta-llama/llama-4-scout-17b-16e-instruct

How to get API key (FREE, no credit card):
  1. Go to https://console.groq.com/keys
  2. Sign up with email / Google / GitHub
  3. Click "Create API Key"
  4. Copy key → paste to GROQ_API_KEY in .env

Free tier limits (July 2026):
  - 30 requests per minute (RPM)
  - 14,400 requests per day (RPD)
  - 6,000 tokens per minute (TPM) for vision models
"""

from __future__ import annotations

from app.core.config import settings
from app.core.exceptions import AIAuthorizationError, AIInvalidResponseError, AIServiceUnavailableError
from app.infrastructure.ai.base_client import BaseAIClient


class GroqClient(BaseAIClient):
    """
    AI Vision client for Groq (Llama 4 Scout vision model).

    Uses the OpenAI-compatible /openai/v1/chat/completions endpoint
    with vision content (image as base64 data URL).
    """

    @property
    def engine_name(self) -> str:
        return "Groq"

    @property
    def _endpoint(self) -> str:
        return "https://api.groq.com/openai/v1/chat/completions"

    @property
    def _model_name(self) -> str:
        model = getattr(settings, "groq_model", None)
        if not model:
            raise AIServiceUnavailableError(
                self.engine_name, "GROQ_MODEL is not set in .env"
            )
        return model

    def _default_headers(self) -> dict[str, str]:
        """Override to use GROQ_API_KEY instead of the internal AI_API_KEY."""
        api_key = settings.groq_api_key
        if not api_key:
            raise AIAuthorizationError(self.engine_name)
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _build_request_payload(self, messages: list[dict]) -> dict:
        """
        Build the request body for Groq's chat completions API.

        Groq is OpenAI-compatible and does not have thinking mode,
        so no special prefix injection needed.
        """
        return {
            "model": self._model_name,
            "messages": messages,
            "temperature": 0,
            "max_tokens": 8192,
            "stream": False,
        }

    def _parse_response_text(self, response_json: dict) -> str:
        """
        Extract the assistant's content text from the Groq response.

        Standard OpenAI-compatible structure — no thinking blocks.
        """
        try:
            choices = response_json.get("choices", [])
            if not choices:
                raise AIInvalidResponseError(self.engine_name, "Empty 'choices' array")
            content = choices[0]["message"]["content"]
            if not content:
                raise AIInvalidResponseError(self.engine_name, "Empty 'content' field")
            return str(content).strip()
        except AIInvalidResponseError:
            raise
        except (KeyError, IndexError, TypeError) as exc:
            raise AIInvalidResponseError(
                self.engine_name,
                f"Unexpected response structure: {exc}",
            ) from exc
