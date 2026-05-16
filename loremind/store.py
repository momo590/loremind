"""Adapter between Loremind campaign entities and the TINM PCP v0 store.

TINM handles cross-session memory persistence (PCP v0 format).
This adapter translates TTRPG entities into TINM artifacts and back.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional

from loremind.schema import CampaignEntity, EntityType


LOREMIND_HOME = Path.home() / ".loremind"
CAMPAIGNS_DIR = LOREMIND_HOME / "campaigns"


class CampaignStore:
    """Persistent storage for a single campaign."""

    def __init__(self, campaign_name: str):
        self.campaign_name = campaign_name
        self.root = CAMPAIGNS_DIR / campaign_name
        self._init_dirs()

    def _init_dirs(self) -> None:
        for entity_type in EntityType:
            (self.root / f"{entity_type.value}s").mkdir(parents=True, exist_ok=True)
        (self.root / "sessions").mkdir(parents=True, exist_ok=True)
        (self.root / "raw").mkdir(parents=True, exist_ok=True)

    def save_entity(self, entity: CampaignEntity) -> Path:
        folder = self.root / f"{entity.entity_type.value}s"
        path = folder / f"{entity.slug()}.md"
        path.write_text(entity.to_markdown(), encoding="utf-8")
        return path

    def load_entity(self, entity_type: EntityType, slug: str) -> Optional[CampaignEntity]:
        path = self.root / f"{entity_type.value}s" / f"{slug}.md"
        if not path.exists():
            return None
        # Minimal parse — summary is first paragraph after ## Summary
        text = path.read_text(encoding="utf-8")
        name = slug.replace("-", " ").title()
        summary_start = text.find("## Summary\n")
        summary = ""
        if summary_start != -1:
            after = text[summary_start + len("## Summary\n"):]
            summary = after.split("\n\n")[0].strip()
        return CampaignEntity(name=name, entity_type=entity_type, summary=summary)

    def all_entities(self, entity_type: Optional[EntityType] = None) -> list[CampaignEntity]:
        types = [entity_type] if entity_type else list(EntityType)
        results = []
        for et in types:
            folder = self.root / f"{et.value}s"
            if folder.exists():
                for path in folder.glob("*.md"):
                    entity = self.load_entity(et, path.stem)
                    if entity:
                        results.append(entity)
        return results

    def save_raw_session(self, session_number: int, text: str, source: str) -> Path:
        path = self.root / "raw" / f"session-{session_number:03d}-{source}.md"
        path.write_text(text, encoding="utf-8")
        return path

    def context_block(self, max_entities: int = 20) -> str:
        """Build a context string to inject into AI client (MCP or direct)."""
        entities = self.all_entities()[:max_entities]
        if not entities:
            return "No campaign data yet."
        lines = [f"# {self.campaign_name} — Campaign Memory", ""]
        by_type: dict[str, list[CampaignEntity]] = {}
        for e in entities:
            by_type.setdefault(e.entity_type.value + "s", []).append(e)
        for type_label, group in by_type.items():
            lines.append(f"## {type_label.title()}")
            for e in group:
                lines.append(f"- **{e.name}**: {e.summary[:120]}")
            lines.append("")
        return "\n".join(lines)
