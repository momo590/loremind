"""TTRPG entity types stored in the campaign wiki."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
import json


class EntityType(str, Enum):
    NPC = "npc"
    LOCATION = "location"
    FACTION = "faction"
    THREAD = "thread"  # unresolved plot thread
    EVENT = "event"    # notable session event
    ITEM = "item"      # significant item / artifact


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
    source: str  # "file", "whatsapp", "icloud_scan", "screen_capture"
    captured_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    image_paths: list[str] = field(default_factory=list)
