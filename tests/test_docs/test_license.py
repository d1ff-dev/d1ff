"""Tests for LICENSE file completeness (Story 7.2, AC: #4).

Pure filesystem checks using pathlib.Path — no imports from src/d1ff/.
"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]
LICENSE_PATH = PROJECT_ROOT / "LICENSE"


def test_license_exists() -> None:
    assert LICENSE_PATH.exists(), "LICENSE file must exist at the project root"


def test_license_is_mit() -> None:
    content = LICENSE_PATH.read_text(encoding="utf-8")
    assert "MIT License" in content, "LICENSE file must contain 'MIT License'"


def test_license_has_copyright() -> None:
    content = LICENSE_PATH.read_text(encoding="utf-8")
    assert "Copyright" in content, "LICENSE file must contain a Copyright notice"


def test_license_has_d1ff_copyright() -> None:
    content = LICENSE_PATH.read_text(encoding="utf-8")
    assert "d1ff" in content, "LICENSE file must reference 'd1ff' in the copyright notice"


def test_license_has_permission_grant() -> None:
    content = LICENSE_PATH.read_text(encoding="utf-8")
    assert "Permission is hereby granted" in content, (
        "LICENSE file must contain the standard MIT permission grant text"
    )
