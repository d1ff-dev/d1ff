"""Tests for model_router — provider family detection and LiteLLM model string."""

from d1ff.providers.model_router import get_litellm_model_string, get_provider_family


def test_get_provider_family_anthropic() -> None:
    """provider='anthropic' → 'claude'."""
    assert get_provider_family("anthropic", "claude-opus-4-5") == "claude"


def test_get_provider_family_claude_model() -> None:
    """Model name starting with 'claude' takes precedence over provider."""
    assert get_provider_family("openai", "claude-3-5-sonnet") == "claude"


def test_get_provider_family_openai() -> None:
    """provider='openai' with GPT model → 'openai'."""
    assert get_provider_family("openai", "gpt-4o") == "openai"


def test_get_provider_family_deepseek() -> None:
    """provider='deepseek' → 'deepseek'."""
    assert get_provider_family("deepseek", "deepseek-chat") == "deepseek"


def test_get_provider_family_google() -> None:
    """provider='google' with gemini model → 'google'."""
    assert get_provider_family("google", "gemini-1.5-pro") == "google"


def test_get_provider_family_unknown_defaults_to_openai() -> None:
    """Unknown provider and model → defaults to 'openai' (JSON format, safest)."""
    assert get_provider_family("unknown", "some-model") == "openai"


def test_get_provider_family_gemini_model_without_google_provider() -> None:
    """model starting with 'gemini' → 'google' regardless of provider."""
    assert get_provider_family("openai", "gemini-pro") == "google"


def test_get_provider_family_deepseek_model_without_deepseek_provider() -> None:
    """model starting with 'deepseek' → 'deepseek' regardless of provider."""
    assert get_provider_family("custom", "deepseek-r1") == "deepseek"


def test_get_litellm_model_string() -> None:
    """Returns 'provider/model' format."""
    assert get_litellm_model_string("anthropic", "claude-opus-4-5") == "anthropic/claude-opus-4-5"


def test_get_litellm_model_string_openai() -> None:
    """Returns 'provider/model' format for openai."""
    assert get_litellm_model_string("openai", "gpt-4o") == "openai/gpt-4o"
