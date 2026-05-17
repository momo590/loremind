"""Tests for the LLMProvider abstraction (T2)."""
from __future__ import annotations

import inspect
import json
from unittest.mock import MagicMock, patch

import pytest

from loremind.llm import KNOWN_PROVIDERS, get_llm
from loremind.llm.base import LLMProvider
from loremind.llm.claude_provider import ClaudeProvider
from loremind.llm.ollama_provider import OllamaProvider
from loremind.llm.openai_provider import OpenAIProvider
from loremind.schema import EntityType, Location, NPC


def test_factory_returns_ollama_by_default(monkeypatch):
    monkeypatch.delenv("LOREMIND_LLM", raising=False)
    llm = get_llm()
    assert isinstance(llm, OllamaProvider)


def test_factory_returns_claude_when_env_set(monkeypatch):
    monkeypatch.setenv("LOREMIND_LLM", "claude")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    llm = get_llm()
    assert isinstance(llm, ClaudeProvider)


def test_factory_returns_openai_when_env_set(monkeypatch):
    monkeypatch.setenv("LOREMIND_LLM", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    llm = get_llm()
    assert isinstance(llm, OpenAIProvider)


def test_factory_raises_on_unknown_provider():
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        get_llm(provider="not-a-real-llm")


def test_factory_explicit_provider_overrides_env(monkeypatch):
    monkeypatch.setenv("LOREMIND_LLM", "claude")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    llm = get_llm(provider="ollama")
    assert isinstance(llm, OllamaProvider)


def test_known_providers_constant():
    assert set(KNOWN_PROVIDERS) == {"ollama", "claude", "openai"}


def _fake_anthropic_message(payload_text: str):
    msg = MagicMock()
    msg.content = [MagicMock(text=payload_text)]
    return msg


def test_claude_provider_extract_entities():
    entities_json = json.dumps([
        {
            "name": "Brask the Lopsided",
            "entity_type": "npc",
            "summary": "Half-orc smith.",
            "details": {"location": "Iron District"},
            "tags": ["smith"],
        }
    ])

    with patch("loremind.llm.claude_provider.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = _fake_anthropic_message(entities_json)

        provider = ClaudeProvider(api_key="test-key")
        entities = provider.extract_entities(
            "Brask the smith, Iron District",
            {"existing_context": ""},
        )

    assert len(entities) == 1
    e = entities[0]
    assert isinstance(e, NPC)
    assert e.name == "Brask the Lopsided"
    assert e.entity_type is EntityType.NPC
    assert e.frontmatter["location"] == "Iron District"
    assert e.frontmatter["tags"] == ["smith"]
    # Ensure prompt formatting did not choke on JSON braces in the schema example
    call_kwargs = mock_client.messages.create.call_args.kwargs
    sent_prompt = call_kwargs["messages"][0]["content"]
    assert "Brask" in sent_prompt  # raw notes interpolated
    assert '"key": "value"' in sent_prompt  # JSON example survived format()


def test_claude_provider_strips_markdown_fences():
    fenced = "```json\n" + json.dumps([
        {"name": "X", "entity_type": "npc", "summary": "y"}
    ]) + "\n```"

    with patch("loremind.llm.claude_provider.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = _fake_anthropic_message(fenced)
        provider = ClaudeProvider(api_key="test-key")
        entities = provider.extract_entities("anything", {})
    assert len(entities) == 1
    assert entities[0].name == "X"


def test_ollama_provider_signature_matches_abc():
    for method_name in ("extract_entities", "ocr_image", "transcribe_audio"):
        abc_sig = inspect.signature(getattr(LLMProvider, method_name))
        impl_sig = inspect.signature(getattr(OllamaProvider, method_name))
        assert list(abc_sig.parameters) == list(impl_sig.parameters), (
            f"{method_name}: ABC params {list(abc_sig.parameters)} "
            f"!= impl {list(impl_sig.parameters)}"
        )


def test_ollama_provider_extract_entities_uses_urlopen():
    entities_json = json.dumps([
        {"name": "Iron Citadel", "entity_type": "location", "summary": "Fortress."}
    ])
    fake_resp_body = json.dumps({"response": entities_json}).encode("utf-8")

    fake_resp = MagicMock()
    fake_resp.read.return_value = fake_resp_body
    fake_resp.__enter__ = lambda self: self
    fake_resp.__exit__ = lambda self, *exc: False

    with patch("loremind.llm.ollama_provider.urllib.request.urlopen", return_value=fake_resp):
        provider = OllamaProvider()
        entities = provider.extract_entities("Iron Citadel sits on the hill", {})

    assert len(entities) == 1
    assert isinstance(entities[0], Location)
    assert entities[0].entity_type is EntityType.LOCATION


def test_provider_stubs_raise_not_implemented():
    provider = OllamaProvider()
    with pytest.raises(NotImplementedError):
        provider.ocr_image("/tmp/img.png")
    with pytest.raises(NotImplementedError):
        provider.transcribe_audio("/tmp/audio.m4a")
