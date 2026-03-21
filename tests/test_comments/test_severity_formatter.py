"""Tests for severity_formatter.py — comment formatting and severity classification.

All functions under test are pure sync — no mocking needed, no asyncio markers.
FR24, FR25, FR26, FR27, FR28, NFR21.
"""

from __future__ import annotations

import pytest

from d1ff.comments import FormattedReview, InlineComment, ReviewSummary, format_review
from d1ff.pipeline import ReviewFinding, SummaryResult, VerifiedFindings
from d1ff.providers.cost_tracker import CostRecord

# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def make_cost() -> CostRecord:
    return CostRecord(
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        estimated_cost_usd=0.001,
        model="gpt-4o",
    )


def make_finding(
    severity: str = "critical",
    category: str = "bug",
    confidence: str = "high",
    file: str = "main.py",
    line: int = 10,
    message: str = "Test issue",
    suggestion: str | None = None,
) -> ReviewFinding:
    return ReviewFinding(
        severity=severity,  # type: ignore[arg-type]
        category=category,  # type: ignore[arg-type]
        confidence=confidence,  # type: ignore[arg-type]
        file=file,
        line=line,
        message=message,
        suggestion=suggestion,
    )


def make_verified(
    findings: list[ReviewFinding] | None = None,
    was_degraded: bool = False,
) -> VerifiedFindings:
    return VerifiedFindings(
        findings=findings or [],
        cost=make_cost(),
        was_degraded=was_degraded,
    )


INSTALLATION_ID = "test-installation-123"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_critical_finding_becomes_inline_comment() -> None:
    finding = make_finding(severity="critical")
    verified = make_verified([finding])

    result = format_review(verified, None, INSTALLATION_ID)

    assert len(result.inline_comments) == 1
    assert "🔴 Critical" in result.inline_comments[0].body


def test_warning_finding_becomes_inline_comment() -> None:
    finding = make_finding(severity="warning")
    verified = make_verified([finding])

    result = format_review(verified, None, INSTALLATION_ID)

    assert len(result.inline_comments) == 1
    assert "🟡 Warning" in result.inline_comments[0].body


def test_suggestion_finding_goes_to_summary_only() -> None:
    finding = make_finding(severity="suggestion", message="Consider renaming this variable")
    verified = make_verified([finding])

    result = format_review(verified, None, INSTALLATION_ID)

    assert result.inline_comments == []
    assert "Consider renaming this variable" in result.summary.body


def test_nitpick_finding_goes_to_summary_only() -> None:
    finding = make_finding(severity="nitpick")
    verified = make_verified([finding])

    result = format_review(verified, None, INSTALLATION_ID)

    assert result.inline_comments == []


def test_severity_breakdown_counts_all_severities() -> None:
    findings = [
        make_finding(severity="critical"),
        make_finding(severity="warning"),
        make_finding(severity="warning"),
        make_finding(severity="suggestion"),
        make_finding(severity="suggestion"),
        make_finding(severity="suggestion"),
        make_finding(severity="nitpick"),
    ]
    verified = make_verified(findings)

    result = format_review(verified, None, INSTALLATION_ID)

    assert "🔴 Critical: 1" in result.summary.body
    assert "🟡 Warning: 2" in result.summary.body
    assert "💡 Suggestions: 3" in result.summary.body
    assert "🔵 Nitpicks: 1" in result.summary.body


def test_suggestion_block_included_when_suggestion_present() -> None:
    finding = make_finding(severity="critical", suggestion="return x + 1")
    verified = make_verified([finding])

    result = format_review(verified, None, INSTALLATION_ID)

    assert len(result.inline_comments) == 1
    body = result.inline_comments[0].body
    assert "```suggestion" in body
    assert "return x + 1" in body


def test_suggestion_block_omitted_when_suggestion_none() -> None:
    finding = make_finding(severity="critical", suggestion=None)
    verified = make_verified([finding])

    result = format_review(verified, None, INSTALLATION_ID)

    assert len(result.inline_comments) == 1
    body = result.inline_comments[0].body
    assert "```suggestion" not in body


def test_pr_summary_included_when_summary_result_provided() -> None:
    summary_result = SummaryResult(summary="This PR adds feature X", cost=make_cost())
    verified = make_verified()

    result = format_review(verified, summary_result, INSTALLATION_ID)

    assert result.summary.body.startswith("## PR Summary")
    assert "This PR adds feature X" in result.summary.body


def test_pr_summary_omitted_when_none() -> None:
    verified = make_verified()

    result = format_review(verified, None, INSTALLATION_ID)

    assert "## PR Summary" not in result.summary.body


def test_degraded_disclaimer_added_when_was_degraded_true() -> None:
    verified = make_verified(was_degraded=True)

    result = format_review(verified, None, INSTALLATION_ID)

    assert "⚠️ Verification pass was skipped or failed" in result.summary.body


def test_no_disclaimer_when_not_degraded() -> None:
    verified = make_verified(was_degraded=False)

    result = format_review(verified, None, INSTALLATION_ID)

    assert "⚠️ Verification pass was skipped or failed" not in result.summary.body


def test_empty_findings_produces_valid_formatted_review() -> None:
    verified = make_verified(findings=[])

    result = format_review(verified, None, INSTALLATION_ID)

    assert isinstance(result, FormattedReview)
    assert result.inline_comments == []
    assert "🔴 Critical: 0" in result.summary.body
    assert "🟡 Warning: 0" in result.summary.body
    assert "💡 Suggestions: 0" in result.summary.body
    assert "🔵 Nitpicks: 0" in result.summary.body


def test_formatted_review_models_are_frozen() -> None:
    from pydantic import ValidationError

    inline = InlineComment(file="foo.py", line=1, body="body text")
    with pytest.raises(ValidationError):
        inline.file = "other.py"  # type: ignore[misc]

    summary = ReviewSummary(body="summary text")
    with pytest.raises(ValidationError):
        summary.body = "changed"  # type: ignore[misc]

    review = FormattedReview(
        inline_comments=[],
        summary=ReviewSummary(body="x"),
        was_degraded=False,
    )
    with pytest.raises(ValidationError):
        review.was_degraded = True  # type: ignore[misc]
