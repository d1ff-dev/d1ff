from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Required — fail fast if missing
    GITHUB_APP_ID: int
    GITHUB_PRIVATE_KEY: str  # PEM string, newlines as \n
    GITHUB_WEBHOOK_SECRET: SecretStr
    ENCRYPTION_KEY: SecretStr  # Fernet key, base64url-encoded 32 bytes

    # GitHub OAuth App (for web UI login) — required, fail fast if missing (AD-16)
    GITHUB_CLIENT_ID: str
    GITHUB_CLIENT_SECRET: SecretStr
    SESSION_SECRET_KEY: SecretStr

    # Optional with defaults
    BASE_URL: str = "http://localhost:8000"  # Public base URL for OAuth callback
    DATABASE_URL: str = "sqlite+aiosqlite:////data/d1ff.db"
    MAX_CONCURRENT_REVIEWS: int = 10
    # Hosted tier rate limiting (AD-7)
    HOSTED_MODE: bool = False  # When True, enables slowapi per-installation rate limiting
    RATE_LIMIT_PER_MINUTE: int = 10  # Max webhook requests per installation per minute
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    # LLM defaults
    LITELLM_DEFAULT_MODEL: str = "gpt-4o-mini"
    LITELLM_FALLBACK_MODEL: str | None = None


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()
