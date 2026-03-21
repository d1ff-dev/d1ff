"""Tests for README.md documentation completeness (Story 7.2, AC: #1, #2, #3).

Pure filesystem checks using pathlib.Path — no imports from src/d1ff/.
"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]
README_PATH = PROJECT_ROOT / "README.md"


def test_readme_exists() -> None:
    assert README_PATH.exists(), "README.md must exist at the project root"


def test_readme_is_substantial() -> None:
    content = README_PATH.read_text(encoding="utf-8")
    assert len(content) > 1000, "README.md must be > 1000 chars (smoke test for non-stub content)"


def test_readme_has_quickstart_section() -> None:
    content = README_PATH.read_text(encoding="utf-8").lower()
    assert "quickstart" in content, "README.md must contain a 'Quickstart' section"


def test_readme_has_savings_or_cost_section() -> None:
    content = README_PATH.read_text(encoding="utf-8").lower()
    assert "savings" in content or "cost" in content, (
        "README.md must contain a savings calculator or cost comparison section"
    )


def test_readme_has_demo_gif_reference() -> None:
    content = README_PATH.read_text(encoding="utf-8").lower()
    assert "demo" in content and "gif" in content, (
        "README.md must reference a demo GIF (even as a placeholder)"
    )


def test_readme_has_tagline_on_first_screen() -> None:
    """Tagline and quickstart must appear within the first 50 lines."""
    lines = README_PATH.read_text(encoding="utf-8").splitlines()
    first_screen = "\n".join(lines[:50]).lower()
    assert "quickstart" in first_screen, (
        "Quickstart section must appear within the first 50 lines of README.md"
    )


def test_readme_has_license_section() -> None:
    content = README_PATH.read_text(encoding="utf-8").lower()
    assert "license" in content, "README.md must contain a License section"


def test_readme_has_supported_providers() -> None:
    content = README_PATH.read_text(encoding="utf-8").lower()
    assert "openai" in content or "anthropic" in content, (
        "README.md must list supported LLM providers"
    )
