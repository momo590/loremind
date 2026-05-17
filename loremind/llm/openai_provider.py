"""OpenAI provider — opt-in cloud backend (not the default)."""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Optional

from loremind.llm.base import EXTRACT_PROMPT, LLMProvider
from loremind.schema import CampaignEntity, EntityType


DEFAULT_HOST = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TIMEOUT = 60


class OpenAIProvider(LLMProvider):

    def __init__(
        self,
        api_key: Optional[str] = None,
        host: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._host = host or os.environ.get("OPENAI_HOST", DEFAULT_HOST)
        self._model = model or os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
        self._timeout = timeout

    def _post(self, path: str, payload: dict) -> dict:
        req = urllib.request.Request(
            f"{self._host}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def extract_entities(self, text: str, context: dict) -> list[CampaignEntity]:
        existing = context.get("existing_context", "")
        prompt = EXTRACT_PROMPT.format(existing_context=existing, raw_notes=text)

        resp = self._post(
            "/chat/completions",
            {
                "model": self._model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
            },
        )
        content = resp["choices"][0]["message"]["content"]
        data = json.loads(content)
        # response_format=json_object always wraps in a dict; entities expected under "entities"
        rows = data["entities"] if isinstance(data, dict) and "entities" in data else data
        return [
            CampaignEntity(
                name=d["name"],
                entity_type=EntityType(d["entity_type"]),
                summary=d["summary"],
                details=d.get("details", {}),
                tags=d.get("tags", []),
            )
            for d in rows
        ]

    def ocr_image(self, path: str) -> str:
        raise NotImplementedError("OpenAI vision OCR wired in v0.2.")

    def transcribe_audio(self, path: str) -> str:
        raise NotImplementedError("OpenAI Whisper transcription wired in T7.")
