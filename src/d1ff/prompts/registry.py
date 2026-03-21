"""Prompt registry — maps (provider_family, pass_type) to (subfolder, file_extension).

Google models use OpenAI JSON format (no google/ subdirectory per architecture spec).
"""

from __future__ import annotations

from typing import Literal

ProviderFamily = Literal["claude", "openai", "deepseek", "google"]
PassType = Literal["summary", "review", "verify"]

# Maps (provider_family, pass_type) → (subfolder, extension)
PROMPT_REGISTRY: dict[tuple[str, str], tuple[str, str]] = {
    ("claude", "summary"): ("claude", "xml"),
    ("claude", "review"): ("claude", "xml"),
    ("claude", "verify"): ("claude", "xml"),
    ("openai", "summary"): ("openai", "json"),
    ("openai", "review"): ("openai", "json"),
    ("openai", "verify"): ("openai", "json"),
    ("deepseek", "summary"): ("deepseek", "txt"),
    ("deepseek", "review"): ("deepseek", "txt"),
    ("deepseek", "verify"): ("deepseek", "txt"),
    ("google", "summary"): ("openai", "json"),  # google uses openai JSON format
    ("google", "review"): ("openai", "json"),
    ("google", "verify"): ("openai", "json"),
}
