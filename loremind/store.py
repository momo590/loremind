"""Campaign store — per-campaign markdown wiki on disk.

Each entity is one markdown file under `~/.loremind/campaigns/<name>/<type>s/<slug>.md`.
The file starts with a JSON frontmatter block (see schema.Entity.to_markdown) so we
can round-trip without a YAML dep.
"""
from __future__ import annotations

from dataclasses import fields as dc_fields
from pathlib import Path
from typing import Optional

from rapidfuzz import fuzz

from loremind.schema import (
    Entity,
    EntityType,
    entity_from_markdown,
)


DEFAULT_MERGE_THRESHOLD = 85
_BASE_ENTITY_FIELDS = {"name", "id", "body_md", "frontmatter"}


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

    def find_similar(
        self,
        name: str,
        entity_type: Optional[EntityType] = None,
        threshold: int = DEFAULT_MERGE_THRESHOLD,
    ) -> Optional[Entity]:
        """Return the highest-scoring entity with `fuzz.partial_ratio >= threshold`, or None.

        Filters by `entity_type` when given — NPCs only match NPCs, etc. This stops
        "Iron Citadel" (Location) from merging into "Iron Circle" (Faction).
        """
        candidates = self.all_entities(entity_type)
        best: Optional[Entity] = None
        best_score = -1.0
        target = name.lower()
        for c in candidates:
            score = fuzz.partial_ratio(target, c.name.lower())
            if score >= threshold and score > best_score:
                best = c
                best_score = score
        return best

    def merge_entity(self, existing: Entity, new: Entity) -> Entity:
        """Fold `new` into `existing` in place and return existing (caller persists).

        - Bodies are concatenated when `new.body_md` is fresh.
        - Frontmatter lists are union'd with order preserved (dedup).
        - Frontmatter dicts are shallow-merged (new wins on key conflict).
        - Frontmatter scalars keep existing as canonical (except session-tracking
          keys, which the processor refreshes after merge).
        - Typed dataclass fields take `new` only when `existing` is empty.
        """
        new_body = new.body_md.strip() if new.body_md else ""
        if new_body and new_body not in (existing.body_md or ""):
            if existing.body_md.strip():
                existing.body_md = existing.body_md.rstrip() + "\n\n" + new_body
            else:
                existing.body_md = new_body

        for key, new_val in new.frontmatter.items():
            if key not in existing.frontmatter:
                existing.frontmatter[key] = new_val
                continue
            existing_val = existing.frontmatter[key]
            if isinstance(existing_val, list) and isinstance(new_val, list):
                merged = list(existing_val)
                for item in new_val:
                    if item not in merged:
                        merged.append(item)
                existing.frontmatter[key] = merged
            elif isinstance(existing_val, dict) and isinstance(new_val, dict):
                existing.frontmatter[key] = {**existing_val, **new_val}
            # else: scalar conflict → keep existing as canonical

        for f in dc_fields(existing):
            if f.name in _BASE_ENTITY_FIELDS:
                continue
            try:
                existing_val = getattr(existing, f.name)
                new_val = getattr(new, f.name)
            except AttributeError:
                continue
            if not existing_val and new_val:
                setattr(existing, f.name, new_val)

        return existing

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
