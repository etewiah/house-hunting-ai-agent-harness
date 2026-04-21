from __future__ import annotations

import os


def load_llm():
    """Detect and return an LlmAdapter based on environment variables.

    Priority:
      1. LLM_PROVIDER env var (explicit override)
      2. ANTHROPIC_API_KEY present → AnthropicAdapter
      3. OPENAI_API_KEY present → OpenAIAdapter
      4. OPENAI_BASE_URL present (local/Ollama, no key needed) → OpenAIAdapter
      5. None → demo mode (regex fallback)

    Environment variables:
      LLM_PROVIDER        anthropic | openai | ollama | groq | together | lm_studio
      ANTHROPIC_API_KEY   required for Anthropic
      OPENAI_API_KEY      required for OpenAI/Groq/Together; not needed for Ollama
      OPENAI_BASE_URL     override API endpoint (e.g. http://localhost:11434/v1 for Ollama)
      OPENAI_MODEL        model name for OpenAI-compatible providers (default: gpt-4o-mini)
    """
    provider = os.getenv("LLM_PROVIDER", "").lower()

    if provider in ("openai", "ollama", "groq", "together", "lm_studio"):
        return _load_openai()

    if provider == "anthropic":
        return _load_anthropic()

    # Auto-detect from available keys
    if os.getenv("ANTHROPIC_API_KEY"):
        return _load_anthropic()

    if os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_BASE_URL"):
        return _load_openai()

    return None


def _load_anthropic():
    try:
        from src.connectors.anthropic_adapter import AnthropicAdapter
        return AnthropicAdapter()
    except Exception as exc:
        raise RuntimeError(f"Failed to load Anthropic adapter: {exc}") from exc


def _load_openai():
    try:
        from src.connectors.openai_adapter import OpenAIAdapter
        return OpenAIAdapter()
    except ImportError:
        raise ImportError(
            "openai package not installed. Run: uv add openai"
        )
    except Exception as exc:
        raise RuntimeError(f"Failed to load OpenAI adapter: {exc}") from exc
