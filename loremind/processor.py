"""Raw session notes → structured TTRPG entities via LLM."""
from __future__ import annotations
import json
import os
from typing import Optional

import anthropic

from loremind.schema import CampaignEntity, EntityType, SessionDump
from loremind.engine.tinm_adapter import CampaignStore


EXTRACT_PROMPT = """You are a campaign wiki builder for a TTRPG Game Master.

The GM just gave you raw session notes — messy, abbreviated, stream-of-consciousness.
Extract all named entities (NPCs, locations, factions, unresolved plot threads, significant items).

For each entity, output a JSON object. Return a JSON array.

Entity schema:
{
  "name": "exact name as written",
  "entity_type": "npc|location|faction|thread|event|item",
  "summary": "1-2 sentence summary of what we know",
  "details": {"key": "value"},  // any specific facts: allegiance, appearance, motivation, status
  "tags": ["tag1", "tag2"]
}

Rules:
- Extract only entities explicitly mentioned. Do not invent.
- Threads = unresolved plot hooks, promises made, mysteries raised.
- Be specific: "offered the party 200gp, was refused, may return hostile" is better than "merchant".
- If an entity appears in existing campaign context (provided below), merge/update — don't duplicate.

Existing campaign context:
{existing_context}

Raw session notes:
{raw_notes}

Return ONLY the JSON array. No explanation, no markdown fences."""


class SessionProcessor:

    def __init__(self, store: CampaignStore, api_key: Optional[str] = None):
        self.store = store
        self._client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))

    def process(self, dump: SessionDump) -> list[CampaignEntity]:
        existing = self.store.context_block()

        prompt = EXTRACT_PROMPT.format(
            existing_context=existing,
            raw_notes=dump.raw_text,
        )

        response = self._client.messages.create(
            model="claude-opus-4-7",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        raw_json = response.content[0].text.strip()
        # Strip markdown fences if model added them anyway
        if raw_json.startswith("```"):
            raw_json = raw_json.split("```")[1]
            if raw_json.startswith("json"):
                raw_json = raw_json[4:]

        entities_data = json.loads(raw_json)
        entities = []

        for d in entities_data:
            entity = CampaignEntity(
                name=d["name"],
                entity_type=EntityType(d["entity_type"]),
                summary=d["summary"],
                details=d.get("details", {}),
                tags=d.get("tags", []),
                first_seen_session=dump.session_number,
                last_updated_session=dump.session_number,
                raw_fragments=[dump.raw_text],
            )
            self.store.save_entity(entity)
            entities.append(entity)

        self.store.save_raw_session(dump.session_number, dump.raw_text, dump.source)
        return entities
