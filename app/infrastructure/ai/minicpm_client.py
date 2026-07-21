"""
app/infrastructure/ai/minicpm_client.py
======================================
Secondary AI Vision HTTP client (configurable model).

Connects to the AI model server via the OpenAI-compatible chat completions API.
By default uses the model specified by MINICPM_MODEL in .env (e.g. minicpm-v,
minicpm-v:8b, or any other Ollama-served vision model).

This client shares the same base class and interface as QwenClient,
allowing seamless swapping between AI engines.
"""

from __future__ import annotations

import logging
import re as _re

from app.core.config import settings
from app.core.exceptions import AIInvalidResponseError
from app.infrastructure.ai.base_client import BaseAIClient

logger = logging.getLogger(__name__)


class MinicpmClient(BaseAIClient):
    """
    AI Vision client for the secondary OCR model (configurable via .env).

    Uses the OpenAI-compatible /v1/chat/completions endpoint with
    vision content (image as base64 data URL).

    Supports any Ollama-served vision model: minicpm-v, deepseek-ocr,
    llama3.2-vision, qwen2-vl, pixtral, etc.
    """

    @property
    def engine_name(self) -> str:
        return "MiniCPM"

    @property
    def _endpoint(self) -> str:
        host = settings.ai_host.rstrip("/")
        path = settings.minicpm_endpoint.lstrip("/")
        return f"{host}/{path}"

    @property
    def _model_name(self) -> str:
        return getattr(settings, "minicpm_model", "minicpm-v:8b")

    def _build_request_payload(self, messages: list[dict]) -> dict:
        """
        Build the request body for the completions API.

        Uses assistant prefix injection ('{') to force the model to skip
        chain-of-thought reasoning and output JSON directly. This reduces
        compute load and prevents VRAM spikes on Ollama.

        If a model does not support prefix injection, set
        MINICPM_USE_PREFIX=false in .env to disable it.
        """
        # Check if prefix injection should be used (default: True)
        use_prefix = settings.minicpm_use_prefix

        if use_prefix:
            messages_with_prefix = list(messages) + [
                {"role": "assistant", "content": "{"}
            ]
        else:
            messages_with_prefix = messages

        return {
            "model": self._model_name,
            "messages": messages_with_prefix,
            "temperature": 0,
            "max_tokens": 4096,
            "stream": False,
        }

    def _parse_response_text(self, response_json: dict) -> str:
        """
        Extract the assistant's content text from the AI response.

        If prefix injection was used, prepends '{' to reconstruct valid JSON.
        Falls back to the 'reasoning' field if content is empty (Ollama
        thinking mode edge case).
        """
        try:
            choices = response_json.get("choices", [])
            if not choices:
                raise AIInvalidResponseError(self.engine_name, "Empty 'choices' array")

            message = choices[0]["message"]
            content = message.get("content") or ""
            content = str(content).strip()

            logger.debug(
                f"[{self.engine_name}] Raw extracted content (before clean): "
                f"{repr(content[:500])}"
            )

            # Strip any residual <think>...</think> blocks
            content = _re.sub(r"<think>.*?</think>", "", content, flags=_re.DOTALL).strip()

            # Prepend the assistant prefix we injected (if applicable)
            if content and not content.startswith("{"):
                content = "{" + content

            # Fallback: reasoning field if content is empty (Ollama thinking mode)
            if not content:
                reasoning = message.get("reasoning") or ""
                reasoning = str(reasoning).strip()
                if reasoning:
                    logger.debug(
                        f"[{self.engine_name}] content empty, extracting from "
                        f"reasoning field (len={len(reasoning)})"
                    )
                    content = reasoning

            logger.debug(f"[{self.engine_name}] Cleaned content: {repr(content[:500])}")

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
