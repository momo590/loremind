"""Tests for the LLMProvider abstraction (T2) and function-calling layer (T5)."""
from __future__ import annotations

import inspect
import json
from unittest.mock import MagicMock, patch

import pytest

from loremind.llm import KNOWN_PROVIDERS, get_llm
from loremind.llm.base import LLMProvider
from loremind.llm.claude_provider import ClaudeProvider, EXTRACT_TOOL, EXTRACT_TOOL_NAME
from loremind.llm.ollama_provider import OllamaProvider
from loremind.llm.openai_provider import OpenAIProvider
from loremind.schema import EntityType, Location, NPC


# --- factory ---


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


# --- Claude provider ---


def test_claude_provider_extract_entities(claude_tool_response):
    payload = [
        {
            "name": "Brask the Lopsided",
            "entity_type": "npc",
            "summary": "Half-orc smith.",
            "details": {"role": "blacksmith", "location": "Iron District"},
            "tags": ["smith"],
        }
    ]

    with patch("loremind.llm.claude_provider.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = claude_tool_response(payload)

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
    assert e.role == "blacksmith"
    assert e.frontmatter["location"] == "Iron District"


def test_claude_provider_uses_tool_use(claude_tool_response):
    """T5: ClaudeProvider must pass `tools=[EXTRACT_TOOL]` and force tool_choice."""
    with patch("loremind.llm.claude_provider.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = claude_tool_response([])

        provider = ClaudeProvider(api_key="test-key")
        provider.extract_entities("anything", {})

    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert "tools" in call_kwargs, "messages.create must be called with tools=[...]"
    assert call_kwargs["tools"] == [EXTRACT_TOOL]
    assert call_kwargs["tool_choice"] == {"type": "tool", "name": EXTRACT_TOOL_NAME}
    # Prompt still interpolates the merge instructions
    sent_prompt = call_kwargs["messages"][0]["content"]
    assert "Known canonical entity names" in sent_prompt


def test_claude_provider_returns_empty_when_no_tool_block():
    """Defensive: if the model returns no tool_use block (shouldn't happen with
    tool_choice but possible during testing), we degrade to an empty list."""
    bogus = MagicMock()
    bogus.content = [MagicMock(type="text")]
    with patch("loremind.llm.claude_provider.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = bogus
        provider = ClaudeProvider(api_key="test-key")
        assert provider.extract_entities("x", {}) == []


# --- Ollama provider ---


def _fake_urlopen(response_text: str):
    """Build a context-manager mock that mimics urllib.request.urlopen()."""
    cm = MagicMock()
    cm.read.return_value = json.dumps({"response": response_text}).encode("utf-8")
    cm.__enter__ = lambda self: self
    cm.__exit__ = lambda self, *exc: False
    return cm


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
    with patch(
        "loremind.llm.ollama_provider.urllib.request.urlopen",
        return_value=_fake_urlopen(entities_json),
    ):
        provider = OllamaProvider()
        entities = provider.extract_entities("Iron Citadel sits on the hill", {})

    assert len(entities) == 1
    assert isinstance(entities[0], Location)
    assert entities[0].entity_type is EntityType.LOCATION


def test_ollama_provider_uses_json_mode():
    """T5: the /api/generate payload must carry `format=json`."""
    captured_payloads = []

    def _capture(req, timeout=None):  # noqa: ARG001
        captured_payloads.append(json.loads(req.data.decode("utf-8")))
        return _fake_urlopen(json.dumps([{
            "name": "X", "entity_type": "npc", "summary": "y",
        }]))

    with patch("loremind.llm.ollama_provider.urllib.request.urlopen", side_effect=_capture):
        provider = OllamaProvider()
        provider.extract_entities("notes", {})

    assert captured_payloads, "expected one Ollama call"
    assert captured_payloads[0]["format"] == "json"
    assert captured_payloads[0]["stream"] is False


def test_ollama_provider_retries_once_on_malformed_json():
    """First /api/generate returns garbage → provider retries with a sharpening
    suffix → second call returns valid JSON → extract succeeds."""
    valid = json.dumps([{"name": "Brask", "entity_type": "npc", "summary": "smith"}])
    responses = iter([
        _fake_urlopen("not valid json at all{{"),
        _fake_urlopen(valid),
    ])

    captured_prompts: list[str] = []

    def _capture(req, timeout=None):  # noqa: ARG001
        captured_prompts.append(json.loads(req.data.decode("utf-8"))["prompt"])
        return next(responses)

    with patch("loremind.llm.ollama_provider.urllib.request.urlopen", side_effect=_capture):
        provider = OllamaProvider()
        entities = provider.extract_entities("notes", {})

    assert len(captured_prompts) == 2
    assert "IMPORTANT" in captured_prompts[1]  # retry prompt includes sharpening suffix
    assert len(entities) == 1
    assert entities[0].name == "Brask"


def test_ollama_provider_accepts_entities_wrapper():
    """Ollama JSON mode may wrap entities as {"entities": [...]}."""
    wrapped = json.dumps({"entities": [
        {"name": "X", "entity_type": "npc", "summary": "y"}
    ]})
    with patch(
        "loremind.llm.ollama_provider.urllib.request.urlopen",
        return_value=_fake_urlopen(wrapped),
    ):
        provider = OllamaProvider()
        entities = provider.extract_entities("notes", {})
    assert len(entities) == 1


def test_provider_stubs_raise_not_implemented():
    provider = OllamaProvider()
    with pytest.raises(NotImplementedError):
        provider.ocr_image("/tmp/img.png")
    with pytest.raises(NotImplementedError):
        provider.transcribe_audio("/tmp/audio.m4a")


# --- T5: zero-parse-failure stress ---


def test_100_claude_extractions_zero_parse_failures(claude_tool_response):
    """tool_use bypasses raw JSON parsing entirely; 100 mock calls should all succeed."""
    payload = [{"name": "Brask", "entity_type": "npc", "summary": "smith"}]
    with patch("loremind.llm.claude_provider.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = claude_tool_response(payload)
        provider = ClaudeProvider(api_key="test-key")
        for _ in range(100):
            entities = provider.extract_entities("notes", {})
            assert len(entities) == 1
            assert entities[0].name == "Brask"


def test_100_ollama_extractions_zero_parse_failures():
    """format=json + retry: 100 valid responses parse cleanly."""
    valid = json.dumps([{"name": "X", "entity_type": "npc", "summary": "y"}])

    def _always_valid(req, timeout=None):  # noqa: ARG001
        return _fake_urlopen(valid)

    with patch("loremind.llm.ollama_provider.urllib.request.urlopen", side_effect=_always_valid):
        provider = OllamaProvider()
        for _ in range(100):
            entities = provider.extract_entities("notes", {})
            assert len(entities) == 1
            assert entities[0].name == "X"
