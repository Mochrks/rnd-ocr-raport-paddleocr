"""
app/infrastructure/ai/deepseek_client.py
==========================================
DeepSeek Vision HTTP client.

Connects to the company's internal DeepSeek model server via the
OpenAI-compatible chat completions API.

Configuration (from environment):
  AI_HOST            — base URL, e.g. http://11.11.141.1:8080
  AI_API_KEY         — Bearer token
  DEEPSEEK_ENDPOINT  — path, default /v1/chat/completions

The model name sent in the request body is "deepseek-vl" by default.
Override by setting DEEPSEEK_MODEL in your environment if the internal
server uses a different model identifier.
"""

from __future__ import annotations

from app.core.config import settings
from app.core.exceptions import AIInvalidResponseError
from app.infrastructure.ai.base_client import BaseAIClient


class DeepSeekClient(BaseAIClient):
    """
    AI Vision client for the DeepSeek model.

    Uses the OpenAI-compatible /v1/chat/completions endpoint with
    vision content (image as base64 data URL).
    """

    @property
    def engine_name(self) -> str:
        return "DeepSeek"

    @property
    def _endpoint(self) -> str:
        host = settings.ai_host.rstrip("/")
        path = settings.deepseek_endpoint.lstrip("/")
        return f"{host}/{path}"

    @property
    def _model_name(self) -> str:
        # Allows override via DEEPSEEK_MODEL env var if server uses a custom name
        return getattr(settings, "deepseek_model", "deepseek-vl")

    def _build_request_payload(self, messages: list[dict]) -> dict:
        """
        Build the request body for the DeepSeek completions API.

        Uses temperature=0 for deterministic, fact-based OCR output.
        max_tokens is set high enough to accommodate a full raport JSON.
        """
        return {
            "model": self._model_name,
            "messages": messages,
            "temperature": 0,
            "max_tokens": 4096,
            "stream": False,
        }

    def _parse_response_text(self, response_json: dict) -> str:
        """
        Extract the assistant's content text from the DeepSeek response.

        Expected response structure (OpenAI-compatible):
        {
          "choices": [
            {
              "message": {
                "role": "assistant",
                "content": "<json string>"
              }
            }
          ],
          "usage": { ... }
        }
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
