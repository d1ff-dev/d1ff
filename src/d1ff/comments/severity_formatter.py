"""Core comment formatting logic: VerifiedFindings → FormattedReview (AD-9).

This module is a pure sync data transformation — no I/O, no async, no LLM calls.
FR24: severity labels, FR25: category labels, FR26: confidence labels,
FR27: severity breakdown summary, FR28: inline vs grouped split rule.
"""

from __future__ import annotations

import structlog

from d1ff.comments.models import FormattedReview, InlineComment, ReviewSummary
from d1ff.pipeline import ReviewFinding, SummaryResult, VerifiedFindings

logger = structlog.get_logger(__name__)

_INLINE_SEVERITIES = frozenset({"critical", "warning"})
_GROUPED_SEVERITIES = frozenset({"suggestion", "nitpick"})

_SEVERITY_LABEL: dict[str, str] = {
    "critical": "🔴 Critical",
    "warning": "🟡 Warning",
    "suggestion": "💡 Suggestion",
    "nitpick": "🔵 Nitpick",
}


def _build_inline_body(finding: ReviewFinding) -> str:
    """Build the markdown body for an inline comment (FR24, FR25, FR26)."""
    severity_label = _SEVERITY_LABEL[finding.severity]
    header = (
        f"**{severity_label} [{finding.category}]**"
        f" (confidence: {finding.confidence})"
    )
    parts = [header, "", finding.message]
    if finding.suggestion is not None:
        parts.append("")
        parts.append("```suggestion")
        parts.append(finding.suggestion)
        parts.append("```")
    return "\n".join(parts)


def _build_summary_body(
    findings: VerifiedFindings,
    summary_result: SummaryResult | None,
    grouped_findings: list[ReviewFinding],
) -> str:
    """Build the full markdown summary comment body (FR27, FR28, NFR21)."""
    sections: list[str] = []

    # PR description section (if provided)
    if summary_result is not None:
        sections.append(f"## PR Summary\n\n{summary_result.summary}")

    # Severity breakdown (FR27) — always present, even when all counts are zero
    all_findings = findings.findings
    critical_count = sum(1 for f in all_findings if f.severity == "critical")
    warning_count = sum(1 for f in all_findings if f.severity == "warning")
    suggestion_count = sum(1 for f in all_findings if f.severity == "suggestion")
    nitpick_count = sum(1 for f in all_findings if f.severity == "nitpick")

    breakdown_line = (
        f"🔴 Critical: {critical_count}"
        f"  🟡 Warning: {warning_count}"
        f"  💡 Suggestions: {suggestion_count}"
        f"  🔵 Nitpicks: {nitpick_count}"
    )
    sections.append(f"## Review Summary\n\n{breakdown_line}")

    # Grouped suggestions & nitpicks section (FR28)
    if grouped_findings:
        lines = ["## Suggestions & Nitpicks", ""]
        for f in grouped_findings:
            severity_label = _SEVERITY_LABEL[f.severity]
            entry = (
                f"- **[{severity_label}] [{f.category}]**"
                f" `{f.file}:{f.line}` — {f.message}"
            )
            lines.append(entry)
        sections.append("\n".join(lines))

    # Degradation disclaimer (NFR21) — ONLY when was_degraded is True
    if findings.was_degraded:
        sections.append(
            "---\n> ⚠️ Verification pass was skipped or failed."
            " These findings have not been noise-filtered."
        )

    return "\n\n".join(sections)


def format_review(
    findings: VerifiedFindings,
    summary_result: SummaryResult | None,
    installation_id: str,
) -> FormattedReview:
    """Transform VerifiedFindings into a FormattedReview ready for posting.

    Pure sync function — no I/O, no async, no LLM calls (AD-9).

    Args:
        findings: The verified findings from the pipeline (Pass 3 output).
        summary_result: Optional PR summary from Pass 1. None if Pass 1 was skipped.
        installation_id: GitHub App installation ID, for structured logging (AD-11).

    Returns:
        FormattedReview with inline_comments and summary ready for review_poster.py.
    """
    inline_findings = [f for f in findings.findings if f.severity in _INLINE_SEVERITIES]
    grouped_findings = [f for f in findings.findings if f.severity in _GROUPED_SEVERITIES]

    inline_comments = [
        InlineComment(
            file=f.file,
            line=f.line,
            body=_build_inline_body(f),
        )
        for f in inline_findings
    ]

    summary_body = _build_summary_body(findings, summary_result, grouped_findings)
    summary = ReviewSummary(body=summary_body)

    logger.info(
        "comment_formatting_complete",
        installation_id=installation_id,
        stage="comment_formatting",
        inline_count=len(inline_comments),
        grouped_count=len(grouped_findings),
        was_degraded=findings.was_degraded,
    )

    return FormattedReview(
        inline_comments=inline_comments,
        summary=summary,
        was_degraded=findings.was_degraded,
    )
