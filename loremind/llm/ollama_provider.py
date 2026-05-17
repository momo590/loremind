"""Ollama provider — default local backend (no cloud, no auth). Uses format=json."""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Optional

from loremind.llm.base import EXTRACT_PROMPT, LLMProvider
from loremind.schema import Entity, entity_from_llm_dict


DEFAULT_HOST = "http://127.0.0.1:11434"
DEFAULT_MODEL = "llama3.3:8b"
DEFAULT_TIMEOUT = 60

RETRY_PROMPT_SUFFIX = (
    "\n\nIMPORTANT: Your previous response was not valid JSON. Respond with ONLY a "
    "JSON object of the form {\"entities\": [...]}. No prose, no markdown."
)


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

    def _generate(self, prompt: str) -> str:
        resp = self._post(
            "/api/generate",
            {
                "model": self._model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
            },
        )
        return resp.get("response", "")

    @staticmethod
    def _rows_from_json(raw: str) -> list[dict]:
        data = json.loads(raw)
        if isinstance(data, dict):
            if "entities" in data and isinstance(data["entities"], list):
                return data["entities"]
            # Single entity wrapped as dict
            return [data]
        if isinstance(data, list):
            return data
        raise ValueError(f"Unexpected JSON shape from Ollama: {type(data).__name__}")

    def extract_entities(self, text: str, context: dict) -> list[Entity]:
        names = context.get("existing_entity_names") or []
        names_str = ", ".join(names) if names else "(none yet)"
        prompt = EXTRACT_PROMPT.format(
            existing_context=context.get("existing_context", ""),
            existing_entity_names=names_str,
            raw_notes=text,
        )

        raw = self._generate(prompt)
        try:
            rows = self._rows_from_json(raw)
        except (json.JSONDecodeError, ValueError):
            raw = self._generate(prompt + RETRY_PROMPT_SUFFIX)
            rows = self._rows_from_json(raw)  # propagate if still malformed

        return [entity_from_llm_dict(d) for d in rows]

    def ocr_image(self, path: str) -> str:
        raise NotImplementedError("Ollama vision OCR (moondream2) wired in T8/v0.2.")

    def transcribe_audio(self, path: str) -> str:
        raise NotImplementedError("Audio transcription is wired in T7 (whisper.cpp wrapper).")
