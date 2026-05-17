"""Tests for fuzzy-match entity merge (T4)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from loremind.processor import SessionProcessor
from loremind.schema import EntityType, Faction, Location, NPC, SessionDump


@pytest.fixture
def mock_store(tmp_path):
    from loremind.store import CampaignStore
    import loremind.store as store_module
    store_module.CAMPAIGNS_DIR = tmp_path
    return CampaignStore("merge-test")


def _mock_claude(entities_payload: list[dict]):
    msg = MagicMock()
    msg.content = [MagicMock(text=json.dumps(entities_payload))]
    return msg


def _run_processor(mock_store, entities_payload, session_number=1, raw_text="notes"):
    with patch("loremind.llm.claude_provider.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_claude(entities_payload)
        processor = SessionProcessor(mock_store, api_key="test-key")
        dump = SessionDump(session_number=session_number, raw_text=raw_text, source="test")
        return processor.process(dump)


def test_brask_and_captain_brask_merge(mock_store):
    """Session 1 introduces 'Brask'; session 2 elaborates as 'Captain Brask'.
    Fuzzy match (partial_ratio = 100) folds the second into the first."""
    _run_processor(
        mock_store,
        [{
            "name": "Brask",
            "entity_type": "npc",
            "summary": "Half-orc blacksmith.",
        }],
        session_number=1,
        raw_text="Brask the smith greeted us",
    )

    _run_processor(
        mock_store,
        [{
            "name": "Captain Brask",
            "entity_type": "npc",
            "summary": "Reveals himself as captain of the city watch.",
        }],
        session_number=2,
        raw_text="captain brask turned on us",
    )

    npcs = mock_store.all_entities(EntityType.NPC)
    assert len(npcs) == 1, f"expected merge into 1 NPC, got {len(npcs)}: {[e.name for e in npcs]}"
    merged = npcs[0]
    assert merged.name == "Brask"  # canonical name preserved
    assert "Half-orc blacksmith" in merged.body_md
    assert "captain of the city watch" in merged.body_md
    assert merged.frontmatter["first_seen_session"] == 1
    assert merged.frontmatter["last_updated_session"] == 2
    assert "Brask the smith greeted us" in merged.frontmatter["raw_fragments"]
    assert "captain brask turned on us" in merged.frontmatter["raw_fragments"]


def test_below_threshold_creates_new(mock_store):
    """'Brask' (~5 chars) vs 'Brock' (~5 chars) should score below 85 on partial_ratio
    and therefore stay as two separate NPCs."""
    _run_processor(
        mock_store,
        [{"name": "Brask", "entity_type": "npc", "summary": "Half-orc smith."}],
        session_number=1,
    )
    _run_processor(
        mock_store,
        [{"name": "Brock", "entity_type": "npc", "summary": "Dwarven warrior."}],
        session_number=2,
    )

    npcs = mock_store.all_entities(EntityType.NPC)
    names = sorted(e.name for e in npcs)
    assert names == ["Brask", "Brock"], names


def test_merge_preserves_both_bodies(mock_store):
    existing = NPC(name="Brask", body_md="First note.")
    mock_store.save_entity(existing)

    new = NPC(name="Brask the Lopsided", body_md="Second note adds the silver-coin scar.")
    merged = mock_store.merge_entity(existing, new)

    assert "First note." in merged.body_md
    assert "Second note adds the silver-coin scar." in merged.body_md
    # Newlines separate concatenated bodies
    assert merged.body_md.count("\n\n") >= 1


def test_merge_idempotent_when_new_body_is_subset(mock_store):
    """Re-merging the same content should not duplicate text."""
    existing = NPC(name="Brask", body_md="The smith of Iron District.")
    new = NPC(name="Brask", body_md="The smith of Iron District.")
    merged = mock_store.merge_entity(existing, new)
    assert merged.body_md.count("The smith of Iron District.") == 1


def test_merge_dedups_frontmatter_lists(mock_store):
    existing = NPC(name="Brask", frontmatter={"tags": ["smith", "iron"]})
    new = NPC(name="Brask", frontmatter={"tags": ["iron", "captain"]})
    merged = mock_store.merge_entity(existing, new)
    # Order preserved, "iron" not duplicated, "captain" appended
    assert merged.frontmatter["tags"] == ["smith", "iron", "captain"]


def test_merge_takes_new_typed_field_when_existing_empty(mock_store):
    existing = NPC(name="Brask", role="")  # no role yet
    new = NPC(name="Brask", role="captain")
    merged = mock_store.merge_entity(existing, new)
    assert merged.role == "captain"


def test_merge_keeps_existing_typed_field_when_set(mock_store):
    existing = NPC(name="Brask", role="blacksmith")
    new = NPC(name="Brask", role="captain")  # contradictory
    merged = mock_store.merge_entity(existing, new)
    assert merged.role == "blacksmith"  # existing canonical wins on conflict


def test_find_similar_filters_by_entity_type(mock_store):
    """Iron Circle (Faction) and Iron Citadel (Location) share a prefix but
    must not collide because they live in different folders."""
    mock_store.save_entity(Faction(name="Iron Circle", alignment="neutral"))
    mock_store.save_entity(Location(name="Iron Citadel", region="The Frontier"))

    npc_match = mock_store.find_similar("Iron Captain", EntityType.NPC)
    assert npc_match is None  # no NPCs in store

    fac_match = mock_store.find_similar("Iron Circle", EntityType.FACTION)
    assert fac_match is not None
    assert fac_match.name == "Iron Circle"


def test_processor_passes_existing_names_to_llm(mock_store):
    """Round 2 should receive 'Brask' in the existing_entity_names slot."""
    mock_store.save_entity(NPC(name="Brask", body_md="Round 1."))

    captured = {}

    with patch("loremind.llm.claude_provider.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_claude([
            {"name": "Brask", "entity_type": "npc", "summary": "Round 2."},
        ])
        processor = SessionProcessor(mock_store, api_key="test-key")
        processor.process(SessionDump(session_number=2, raw_text="more brask", source="test"))
        captured["prompt"] = mock_client.messages.create.call_args.kwargs["messages"][0]["content"]

    sent = captured["prompt"]
    assert "Brask" in sent
    assert "Known canonical entity names" in sent
