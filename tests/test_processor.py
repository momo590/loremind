"""Tests for session note processing."""
from __future__ import annotations
from unittest.mock import MagicMock, patch
import json
import pytest

from loremind.processor import SessionProcessor
from loremind.schema import SessionDump, EntityType


@pytest.fixture
def tmp_store(tmp_path):
    from loremind.store import CampaignStore
    return CampaignStore.__new__(CampaignStore)


@pytest.fixture
def mock_store(tmp_path):
    from loremind.store import CampaignStore
    import loremind.store as adapter
    adapter.CAMPAIGNS_DIR = tmp_path
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
        "details": {"allegiance": "neutral", "location": "Iron District"},
        "tags": ["blacksmith", "iron-district"],
    }])

    with patch("anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_anthropic_response(entities_json)

        processor = SessionProcessor(mock_store, api_key="test-key")
        dump = SessionDump(session_number=1, raw_text="Brask hates the temple, silver coin scar on left hand", source="test")
        entities = processor.process(dump)

    assert len(entities) == 1
    assert entities[0].name == "Brask the Lopsided"
    assert entities[0].entity_type == EntityType.NPC
    assert "silver coin scar" in entities[0].summary


def test_processor_saves_to_disk(mock_store):
    entities_json = json.dumps([{
        "name": "Iron Circle HQ",
        "entity_type": "location",
        "summary": "Fortified warehouse district controlled by the Iron Circle faction.",
        "details": {},
        "tags": ["iron-circle"],
    }])

    with patch("anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_anthropic_response(entities_json)

        processor = SessionProcessor(mock_store, api_key="test-key")
        dump = SessionDump(session_number=2, raw_text="Iron Circle HQ is in warehouse district", source="test")
        processor.process(dump)

    saved = mock_store.root / "locations" / "iron-circle-hq.md"
    assert saved.exists()
    assert "Iron Circle HQ" in saved.read_text()
