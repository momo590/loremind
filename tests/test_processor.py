"""Tests for session note processing."""
from __future__ import annotations
import json
from unittest.mock import MagicMock, patch

import pytest

from loremind.processor import SessionProcessor
from loremind.schema import NPC, Location, SessionDump


@pytest.fixture
def mock_store(tmp_path):
    from loremind.store import CampaignStore
    import loremind.store as store_module
    store_module.CAMPAIGNS_DIR = tmp_path
    return CampaignStore("test-campaign")


def _mock_anthropic_response(entities_json: str):
    msg = MagicMock()
    msg.content = [MagicMock(text=entities_json)]
    return msg


def test_processor_extracts_npc(mock_store):
    entities_json = json.dumps([{
        "name": "Brask the Lopsided",
        "entity_type": "npc",
        "summary": "Half-orc blacksmith with a silver coin scar on left hand.",
        "details": {"role": "blacksmith", "location": "Iron District"},
        "tags": ["blacksmith", "iron-district"],
    }])

    with patch("loremind.llm.claude_provider.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_anthropic_response(entities_json)

        processor = SessionProcessor(mock_store, api_key="test-key")
        dump = SessionDump(
            session_number=1,
            raw_text="Brask hates the temple, silver coin scar on left hand",
            source="test",
        )
        entities = processor.process(dump)

    assert len(entities) == 1
    npc = entities[0]
    assert isinstance(npc, NPC)
    assert npc.name == "Brask the Lopsided"
    assert "silver coin scar" in npc.body_md
    assert npc.role == "blacksmith"


def test_processor_saves_to_disk(mock_store):
    entities_json = json.dumps([{
        "name": "Iron Circle HQ",
        "entity_type": "location",
        "summary": "Fortified warehouse district controlled by the Iron Circle faction.",
        "details": {"region": "Iron District"},
        "tags": ["iron-circle"],
    }])

    with patch("loremind.llm.claude_provider.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_anthropic_response(entities_json)

        processor = SessionProcessor(mock_store, api_key="test-key")
        dump = SessionDump(
            session_number=2,
            raw_text="Iron Circle HQ is in warehouse district",
            source="test",
        )
        entities = processor.process(dump)

    assert len(entities) == 1
    assert isinstance(entities[0], Location)
    saved = mock_store.root / "locations" / "iron-circle-hq.md"
    assert saved.exists()
    assert "Iron Circle HQ" in saved.read_text()


def test_processor_writes_session_provenance_to_frontmatter(mock_store):
    entities_json = json.dumps([{
        "name": "Captain Brask",
        "entity_type": "npc",
        "summary": "Captain of the watch.",
    }])

    with patch("loremind.llm.claude_provider.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_anthropic_response(entities_json)

        processor = SessionProcessor(mock_store, api_key="test-key")
        dump = SessionDump(session_number=7, raw_text="watch captain", source="test")
        entities = processor.process(dump)

    npc = entities[0]
    assert npc.frontmatter["first_seen_session"] == 7
    assert npc.frontmatter["last_updated_session"] == 7
    assert npc.frontmatter["raw_fragments"] == ["watch captain"]
