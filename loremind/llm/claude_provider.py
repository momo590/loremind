"""Anthropic Claude provider — default cloud backend, uses tool_use for structured output."""
from __future__ import annotations

import os
from typing import Optional

import anthropic

from loremind.llm.base import EXTRACT_PROMPT, LLMProvider
from loremind.schema import Entity, entity_from_llm_dict


DEFAULT_MODEL = "claude-opus-4-7"
DEFAULT_MAX_TOKENS = 4096
EXTRACT_TOOL_NAME = "record_entities"

# Anthropic tool definition. The model is forced to call this tool, so the response
# is guaranteed to be a structured tool_use block — no markdown fences, no JSON-parse
# failures, no "I'll explain first…" preambles slipping past.
EXTRACT_TOOL = {
    "name": EXTRACT_TOOL_NAME,
    "description": (
        "Record the campaign entities extracted from a TTRPG session's raw notes."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "entities": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "entity_type": {
                            "type": "string",
                            "enum": ["npc", "location", "faction", "item", "thread", "lore"],
                        },
                        "summary": {"type": "string"},
                        "details": {"type": "object", "additionalProperties": True},
                        "tags": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["name", "entity_type", "summary"],
                },
            }
        },
        "required": ["entities"],
    },
}


class ClaudeProvider(LLMProvider):

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self._client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        self._model = model or DEFAULT_MODEL

    def extract_entities(self, text: str, context: dict) -> list[Entity]:
        names = context.get("existing_entity_names") or []
        names_str = ", ".join(names) if names else "(none yet)"
        prompt = EXTRACT_PROMPT.format(
            existing_context=context.get("existing_context", ""),
            existing_entity_names=names_str,
            raw_notes=text,
        )

        response = self._client.messages.create(
            model=self._model,
            max_tokens=DEFAULT_MAX_TOKENS,
            tools=[EXTRACT_TOOL],
            tool_choice={"type": "tool", "name": EXTRACT_TOOL_NAME},
            messages=[{"role": "user", "content": prompt}],
        )

        for block in response.content:
            if getattr(block, "type", None) == "tool_use":
                rows = block.input.get("entities", [])
                return [entity_from_llm_dict(d) for d in rows]
        return []

    def ocr_image(self, path: str) -> str:
        raise NotImplementedError("Claude vision OCR is wired in v0.2 (T8 capture endpoint).")

    def transcribe_audio(self, path: str) -> str:
        raise NotImplementedError("Claude has no audio transcription; use Ollama+whisper.cpp.")
