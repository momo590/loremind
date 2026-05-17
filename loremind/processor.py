"""Raw session notes → structured TTRPG entities via the configured LLMProvider."""
from __future__ import annotations

from typing import Optional

from loremind.llm import get_llm
from loremind.llm.base import LLMProvider
from loremind.llm.claude_provider import ClaudeProvider
from loremind.schema import Entity, SessionDump
from loremind.store import CampaignStore


class SessionProcessor:

    def __init__(
        self,
        store: CampaignStore,
        llm: Optional[LLMProvider] = None,
        api_key: Optional[str] = None,
    ):
        self.store = store
        if llm is not None:
            self._llm = llm
        elif api_key is not None:
            # Legacy path: callers that pass api_key implicitly select Claude.
            self._llm = ClaudeProvider(api_key=api_key)
        else:
            self._llm = get_llm()

    def process(self, dump: SessionDump) -> list[Entity]:
        existing_context = self.store.context_block()
        entities = self._llm.extract_entities(
            dump.raw_text,
            {"existing_context": existing_context},
        )

        for entity in entities:
            entity.frontmatter.setdefault("first_seen_session", dump.session_number)
            entity.frontmatter["last_updated_session"] = dump.session_number
            entity.frontmatter.setdefault("raw_fragments", []).append(dump.raw_text)
            self.store.save_entity(entity)

        self.store.save_raw_session(dump.session_number, dump.raw_text, dump.source)
        return entities
