"""Tests for CONTRIBUTING.md completeness (Story 7.3, AC #2, #3)."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]
CONTRIBUTING = PROJECT_ROOT / "CONTRIBUTING.md"


def test_contributing_exists():
    assert CONTRIBUTING.exists(), "CONTRIBUTING.md must exist at project root"


def test_contributing_covers_prompts():
    content = CONTRIBUTING.read_text(encoding="utf-8")
    assert "prompt" in content.lower(), (
        "CONTRIBUTING.md must explain prompt contributions (FR54, DOC7)"
    )


def test_contributing_covers_code_contributions():
    content = CONTRIBUTING.read_text(encoding="utf-8")
    assert (
        "code contribution" in content.lower() or "code contributions" in content.lower()
    ), "CONTRIBUTING.md must cover code contributions"


def test_contributing_covers_uv_sync():
    content = CONTRIBUTING.read_text(encoding="utf-8")
    assert "uv sync" in content, (
        "CONTRIBUTING.md must include 'uv sync' in development setup instructions"
    )


def test_contributing_sufficient_length():
    content = CONTRIBUTING.read_text(encoding="utf-8")
    assert len(content) > 1000, (
        f"CONTRIBUTING.md is too short ({len(content)} chars); expected > 1000"
    )
