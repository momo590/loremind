"""Campaign store — per-campaign markdown wiki on disk.

Each entity is one markdown file under `~/.loremind/campaigns/<name>/<type>s/<slug>.md`.
The file starts with a JSON frontmatter block (see schema.Entity.to_markdown) so we
can round-trip without a YAML dep.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from loremind.schema import (
    Entity,
    EntityType,
    entity_from_markdown,
)


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

    def _folder(self, entity_type: EntityType) -> Path:
        return self.root / f"{entity_type.value}s"

    def save_entity(self, entity: Entity) -> Path:
        folder = self._folder(entity.entity_type)
        path = folder / f"{entity.slug}.md"
        path.write_text(entity.to_markdown(), encoding="utf-8")
        return path

    def load_entity(self, entity_type: EntityType, slug: str) -> Optional[Entity]:
        path = self._folder(entity_type) / f"{slug}.md"
        if not path.exists():
            return None
        return entity_from_markdown(path.read_text(encoding="utf-8"))

    def all_entities(self, entity_type: Optional[EntityType] = None) -> list[Entity]:
        types = [entity_type] if entity_type else list(EntityType)
        out: list[Entity] = []
        for et in types:
            folder = self._folder(et)
            if not folder.exists():
                continue
            for path in folder.glob("*.md"):
                try:
                    out.append(entity_from_markdown(path.read_text(encoding="utf-8")))
                except (ValueError, KeyError):
                    continue
        return out

    def save_raw_session(self, session_number: int, text: str, source: str) -> Path:
        path = self.root / "raw" / f"session-{session_number:03d}-{source}.md"
        path.write_text(text, encoding="utf-8")
        return path

    def context_block(self, max_entities: int = 20) -> str:
        entities = self.all_entities()[:max_entities]
        if not entities:
            return "No campaign data yet."
        lines = [f"# {self.campaign_name} — Campaign Memory", ""]
        by_type: dict[str, list[Entity]] = {}
        for e in entities:
            by_type.setdefault(e.entity_type.value + "s", []).append(e)
        for type_label, group in by_type.items():
            lines.append(f"## {type_label.title()}")
            for e in group:
                snippet = e.body_md.replace("\n", " ")[:120]
                lines.append(f"- **{e.name}**: {snippet}")
            lines.append("")
        return "\n".join(lines)
