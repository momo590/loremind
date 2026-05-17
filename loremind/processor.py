"""Raw session notes → structured TTRPG entities via the configured LLMProvider.

Pipeline:
1. Gather existing entity names from the store so the LLM can reuse canonical names.
2. Call LLMProvider.extract_entities with the context block + the name list.
3. For each extracted entity, fuzzy-match against existing entities of the same type.
   - Match >= threshold → merge into the existing entity (preserves canonical id/slug).
   - No match → save as new.
4. Stamp session provenance (first_seen / last_updated / raw_fragments) into frontmatter.
"""
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
            self._llm = ClaudeProvider(api_key=api_key)
        else:
            self._llm = get_llm()

    def process(self, dump: SessionDump) -> list[Entity]:
        existing_context = self.store.context_block()
        existing_entities = self.store.all_entities()
        existing_names = [e.name for e in existing_entities]

        extracted = self._llm.extract_entities(
            dump.raw_text,
            {
                "existing_context": existing_context,
                "existing_entity_names": existing_names,
            },
        )

        saved: list[Entity] = []
        for new in extracted:
            match = self.store.find_similar(new.name, new.entity_type)
            if match is not None:
                merged = self.store.merge_entity(match, new)
                self._stamp_session(merged, dump, fresh=False)
                self.store.save_entity(merged)
                saved.append(merged)
            else:
                self._stamp_session(new, dump, fresh=True)
                self.store.save_entity(new)
                saved.append(new)

        self.store.save_raw_session(dump.session_number, dump.raw_text, dump.source)
        return saved

    @staticmethod
    def _stamp_session(entity: Entity, dump: SessionDump, *, fresh: bool) -> None:
        if fresh:
            entity.frontmatter["first_seen_session"] = dump.session_number
            entity.frontmatter["raw_fragments"] = [dump.raw_text]
        else:
            entity.frontmatter.setdefault("first_seen_session", dump.session_number)
            raw = entity.frontmatter.setdefault("raw_fragments", [])
            if dump.raw_text not in raw:
                raw.append(dump.raw_text)
        entity.frontmatter["last_updated_session"] = dump.session_number
