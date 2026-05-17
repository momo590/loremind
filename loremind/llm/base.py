"""LLMProvider ABC — shared interface for Claude, Ollama, and OpenAI backends.

The single shared prompt lives here so all providers stay aligned; T5 will swap
this for provider-specific tool/function-calling schemas.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from loremind.schema import Entity


EXTRACT_PROMPT = """You are a campaign wiki builder for a TTRPG Game Master.

The GM just gave you raw session notes — messy, abbreviated, stream-of-consciousness.
Extract all named entities (NPCs, locations, factions, unresolved plot threads, significant items).

For each entity, output a JSON object. Return a JSON array.

Entity schema:
{{
  "name": "exact name as written",
  "entity_type": "npc|location|faction|thread|event|item",
  "summary": "1-2 sentence summary of what we know",
  "details": {{"key": "value"}},
  "tags": ["tag1", "tag2"]
}}

Rules:
- Extract only entities explicitly mentioned. Do not invent.
- Threads = unresolved plot hooks, promises made, mysteries raised.
- Be specific: "offered the party 200gp, was refused, may return hostile" is better than "merchant".
- If an entity appears in existing campaign context (provided below), merge/update — don't duplicate.
- The list of known canonical names below is authoritative: when the notes mention one of
  these entities (even with a slightly different spelling or title), reuse the EXACT canonical
  name so the store can merge instead of creating a duplicate.

Known canonical entity names:
{existing_entity_names}

Existing campaign context:
{existing_context}

Raw session notes:
{raw_notes}

Return ONLY the JSON array. No explanation, no markdown fences."""


class LLMProvider(ABC):
    """Pluggable LLM backend. v0.1 wires extract_entities; OCR + audio are stubs."""

    @abstractmethod
    def extract_entities(self, text: str, context: dict) -> list[Entity]:
        """Parse raw session text into structured campaign entities."""

    @abstractmethod
    def ocr_image(self, path: str) -> str:
        """Extract text from a captured image (handwritten notes, screenshots)."""

    @abstractmethod
    def transcribe_audio(self, path: str) -> str:
        """Transcribe a session recording. Only Ollama (via whisper.cpp) implements this."""
