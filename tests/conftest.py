"""Shared test fixtures."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def claude_tool_response():
    """Build a mocked Anthropic messages.create() response containing a tool_use block.

    ClaudeProvider (post-T5) reads response.content for a tool_use block whose .input
    holds the structured entity dict — never parses raw JSON text. Tests mirror that.
    """
    def _make(entities_payload: list[dict]):
        block = MagicMock()
        block.type = "tool_use"
        block.name = "record_entities"
        block.input = {"entities": list(entities_payload)}
        msg = MagicMock()
        msg.content = [block]
        return msg

    return _make
