"""Anthropic Claude provider — default cloud backend."""
from __future__ import annotations

import json
import os
from typing import Optional

import anthropic

from loremind.llm.base import EXTRACT_PROMPT, LLMProvider
from loremind.schema import Entity, entity_from_llm_dict


DEFAULT_MODEL = "claude-opus-4-7"
DEFAULT_MAX_TOKENS = 4096


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()


class ClaudeProvider(LLMProvider):

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self._client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        self._model = model or DEFAULT_MODEL

    def extract_entities(self, text: str, context: dict) -> list[Entity]:
        existing = context.get("existing_context", "")
        prompt = EXTRACT_PROMPT.format(existing_context=existing, raw_notes=text)

        response = self._client.messages.create(
            model=self._model,
            max_tokens=DEFAULT_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_json = _strip_fences(response.content[0].text)
        data = json.loads(raw_json)
        return [entity_from_llm_dict(d) for d in data]

    def ocr_image(self, path: str) -> str:
        raise NotImplementedError("Claude vision OCR is wired in v0.2 (T8 capture endpoint).")

    def transcribe_audio(self, path: str) -> str:
        raise NotImplementedError("Claude has no audio transcription; use Ollama+whisper.cpp.")
