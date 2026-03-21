"""Pydantic models for the storage layer."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class Installation(BaseModel):
    model_config = ConfigDict(frozen=True)

    installation_id: int
    account_login: str
    account_type: str
    suspended: bool = False
    created_at: datetime
    updated_at: datetime


class APIKeyRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int | None = None
    installation_id: int
    provider: str
    model: str
    encrypted_key: str
    created_at: datetime
    updated_at: datetime


class User(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int | None = None
    github_id: int
    login: str
    email: str | None = None
    avatar_url: str | None = None
    created_at: datetime
    updated_at: datetime


class InstallationConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    installation_id: int
    provider: str  # one of: "openai", "anthropic", "google", "deepseek"
    model: str  # model name, e.g. "gpt-4o", "claude-opus-4-5", "gemini-pro", "deepseek-chat"
    api_key_record_id: int | None = None  # FK reference to api_keys table row
    custom_endpoint: str | None = None  # optional custom LLM endpoint URL (e.g. Azure OpenAI)
