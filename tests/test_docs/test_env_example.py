"""Tests for .env.example documentation completeness (Story 7.2, AC: #2).

Pure filesystem checks using pathlib.Path — no imports from src/d1ff/.
"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]
ENV_EXAMPLE_PATH = PROJECT_ROOT / ".env.example"

REQUIRED_VARS = [
    "GITHUB_APP_ID",
    "GITHUB_PRIVATE_KEY",
    "GITHUB_WEBHOOK_SECRET",
    "ENCRYPTION_KEY",
    "GITHUB_CLIENT_ID",
    "GITHUB_CLIENT_SECRET",
    "SESSION_SECRET",
]

OPTIONAL_VARS = [
    "LLM_API_KEY",
    "LLM_PROVIDER",
    "LLM_MODEL",
    "LLM_API_BASE",
    "MAX_CONCURRENT_REVIEWS",
    "RATE_LIMIT_RPM",
    "DATABASE_URL",
    "LOG_LEVEL",
    "HOST",
    "PORT",
]


def test_env_example_exists() -> None:
    assert ENV_EXAMPLE_PATH.exists(), ".env.example must exist at the project root"


def test_env_example_not_in_gitignore() -> None:
    gitignore_path = PROJECT_ROOT / ".gitignore"
    if gitignore_path.exists():
        gitignore_content = gitignore_path.read_text(encoding="utf-8")
        # .env.example must NOT be gitignored (must be committed)
        assert ".env.example" not in gitignore_content, (
            ".env.example must NOT be listed in .gitignore — it should be committed"
        )


def test_env_example_gitignores_env() -> None:
    gitignore_path = PROJECT_ROOT / ".gitignore"
    if gitignore_path.exists():
        gitignore_content = gitignore_path.read_text(encoding="utf-8")
        assert ".env" in gitignore_content, ".env must be in .gitignore to prevent secret leaks"


def test_env_example_contains_required_vars() -> None:
    content = ENV_EXAMPLE_PATH.read_text(encoding="utf-8")
    for var in REQUIRED_VARS:
        assert var in content, f".env.example must document required variable: {var}"


def test_env_example_contains_optional_vars() -> None:
    content = ENV_EXAMPLE_PATH.read_text(encoding="utf-8")
    for var in OPTIONAL_VARS:
        assert var in content, f".env.example must document optional variable: {var}"


def test_env_example_has_comments() -> None:
    content = ENV_EXAMPLE_PATH.read_text(encoding="utf-8")
    comment_lines = [line for line in content.splitlines() if line.startswith("#")]
    assert len(comment_lines) >= 5, (
        ".env.example must have at least 5 comment lines explaining variables"
    )
