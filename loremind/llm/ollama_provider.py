"""Ollama provider — default local backend (no cloud, no auth)."""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Optional

from loremind.llm.base import EXTRACT_PROMPT, LLMProvider
from loremind.schema import CampaignEntity, EntityType


DEFAULT_HOST = "http://127.0.0.1:11434"
DEFAULT_MODEL = "llama3.3:8b"
DEFAULT_TIMEOUT = 60


class OllamaProvider(LLMProvider):

    def __init__(
        self,
        host: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self._host = host or os.environ.get("OLLAMA_HOST", DEFAULT_HOST)
        self._model = model or os.environ.get("OLLAMA_MODEL", DEFAULT_MODEL)
        self._timeout = timeout

    def _post(self, path: str, payload: dict) -> dict:
        req = urllib.request.Request(
            f"{self._host}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def extract_entities(self, text: str, context: dict) -> list[CampaignEntity]:
        existing = context.get("existing_context", "")
        prompt = EXTRACT_PROMPT.format(existing_context=existing, raw_notes=text)

        resp = self._post(
            "/api/generate",
            {"model": self._model, "prompt": prompt, "stream": False},
        )
        raw = resp.get("response", "").strip()
        data = json.loads(raw)
        return [
            CampaignEntity(
                name=d["name"],
                entity_type=EntityType(d["entity_type"]),
                summary=d["summary"],
                details=d.get("details", {}),
                tags=d.get("tags", []),
            )
            for d in data
        ]

    def ocr_image(self, path: str) -> str:
        raise NotImplementedError("Ollama vision OCR (moondream2) wired in T8/v0.2.")

    def transcribe_audio(self, path: str) -> str:
        raise NotImplementedError("Audio transcription is wired in T7 (whisper.cpp wrapper).")
