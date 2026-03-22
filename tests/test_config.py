"""Tests for d1ff configuration (AppSettings / get_settings)."""

import pytest
from pydantic import ValidationError

from d1ff.config import AppSettings, get_settings

# Minimal valid env-var set for tests
VALID_ENV = {
    "GITHUB_APP_ID": "123456",
    "GITHUB_PRIVATE_KEY": "-----BEGIN RSA PRIVATE KEY-----\nfake\n-----END RSA PRIVATE KEY-----",
    "GITHUB_WEBHOOK_SECRET": "test-webhook-secret",
    "ENCRYPTION_KEY": "dGVzdC1mZXJuZXQta2V5LTMyLWJ5dGVzLXBhZGRlZA==",
    "GITHUB_CLIENT_ID": "test-client-id",
    "GITHUB_CLIENT_SECRET": "test-client-secret",
    "SESSION_SECRET_KEY": "test-session-secret-key-32-bytes!!",
}


@pytest.fixture(autouse=True)
def clear_settings_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear the lru_cache and ignore .env file to avoid state leakage."""
    get_settings.cache_clear()
    monkeypatch.setattr(AppSettings, "model_config", {**AppSettings.model_config, "env_file": None})
    yield  # type: ignore[misc]
    get_settings.cache_clear()


def test_settings_load_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Valid env vars should produce a fully populated AppSettings instance."""
    for key, value in VALID_ENV.items():
        monkeypatch.setenv(key, value)

    settings = get_settings()

    assert settings.GITHUB_APP_ID == 123456
    assert settings.GITHUB_PRIVATE_KEY.startswith("-----BEGIN RSA PRIVATE KEY-----")
    assert settings.GITHUB_WEBHOOK_SECRET.get_secret_value() == "test-webhook-secret"
    assert settings.ENCRYPTION_KEY.get_secret_value() == VALID_ENV["ENCRYPTION_KEY"]
    # Optional defaults
    assert settings.MAX_CONCURRENT_REVIEWS == 10
    assert settings.PORT == 8000
    assert settings.LOG_LEVEL == "INFO"
    assert settings.LITELLM_DEFAULT_MODEL == "gpt-4o-mini"
    assert settings.LITELLM_FALLBACK_MODEL is None


def test_settings_fail_fast_missing_required(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing a required env var must raise ValidationError immediately."""
    for key, value in VALID_ENV.items():
        monkeypatch.setenv(key, value)
    # Remove one required field
    monkeypatch.delenv("GITHUB_APP_ID")

    with pytest.raises(ValidationError):
        AppSettings()


def test_encryption_key_not_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    """The raw ENCRYPTION_KEY value must not appear in the settings repr."""
    for key, value in VALID_ENV.items():
        monkeypatch.setenv(key, value)

    settings = get_settings()
    raw_value = VALID_ENV["ENCRYPTION_KEY"]

    assert raw_value not in repr(settings)
    assert raw_value not in str(settings)


def test_webhook_secret_not_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    """The raw GITHUB_WEBHOOK_SECRET value must not appear in the settings repr."""
    for key, value in VALID_ENV.items():
        monkeypatch.setenv(key, value)

    settings = get_settings()
    raw_value = VALID_ENV["GITHUB_WEBHOOK_SECRET"]

    assert raw_value not in repr(settings)
    assert raw_value not in str(settings)
