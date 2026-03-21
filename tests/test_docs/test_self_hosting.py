"""Tests for docs/self-hosting.md completeness (Story 7.3, AC #1, #4)."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]
SELF_HOSTING = PROJECT_ROOT / "docs" / "self-hosting.md"


def test_self_hosting_exists():
    assert SELF_HOSTING.exists(), "docs/self-hosting.md must exist"


def test_self_hosting_covers_docker():
    content = SELF_HOSTING.read_text(encoding="utf-8")
    assert "docker" in content.lower(), "self-hosting guide must cover Docker deployment"


def test_self_hosting_covers_environment_variables():
    content = SELF_HOSTING.read_text(encoding="utf-8")
    assert (
        "environment variable" in content.lower() or "env var" in content.lower()
    ), "self-hosting guide must cover environment variable configuration"


def test_self_hosting_covers_github_app():
    content = SELF_HOSTING.read_text(encoding="utf-8")
    assert "github app" in content.lower(), "self-hosting guide must cover GitHub App registration"


def test_self_hosting_covers_data_flow():
    content = SELF_HOSTING.read_text(encoding="utf-8")
    assert (
        "persist" in content.lower() or "data flow" in content.lower()
    ), "self-hosting guide must cover data flow and what is persisted (DOC10)"


def test_self_hosting_sufficient_length():
    content = SELF_HOSTING.read_text(encoding="utf-8")
    assert len(content) > 2000, (
        f"self-hosting guide is too short ({len(content)} chars); expected > 2000"
    )
