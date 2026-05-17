"""Tests for the Entity hierarchy (T3)."""
from __future__ import annotations

import json

import pytest

from loremind.schema import (
    ENTITY_TYPE_REGISTRY,
    Entity,
    EntityType,
    Faction,
    Item,
    Lore,
    Location,
    NPC,
    Thread,
    ThreadStatus,
    ThreadSubtype,
    entity_from_llm_dict,
    entity_from_markdown,
    slugify,
)


def test_each_type_validates():
    NPC(name="Brask", role="blacksmith", faction="iron-circle", notes="silver coin scar")
    Location(name="Iron Citadel", parent_location="Northreach", region="The Frontier")
    Faction(name="Iron Circle", alignment="neutral", members_ref=["brask"])
    Item(name="Sundering Hammer", owner_ref="brask", properties={"damage": "1d10"})
    Thread(name="Dragon-cult loyalty", subtype=ThreadSubtype.PROMISE)
    Lore(name="The Sundering", era="ancient", tags=["calamity"])


def test_registry_covers_all_types():
    assert set(ENTITY_TYPE_REGISTRY.keys()) == set(EntityType)
    assert ENTITY_TYPE_REGISTRY[EntityType.NPC] is NPC
    assert ENTITY_TYPE_REGISTRY[EntityType.THREAD] is Thread


def test_thread_subtype_enum_enforced():
    with pytest.raises(ValueError):
        Thread(name="bad", subtype="not-a-real-subtype")
    # str → enum coercion accepts valid values
    t = Thread(name="ok", subtype="reminder")
    assert t.subtype is ThreadSubtype.REMINDER


def test_thread_status_enum_enforced():
    with pytest.raises(ValueError):
        Thread(name="bad", status="halfway")
    t = Thread(name="closed", status="resolved")
    assert t.status is ThreadStatus.RESOLVED


def test_slug_generated_from_name():
    assert slugify("Brask the Lopsided") == "brask-the-lopsided"
    assert slugify("King's Court") == "king-s-court"
    assert slugify("  Trailing-Spaces  ") == "trailing-spaces"
    npc = NPC(name="Brask the Lopsided")
    assert npc.slug == "brask-the-lopsided"
    assert npc.id == "brask-the-lopsided"


def test_serialize_to_frontmatter_dict():
    npc = NPC(
        name="Brask",
        role="blacksmith",
        faction="iron-circle",
        notes="silver coin scar",
        body_md="A half-orc.",
        frontmatter={"first_seen_session": 1, "tags": ["smith"]},
    )
    fm = npc.to_frontmatter_dict()
    assert fm["type"] == "npc"
    assert fm["name"] == "Brask"
    assert fm["id"] == "brask"
    assert fm["role"] == "blacksmith"
    assert fm["faction"] == "iron-circle"
    assert fm["notes"] == "silver coin scar"
    assert fm["frontmatter"] == {"first_seen_session": 1, "tags": ["smith"]}


def test_thread_frontmatter_enum_values():
    t = Thread(
        name="Dragon cult",
        subtype=ThreadSubtype.PROMISE,
        status=ThreadStatus.OPEN,
        related_entities_refs=["brask", "iron-circle"],
    )
    fm = t.to_frontmatter_dict()
    assert fm["type"] == "thread"
    assert fm["subtype"] == "promise"
    assert fm["status"] == "open"
    assert fm["related_entities_refs"] == ["brask", "iron-circle"]


def test_deserialize_from_markdown_roundtrip():
    npc = NPC(
        name="Brask the Lopsided",
        role="blacksmith",
        faction="iron-circle",
        notes="silver coin scar",
        body_md="Half-orc blacksmith with a silver coin scar on left hand.",
        frontmatter={"tags": ["smith"]},
    )
    md = npc.to_markdown()

    parsed = entity_from_markdown(md)
    assert isinstance(parsed, NPC)
    assert parsed.name == "Brask the Lopsided"
    assert parsed.role == "blacksmith"
    assert parsed.faction == "iron-circle"
    assert parsed.body_md == "Half-orc blacksmith with a silver coin scar on left hand."
    assert parsed.frontmatter == {"tags": ["smith"]}


def test_deserialize_thread_roundtrip():
    thread = Thread(
        name="Dragon-cult loyalty",
        subtype=ThreadSubtype.CONTRADICTION,
        status=ThreadStatus.OPEN,
        related_entities_refs=["dragon-cult"],
        body_md="GM said dragons were extinct, then introduced one.",
    )
    md = thread.to_markdown()
    parsed = entity_from_markdown(md)
    assert isinstance(parsed, Thread)
    assert parsed.subtype is ThreadSubtype.CONTRADICTION
    assert parsed.status is ThreadStatus.OPEN
    assert parsed.related_entities_refs == ["dragon-cult"]


def test_entity_from_llm_dict_routes_to_correct_subclass():
    npc = entity_from_llm_dict({
        "name": "Brask",
        "entity_type": "npc",
        "summary": "Half-orc smith",
        "details": {"role": "blacksmith", "location": "Iron District"},
        "tags": ["smith"],
    })
    assert isinstance(npc, NPC)
    assert npc.name == "Brask"
    assert npc.role == "blacksmith"
    assert npc.body_md == "Half-orc smith"
    # location is not an NPC typed field, falls into frontmatter
    assert npc.frontmatter["location"] == "Iron District"
    assert npc.frontmatter["tags"] == ["smith"]


def test_entity_from_llm_dict_handles_legacy_event_type():
    thread = entity_from_llm_dict({
        "name": "Promise to the priest",
        "entity_type": "event",
        "summary": "GM owes the players a follow-up",
    })
    assert isinstance(thread, Thread)


def test_entity_from_llm_dict_rejects_unknown_type():
    with pytest.raises(ValueError):
        entity_from_llm_dict({"name": "X", "entity_type": "alien"})


def test_abstract_entity_cannot_report_type():
    e = Entity(name="abstract")
    with pytest.raises(TypeError):
        _ = e.entity_type


def test_to_markdown_includes_name_header():
    npc = NPC(name="Brask", body_md="Smith.")
    md = npc.to_markdown()
    assert md.startswith("---\n")
    assert "\n# Brask\n" in md
    assert "Smith." in md
    # Frontmatter is parseable JSON
    fm_block = md.split("---\n")[1]
    parsed = json.loads(fm_block.split("\n---")[0])
    assert parsed["type"] == "npc"
