"""Model routing — provider family detection and LiteLLM model string construction.

Pure functions, no I/O, no async, no state.
"""

from __future__ import annotations


def get_provider_family(provider: str, model: str) -> str:
    """Return the provider family for prompt template selection.

    Handles cross-combinations (e.g., provider="openai" with model="claude-*" for proxies).
    Unknown provider/model combinations default to "openai" (JSON format, safest).
    """
    p, m = provider.lower(), model.lower()
    if p == "anthropic" or m.startswith("claude"):
        return "claude"
    if p == "deepseek" or m.startswith("deepseek"):
        return "deepseek"
    if p == "google" or m.startswith("gemini"):
        return "google"
    # openai or unknown → default JSON format
    return "openai"


def get_litellm_model_string(provider: str, model: str) -> str:
    """Return the LiteLLM model string for the given provider and model.

    Example: provider="anthropic", model="claude-opus-4-5" → "anthropic/claude-opus-4-5"
    """
    return f"{provider}/{model}"
