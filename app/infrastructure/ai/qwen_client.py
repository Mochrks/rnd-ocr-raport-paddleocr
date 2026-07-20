"""
app/infrastructure/ai/qwen_client.py
======================================
Qwen3-VL Vision HTTP client.

Connects to the company's internal Qwen3-VL model server via the
OpenAI-compatible chat completions API.

Configuration (from environment):
  AI_HOST        — base URL, e.g. http://11.11.141.1:8080
  AI_API_KEY     — Bearer token
  QWEN_ENDPOINT  — path, default /v1/chat/completions

The model name sent in the request body is "qwen3-vl" by default.
Override by setting QWEN_MODEL in your environment if the internal
server uses a different model identifier.
"""

from __future__ import annotations

import logging
import re as _re

from app.core.config import settings
from app.core.exceptions import AIInvalidResponseError
from app.infrastructure.ai.base_client import BaseAIClient

logger = logging.getLogger(__name__)


class QwenClient(BaseAIClient):
    """
    AI Vision client for the Qwen3-VL model.

    Uses the OpenAI-compatible /v1/chat/completions endpoint with
    vision content (image as base64 data URL).
    """

    @property
    def engine_name(self) -> str:
        return "Qwen"

    @property
    def _endpoint(self) -> str:
        host = settings.ai_host.rstrip("/")
        path = settings.qwen_endpoint.lstrip("/")
        return f"{host}/{path}"

    @property
    def _model_name(self) -> str:
        # Allows override via QWEN_MODEL env var if server uses a custom name
        return getattr(settings, "qwen_model", "qwen3-vl")

    def _build_request_payload(self, messages: list[dict]) -> dict:
        """
        Build the request body for the Qwen3-VL completions API.

        Uses assistant prefix injection ({ ) to force the model to skip
        thinking and directly output JSON. This is the most reliable way
        to disable thinking mode on Ollama-served Qwen3 models, as
        parameter-based flags (think: false, enable_thinking: false) are
        not honored by this server.
        """
        # Inject assistant prefix to force direct JSON output (bypasses thinking)
        messages_with_prefix = list(messages) + [
            {"role": "assistant", "content": "{"}
        ]
        return {
            "model": self._model_name,
            "messages": messages_with_prefix,
            "temperature": 0,
            "max_tokens": 8192,
            "stream": False,
        }

    def _parse_response_text(self, response_json: dict) -> str:
        """
        Extract the assistant's content text from the Qwen response.

        Because we inject an assistant prefix '{', the model continues
        from that prefix — we prepend it back to get valid JSON.

        Fallback: if content is still empty (Ollama thinking mode edge case),
        attempt to extract JSON from the reasoning field.
        """
        try:
            choices = response_json.get("choices", [])
            if not choices:
                raise AIInvalidResponseError(self.engine_name, "Empty 'choices' array")

            message = choices[0]["message"]
            content = message.get("content") or ""
            content = str(content).strip()

            # Strip any residual <think>...</think> blocks
            content = _re.sub(r"<think>.*?</think>", "", content, flags=_re.DOTALL).strip()

            # Prepend the assistant prefix we injected
            if content and not content.startswith("{"):
                content = "{" + content

            # Fallback: reasoning field (Ollama thinking mode edge case)
            if not content:
                reasoning = message.get("reasoning") or ""
                reasoning = str(reasoning).strip()
                if reasoning:
                    logger.debug(
                        f"[{self.engine_name}] content empty, extracting from "
                        f"reasoning field (len={len(reasoning)})"
                    )
                    content = reasoning

            if not content:
                raise AIInvalidResponseError(self.engine_name, "Empty 'content' field")

            return content

        except AIInvalidResponseError:
            raise
        except (KeyError, IndexError, TypeError) as exc:
            raise AIInvalidResponseError(
                self.engine_name,
                f"Unexpected response structure: {exc}",
            ) from exc
