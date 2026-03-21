"""Prompt loader — load model-specific prompt templates from the prompts/ directory.

Prompt files are community-contributed templates stored at the project root in prompts/.
"""

from __future__ import annotations

from pathlib import Path

import structlog

from d1ff.prompts.registry import PROMPT_REGISTRY

logger = structlog.get_logger(__name__)

# From src/d1ff/prompts/loader.py, 4 levels up reaches the project root
PROMPTS_DIR = Path(__file__).parent.parent.parent.parent / "prompts"


def load_prompt(provider_family: str, pass_type: str) -> str:
    """Load the prompt template for the given provider family and pass type.

    Falls back to ("openai", pass_type) if provider_family is not in the registry.
    Raises FileNotFoundError if the resolved prompt file does not exist.
    """
    key = (provider_family, pass_type)
    if key not in PROMPT_REGISTRY:
        # Fall back to openai JSON format for unknown providers
        key = ("openai", pass_type)

    subfolder, extension = PROMPT_REGISTRY[key]
    path = PROMPTS_DIR / subfolder / f"{pass_type}.{extension}"

    if not path.exists():
        raise FileNotFoundError(
            f"Prompt file not found: {path}. "
            f"Expected prompt for provider_family={provider_family!r}, pass_type={pass_type!r}."
        )

    content = path.read_text(encoding="utf-8")

    logger.debug(
        "prompt_loaded",
        provider_family=provider_family,
        pass_type=pass_type,
        path=str(path),
    )

    return content
