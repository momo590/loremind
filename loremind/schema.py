"""TTRPG entity hierarchy (T3 of the v0.1 plan).

Six first-class entity types: NPC, Location, Faction, Item, Thread, Lore.
Thread carries two enums (subtype, status). Each subclass adds typed fields;
arbitrary extras live in `frontmatter`. Markdown serialization uses a JSON
frontmatter block (no YAML dep).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, fields as dc_fields
from datetime import datetime, timezone
from enum import Enum
from typing import ClassVar, Optional


class EntityType(str, Enum):
    NPC = "npc"
    LOCATION = "location"
    FACTION = "faction"
    ITEM = "item"
    THREAD = "thread"
    LORE = "lore"


class ThreadSubtype(str, Enum):
    PROMISE = "promise"
    CONTRADICTION = "contradiction"
    REMINDER = "reminder"


class ThreadStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    return _SLUG_RE.sub("-", name.lower()).strip("-")


@dataclass
class Entity:
    """Base for all TTRPG entities. Subclasses declare type-specific fields."""

    name: str = ""
    id: str = ""
    body_md: str = ""
    frontmatter: dict = field(default_factory=dict)

    ENTITY_TYPE: ClassVar[Optional[EntityType]] = None  # set by subclasses

    def __post_init__(self) -> None:
        if not self.id:
            self.id = slugify(self.name)

    @property
    def slug(self) -> str:
        return slugify(self.name)

    @property
    def entity_type(self) -> EntityType:
        if self.ENTITY_TYPE is None:
            raise TypeError("Entity is abstract; instantiate a concrete subclass.")
        return self.ENTITY_TYPE

    def _typed_field_names(self) -> list[str]:
        base_names = {"name", "id", "body_md", "frontmatter"}
        return [f.name for f in dc_fields(self) if f.name not in base_names]

    def to_frontmatter_dict(self) -> dict:
        out: dict = {
            "id": self.id,
            "name": self.name,
            "type": self.entity_type.value,
        }
        for fname in self._typed_field_names():
            v = getattr(self, fname)
            if isinstance(v, Enum):
                v = v.value
            out[fname] = v
        if self.frontmatter:
            out["frontmatter"] = dict(self.frontmatter)
        return out

    def to_markdown(self) -> str:
        fm = self.to_frontmatter_dict()
        blob = json.dumps(fm, indent=2, ensure_ascii=False, default=_json_default)
        return f"---\n{blob}\n---\n\n# {self.name}\n\n{self.body_md}\n"


def _json_default(o):
    if isinstance(o, Enum):
        return o.value
    if isinstance(o, datetime):
        return o.isoformat()
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")


@dataclass
class NPC(Entity):
    role: str = ""
    faction: str = ""
    notes: str = ""

    ENTITY_TYPE: ClassVar[EntityType] = EntityType.NPC


@dataclass
class Location(Entity):
    parent_location: str = ""
    region: str = ""

    ENTITY_TYPE: ClassVar[EntityType] = EntityType.LOCATION


@dataclass
class Faction(Entity):
    alignment: str = ""
    members_ref: list = field(default_factory=list)

    ENTITY_TYPE: ClassVar[EntityType] = EntityType.FACTION


@dataclass
class Item(Entity):
    owner_ref: str = ""
    properties: dict = field(default_factory=dict)

    ENTITY_TYPE: ClassVar[EntityType] = EntityType.ITEM


@dataclass
class Thread(Entity):
    subtype: ThreadSubtype = ThreadSubtype.PROMISE
    status: ThreadStatus = ThreadStatus.OPEN
    related_entities_refs: list = field(default_factory=list)

    ENTITY_TYPE: ClassVar[EntityType] = EntityType.THREAD

    def __post_init__(self) -> None:
        super().__post_init__()
        # Coerce strings to enum (raises ValueError on invalid value)
        if not isinstance(self.subtype, ThreadSubtype):
            self.subtype = ThreadSubtype(self.subtype)
        if not isinstance(self.status, ThreadStatus):
            self.status = ThreadStatus(self.status)


@dataclass
class Lore(Entity):
    era: str = ""
    tags: list = field(default_factory=list)

    ENTITY_TYPE: ClassVar[EntityType] = EntityType.LORE


ENTITY_TYPE_REGISTRY: dict[EntityType, type[Entity]] = {
    EntityType.NPC: NPC,
    EntityType.LOCATION: Location,
    EntityType.FACTION: Faction,
    EntityType.ITEM: Item,
    EntityType.THREAD: Thread,
    EntityType.LORE: Lore,
}


_LLM_TYPED_KEYS: dict[EntityType, tuple[str, ...]] = {
    EntityType.NPC: ("role", "faction", "notes"),
    EntityType.LOCATION: ("parent_location", "region"),
    EntityType.FACTION: ("alignment", "members_ref"),
    EntityType.ITEM: ("owner_ref", "properties"),
    EntityType.THREAD: ("subtype", "status", "related_entities_refs"),
    EntityType.LORE: ("era", "tags"),
}


def entity_from_llm_dict(d: dict) -> Entity:
    """Convert an LLM-emitted dict ({"entity_type", "name", "summary", "details", "tags"})
    into the correct Entity subclass."""
    raw_type = (d.get("entity_type") or d.get("type") or "").lower()
    # Map legacy "event" → "thread" so the old prompt schema still routes cleanly
    if raw_type == "event":
        raw_type = "thread"
    enum = EntityType(raw_type)
    cls = ENTITY_TYPE_REGISTRY[enum]

    name = d.get("name", "")
    body_md = d.get("summary") or d.get("body_md") or ""
    details = dict(d.get("details") or {})
    tags = list(d.get("tags") or [])

    typed_kwargs: dict = {}
    for key in _LLM_TYPED_KEYS[enum]:
        if key in details:
            typed_kwargs[key] = details.pop(key)
    # Some LLMs put typed fields at the top level instead of under details
    for key in _LLM_TYPED_KEYS[enum]:
        if key not in typed_kwargs and key in d:
            typed_kwargs[key] = d[key]

    frontmatter = details
    if tags:
        frontmatter["tags"] = tags

    return cls(name=name, body_md=body_md, frontmatter=frontmatter, **typed_kwargs)


def entity_from_markdown(text: str) -> Entity:
    """Parse a markdown file produced by Entity.to_markdown() back into an Entity."""
    if not text.startswith("---\n"):
        raise ValueError("Missing JSON frontmatter block at start of markdown.")
    rest = text[4:]
    end_marker = rest.find("\n---")
    if end_marker < 0:
        raise ValueError("Unclosed frontmatter block.")
    fm_text = rest[:end_marker]
    body = rest[end_marker + len("\n---"):].lstrip("\n")

    if body.startswith("# "):
        nl = body.find("\n")
        body = body[nl + 1:] if nl >= 0 else ""
    body = body.strip()

    fm = json.loads(fm_text)
    enum = EntityType(fm["type"])
    cls = ENTITY_TYPE_REGISTRY[enum]

    typed_kwargs = {}
    for key in _LLM_TYPED_KEYS[enum]:
        if key in fm:
            typed_kwargs[key] = fm[key]

    extras = fm.get("frontmatter", {}) or {}
    return cls(
        id=fm.get("id", ""),
        name=fm["name"],
        body_md=body,
        frontmatter=extras,
        **typed_kwargs,
    )


@dataclass
class SessionDump:
    """Raw notes from one GM session, before processing."""
    session_number: int
    raw_text: str
    source: str
    captured_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    image_paths: list = field(default_factory=list)
