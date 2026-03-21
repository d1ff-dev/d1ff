"""Tests for Docker configuration integrity.

Lightweight file-read + settings instantiation tests — no Docker daemon required.
"""

from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent


def _read_env_example() -> str:
    return (ROOT / ".env.example").read_text(encoding="utf-8")


def test_env_example_contains_required_vars() -> None:
    """All required environment variable names must appear in .env.example."""
    content = _read_env_example()
    required_vars = [
        "GITHUB_APP_ID",
        "GITHUB_PRIVATE_KEY",
        "GITHUB_WEBHOOK_SECRET",
        "ENCRYPTION_KEY",
    ]
    for var in required_vars:
        assert var in content, f"Required var {var!r} missing from .env.example"


def test_env_example_contains_optional_vars() -> None:
    """All optional environment variable names must appear in .env.example."""
    content = _read_env_example()
    optional_vars = [
        "DATABASE_URL",
        "MAX_CONCURRENT_REVIEWS",
        "LOG_LEVEL",
        "LITELLM_DEFAULT_MODEL",
    ]
    for var in optional_vars:
        assert var in content, f"Optional var {var!r} missing from .env.example"


def test_app_settings_defaults_match_env_example(monkeypatch: pytest.MonkeyPatch) -> None:
    """AppSettings defaults match the documented values in .env.example."""
    # Provide required fields so AppSettings can instantiate
    monkeypatch.setenv("GITHUB_APP_ID", "1")
    monkeypatch.setenv("GITHUB_PRIVATE_KEY", "fake-key")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "fake-secret")
    monkeypatch.setenv("ENCRYPTION_KEY", "fake-encryption-key")
    monkeypatch.setenv("GITHUB_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GITHUB_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-session-secret-key-32-bytes!!")

    from d1ff.config import get_settings

    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.DATABASE_URL == "sqlite+aiosqlite:////data/d1ff.db"
        assert settings.PORT == 8000
    finally:
        get_settings.cache_clear()
