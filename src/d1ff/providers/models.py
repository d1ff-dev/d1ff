"""Pydantic models for the LLM providers module."""

from pydantic import BaseModel, ConfigDict


class ProviderConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    installation_id: int
    provider: str  # e.g. "openai", "anthropic", "google", "deepseek"
    model: str  # e.g. "gpt-4o", "claude-opus-4-5"
    api_key_encrypted: str  # Fernet-encrypted; decrypted at call time
    custom_endpoint: str | None = None  # optional custom LLM endpoint URL (e.g. Azure OpenAI)
