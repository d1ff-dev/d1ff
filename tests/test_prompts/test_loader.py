"""Tests for prompts/loader.py — load prompt templates by provider family and pass type."""

from pathlib import Path
from unittest.mock import patch

import pytest

from d1ff.prompts.loader import PROMPTS_DIR, load_prompt


def test_prompts_dir_exists() -> None:
    """PROMPTS_DIR resolves to the actual prompts/ directory at project root."""
    assert PROMPTS_DIR.exists(), f"PROMPTS_DIR not found: {PROMPTS_DIR}"
    assert PROMPTS_DIR.is_dir()


def test_load_prompt_claude_summary() -> None:
    """load_prompt('claude', 'summary') returns non-empty string."""
    content = load_prompt("claude", "summary")
    assert isinstance(content, str)
    assert len(content.strip()) > 0


def test_load_prompt_openai_review() -> None:
    """load_prompt('openai', 'review') returns non-empty string."""
    content = load_prompt("openai", "review")
    assert isinstance(content, str)
    assert len(content.strip()) > 0


def test_load_prompt_deepseek_verify() -> None:
    """load_prompt('deepseek', 'verify') returns non-empty string."""
    content = load_prompt("deepseek", "verify")
    assert isinstance(content, str)
    assert len(content.strip()) > 0


def test_load_prompt_google_falls_back_to_openai() -> None:
    """load_prompt('google', 'summary') returns same content as load_prompt('openai', 'summary')."""
    google_content = load_prompt("google", "summary")
    openai_content = load_prompt("openai", "summary")
    assert google_content == openai_content


def test_load_prompt_unknown_falls_back_to_openai() -> None:
    """load_prompt with unknown provider falls back to openai JSON format."""
    unknown_content = load_prompt("unknown_provider", "summary")
    openai_content = load_prompt("openai", "summary")
    assert unknown_content == openai_content


def test_load_prompt_missing_file_raises(tmp_path: Path) -> None:
    """load_prompt raises FileNotFoundError when prompt file does not exist."""
    with patch("d1ff.prompts.loader.PROMPTS_DIR", tmp_path), pytest.raises(
        FileNotFoundError, match="Prompt file not found"
    ):
        load_prompt("openai", "summary")


def test_load_prompt_all_nine_files() -> None:
    """All 9 prompt files can be loaded without error."""
    providers = ["claude", "openai", "deepseek"]
    passes = ["summary", "review", "verify"]
    for provider in providers:
        for pass_type in passes:
            content = load_prompt(provider, pass_type)
            assert len(content.strip()) > 0, f"Empty content for {provider}/{pass_type}"
