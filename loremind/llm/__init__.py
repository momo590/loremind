"""LLM provider factory. `LOREMIND_LLM` env var picks the backend; default = ollama."""
from __future__ import annotations

import os
from typing import Optional

from loremind.llm.base import LLMProvider


KNOWN_PROVIDERS = ("ollama", "claude", "openai")
DEFAULT_PROVIDER = "ollama"


def get_llm(provider: Optional[str] = None, **kwargs) -> LLMProvider:
    """Return the LLM provider instance for `provider` (env override: LOREMIND_LLM)."""
    name = (provider or os.environ.get("LOREMIND_LLM", DEFAULT_PROVIDER)).lower()

    if name == "ollama":
        from loremind.llm.ollama_provider import OllamaProvider
        return OllamaProvider(**kwargs)
    if name == "claude":
        from loremind.llm.claude_provider import ClaudeProvider
        return ClaudeProvider(**kwargs)
    if name == "openai":
        from loremind.llm.openai_provider import OpenAIProvider
        return OpenAIProvider(**kwargs)

    raise ValueError(
        f"Unknown LLM provider {name!r}. Choices: {', '.join(KNOWN_PROVIDERS)}."
    )


__all__ = ["LLMProvider", "get_llm", "KNOWN_PROVIDERS", "DEFAULT_PROVIDER"]
