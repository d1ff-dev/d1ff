"""Tests for pipeline/models.py — frozen Pydantic contracts."""

import pytest
from pydantic import ValidationError

from d1ff.pipeline import ReviewFinding, ReviewFindings, SummaryResult
from d1ff.providers.cost_tracker import CostRecord

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MOCK_COST = CostRecord(
    prompt_tokens=10,
    completion_tokens=5,
    total_tokens=15,
    estimated_cost_usd=0.001,
    model="gpt-4o",
)


def _make_finding(**kwargs) -> ReviewFinding:
    defaults = dict(
        severity="warning",
        category="bug",
        confidence="high",
        file="src/foo.py",
        line=1,
        message="Test finding",
    )
    defaults.update(kwargs)
    return ReviewFinding.model_validate(defaults)


# ---------------------------------------------------------------------------
# SummaryResult
# ---------------------------------------------------------------------------


def test_summary_result_is_frozen():
    result = SummaryResult(summary="A PR that adds auth.", cost=_MOCK_COST)
    with pytest.raises((ValidationError, TypeError)):
        result.summary = "mutated"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ReviewFinding — severity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("severity", ["critical", "warning", "suggestion", "nitpick"])
def test_review_finding_all_severity_values(severity):
    finding = _make_finding(severity=severity)
    assert finding.severity == severity


# ---------------------------------------------------------------------------
# ReviewFinding — category
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "category",
    ["bug", "security", "style", "performance", "logic", "maintainability"],
)
def test_review_finding_all_category_values(category):
    finding = _make_finding(category=category)
    assert finding.category == category


# ---------------------------------------------------------------------------
# ReviewFinding — suggestion optional
# ---------------------------------------------------------------------------


def test_review_finding_suggestion_optional():
    finding = _make_finding()
    assert finding.suggestion is None


def test_review_finding_suggestion_provided():
    finding = _make_finding(suggestion="Use a null check.")
    assert finding.suggestion == "Use a null check."


# ---------------------------------------------------------------------------
# ReviewFindings
# ---------------------------------------------------------------------------


def test_review_findings_is_frozen():
    findings = ReviewFindings(findings=[], cost=_MOCK_COST)
    with pytest.raises((ValidationError, TypeError)):
        findings.findings = []  # type: ignore[misc]


def test_review_findings_contains_findings():
    f = _make_finding()
    result = ReviewFindings(findings=[f], cost=_MOCK_COST)
    assert len(result.findings) == 1
    assert result.findings[0] is f
