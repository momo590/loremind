"""TTRPG entity types stored in the campaign wiki."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional
import json


class EntityType(str, Enum):
    """6 first-class types per the locked v0.1 plan (subagent tie-break vs Codex)."""
    NPC = "npc"
    LOCATION = "location"
    FACTION = "faction"
    ITEM = "item"
    THREAD = "thread"  # unresolved plot thread — see ThreadSubtype below
    LORE = "lore"      # worldbuilding facts, history


class ThreadSubtype(str, Enum):
    """Thread is a unified type with three workflow subtypes."""
    PROMISE = "promise"            # GM promised something, owes the players
    CONTRADICTION = "contradiction"  # GM contradicted earlier canon, needs resolution
    REMINDER = "reminder"          # forgot to address something, queue for next session


@dataclass
class CampaignEntity:
    name: str
    entity_type: EntityType
    summary: str
    details: dict = field(default_factory=dict)
    first_seen_session: int = 0
    last_updated_session: int = 0
    raw_fragments: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    # Only meaningful when entity_type == THREAD
    thread_subtype: Optional[ThreadSubtype] = None
    # Always-on source provenance — required for review mode + trust
    source_session: Optional[int] = None
    source_snippet: Optional[str] = None

    def to_markdown(self) -> str:
        lines = [
            f"# {self.name}",
            f"**Type:** {self.entity_type.value}",
            f"**First seen:** session {self.first_seen_session}",
            f"**Last updated:** session {self.last_updated_session}",
            "",
            "## Summary",
            self.summary,
        ]
        if self.details:
            lines += ["", "## Details"]
            for k, v in self.details.items():
                lines.append(f"- **{k}:** {v}")
        if self.tags:
            lines += ["", f"**Tags:** {', '.join(self.tags)}"]
        return "\n".join(lines)

    def slug(self) -> str:
        return self.name.lower().replace(" ", "-").replace("'", "").replace('"', "")


@dataclass
class SessionDump:
    """Raw notes from one GM session, before processing."""
    session_number: int
    raw_text: str
    source: str  # "cli", "stdin", "audio", "whatsapp", "clicky"
    captured_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    image_paths: list[str] = field(default_factory=list)
