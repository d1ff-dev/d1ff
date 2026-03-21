"""Tests for pipeline/verification_pass.py — Pass 3 noise filtering (AC: 1, 2, 3, 4)."""

import json
from unittest.mock import AsyncMock, patch

import structlog.testing

from d1ff.context.models import FileContext, PRMetadata, ReviewContext
from d1ff.pipeline.models import ReviewFinding, ReviewFindings, VerifiedFindings
from d1ff.pipeline.verification_pass import run_verification_pass
from d1ff.providers.cost_tracker import CostRecord
from d1ff.providers.models import ProviderConfig

# ---------------------------------------------------------------------------
# Fixtures / constants
# ---------------------------------------------------------------------------

_MOCK_COST = CostRecord(
    prompt_tokens=10,
    completion_tokens=5,
    total_tokens=15,
    estimated_cost_usd=0.001,
    model="gpt-4o",
)

_MOCK_CONFIG = ProviderConfig(
    installation_id=42,
    provider="openai",
    model="gpt-4o",
    api_key_encrypted="enc-key",
)

_MOCK_CONTEXT = ReviewContext(
    installation_id=42,
    pr_metadata=PRMetadata(
        number=7,
        title="Add auth module",
        author="alice",
        base_branch="main",
        head_branch="feat/auth",
        html_url="https://github.com/org/repo/pull/7",
        draft=False,
    ),
    diff="+ def login(): pass",
    changed_files=[
        FileContext(path="src/auth.py", content="def login(): pass"),
    ],
)

_FINDING_1 = ReviewFinding(
    severity="warning",
    category="bug",
    confidence="high",
    file="src/auth.py",
    line=1,
    message="Missing input validation.",
    suggestion="Validate inputs before use.",
)

_FINDING_2 = ReviewFinding(
    severity="nitpick",
    category="style",
    confidence="low",
    file="src/auth.py",
    line=2,
    message="Variable name is too short.",
    suggestion=None,
)

_FINDING_3 = ReviewFinding(
    severity="suggestion",
    category="maintainability",
    confidence="medium",
    file="src/auth.py",
    line=3,
    message="Consider extracting method.",
    suggestion=None,
)


def _mock_findings(*items: ReviewFinding) -> ReviewFindings:
    return ReviewFindings(findings=list(items), cost=_MOCK_COST)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_run_verification_pass_returns_verified_findings():
    """Mock LLM returns valid JSON list of findings → VerifiedFindings with was_degraded=False."""
    input_findings = _mock_findings(_FINDING_1, _FINDING_2)
    llm_response = json.dumps([_FINDING_1.model_dump()])

    with patch(
        "d1ff.pipeline.verification_pass.call_llm_with_retry", new_callable=AsyncMock
    ) as mock_llm, patch("d1ff.pipeline.verification_pass.load_prompt", return_value="prompt"):
        mock_llm.return_value = (llm_response, _MOCK_COST)
        result = await run_verification_pass(input_findings, _MOCK_CONTEXT, _MOCK_CONFIG)

    assert isinstance(result, VerifiedFindings)
    assert len(result.findings) == 1
    assert result.was_degraded is False
    assert result.findings[0] == _FINDING_1


async def test_run_verification_pass_filters_low_quality_findings():
    """LLM returns fewer findings than input — output has fewer items."""
    input_findings = _mock_findings(_FINDING_1, _FINDING_2)
    # LLM filters out _FINDING_2 (low confidence / nitpick)
    llm_response = json.dumps([_FINDING_1.model_dump()])

    with patch(
        "d1ff.pipeline.verification_pass.call_llm_with_retry", new_callable=AsyncMock
    ) as mock_llm, patch("d1ff.pipeline.verification_pass.load_prompt", return_value="prompt"):
        mock_llm.return_value = (llm_response, _MOCK_COST)
        result = await run_verification_pass(input_findings, _MOCK_CONTEXT, _MOCK_CONFIG)

    assert len(result.findings) < len(input_findings.findings)
    assert result.findings[0] == _FINDING_1


async def test_run_verification_pass_handles_json_parse_failure_gracefully():
    """LLM returns non-JSON → VerifiedFindings with input findings and was_degraded=True."""
    input_findings = _mock_findings(_FINDING_1, _FINDING_2)

    with patch(
        "d1ff.pipeline.verification_pass.call_llm_with_retry", new_callable=AsyncMock
    ) as mock_llm, patch("d1ff.pipeline.verification_pass.load_prompt", return_value="prompt"):
        mock_llm.return_value = ("not json", _MOCK_COST)
        result = await run_verification_pass(input_findings, _MOCK_CONTEXT, _MOCK_CONFIG)

    assert result.was_degraded is True
    assert result.findings == input_findings.findings


async def test_run_verification_pass_strips_markdown_code_fences():
    """LLM returns JSON wrapped in markdown fences → parses successfully."""
    input_findings = _mock_findings(_FINDING_1)
    fenced_response = f"```json\n{json.dumps([_FINDING_1.model_dump()])}\n```"

    with patch(
        "d1ff.pipeline.verification_pass.call_llm_with_retry", new_callable=AsyncMock
    ) as mock_llm, patch("d1ff.pipeline.verification_pass.load_prompt", return_value="prompt"):
        mock_llm.return_value = (fenced_response, _MOCK_COST)
        result = await run_verification_pass(input_findings, _MOCK_CONTEXT, _MOCK_CONFIG)

    assert result.was_degraded is False
    assert len(result.findings) == 1


async def test_run_verification_pass_skips_empty_findings():
    """Empty ReviewFindings → returns immediately without calling the LLM."""
    empty_findings = ReviewFindings(findings=[], cost=_MOCK_COST)

    with patch(
        "d1ff.pipeline.verification_pass.call_llm_with_retry", new_callable=AsyncMock
    ) as mock_llm:
        result = await run_verification_pass(empty_findings, _MOCK_CONTEXT, _MOCK_CONFIG)

    mock_llm.assert_not_called()
    assert isinstance(result, VerifiedFindings)
    assert result.findings == []
    assert result.was_degraded is False


async def test_run_verification_pass_uses_correct_pass_type():
    """load_prompt is called with pass_type='verify'."""
    input_findings = _mock_findings(_FINDING_1)

    with patch(
        "d1ff.pipeline.verification_pass.call_llm_with_retry", new_callable=AsyncMock
    ) as mock_llm, patch(
        "d1ff.pipeline.verification_pass.load_prompt", return_value="prompt"
    ) as mock_load_prompt:
        mock_llm.return_value = (json.dumps([_FINDING_1.model_dump()]), _MOCK_COST)
        await run_verification_pass(input_findings, _MOCK_CONTEXT, _MOCK_CONFIG)

    # Confirm pass_type="verify" was passed
    call_args = mock_load_prompt.call_args
    assert call_args[0][1] == "verify" or call_args.args[1] == "verify"


async def test_run_verification_pass_skips_invalid_findings_on_validation_error():
    """LLM returns one valid and one invalid finding → only valid one in result."""
    input_findings = _mock_findings(_FINDING_1, _FINDING_2)
    # Invalid finding: severity is not a valid Literal value
    invalid_finding = dict(_FINDING_1.model_dump())
    invalid_finding["severity"] = "invalid_severity"
    llm_response = json.dumps([_FINDING_1.model_dump(), invalid_finding])

    with patch(
        "d1ff.pipeline.verification_pass.call_llm_with_retry", new_callable=AsyncMock
    ) as mock_llm, patch("d1ff.pipeline.verification_pass.load_prompt", return_value="prompt"):
        mock_llm.return_value = (llm_response, _MOCK_COST)
        result = await run_verification_pass(input_findings, _MOCK_CONTEXT, _MOCK_CONFIG)

    # Only the valid finding should be in the result; invalid one is skipped
    assert len(result.findings) == 1
    assert result.findings[0] == _FINDING_1
    assert result.was_degraded is False


# ---------------------------------------------------------------------------
# Story 5.3: Tests for enhanced verification_pass_complete log fields (AC: 1, 2)
# ---------------------------------------------------------------------------


async def test_verification_pass_complete_logs_filtered_count():
    """3 findings in, 2 findings out → filtered_count=1 in verification_pass_complete event."""
    input_findings = _mock_findings(_FINDING_1, _FINDING_2, _FINDING_3)
    # LLM returns only FINDING_1 and FINDING_2 (FINDING_3 filtered)
    llm_response = json.dumps([_FINDING_1.model_dump(), _FINDING_2.model_dump()])

    with structlog.testing.capture_logs() as cap_logs, patch(
        "d1ff.pipeline.verification_pass.call_llm_with_retry",
        new_callable=AsyncMock,
        return_value=(llm_response, _MOCK_COST),
    ), patch("d1ff.pipeline.verification_pass.load_prompt", return_value="prompt"):
        await run_verification_pass(input_findings, _MOCK_CONTEXT, _MOCK_CONFIG)

    complete_event = next(e for e in cap_logs if e["event"] == "verification_pass_complete")
    assert complete_event["filtered_count"] == 1


async def test_verification_pass_complete_logs_filtered_categories():
    """1 filtered finding with category='style' → filtered_categories==['style']."""
    input_findings = _mock_findings(_FINDING_1, _FINDING_2)
    # LLM retains only FINDING_1 (bug); FINDING_2 (style) is filtered
    llm_response = json.dumps([_FINDING_1.model_dump()])

    with structlog.testing.capture_logs() as cap_logs, patch(
        "d1ff.pipeline.verification_pass.call_llm_with_retry",
        new_callable=AsyncMock,
        return_value=(llm_response, _MOCK_COST),
    ), patch("d1ff.pipeline.verification_pass.load_prompt", return_value="prompt"):
        await run_verification_pass(input_findings, _MOCK_CONTEXT, _MOCK_CONFIG)

    complete_event = next(e for e in cap_logs if e["event"] == "verification_pass_complete")
    assert complete_event["filtered_categories"] == ["style"]


async def test_verification_pass_complete_logs_multiple_filtered_categories_sorted():
    """2 filtered findings with categories 'maintainability' and 'bug' → sorted list."""
    input_findings = _mock_findings(_FINDING_1, _FINDING_2, _FINDING_3)
    # LLM retains only FINDING_2 (style); FINDING_1 (bug) and FINDING_3 (maintainability) filtered
    llm_response = json.dumps([_FINDING_2.model_dump()])

    with structlog.testing.capture_logs() as cap_logs, patch(
        "d1ff.pipeline.verification_pass.call_llm_with_retry",
        new_callable=AsyncMock,
        return_value=(llm_response, _MOCK_COST),
    ), patch("d1ff.pipeline.verification_pass.load_prompt", return_value="prompt"):
        await run_verification_pass(input_findings, _MOCK_CONTEXT, _MOCK_CONFIG)

    complete_event = next(e for e in cap_logs if e["event"] == "verification_pass_complete")
    assert complete_event["filtered_categories"] == ["bug", "maintainability"]


async def test_verification_pass_complete_logs_empty_filtered_when_none_removed():
    """All input findings retained → filtered_count=0 and filtered_categories==[]."""
    input_findings = _mock_findings(_FINDING_1, _FINDING_2)
    # LLM returns all findings unchanged
    llm_response = json.dumps([_FINDING_1.model_dump(), _FINDING_2.model_dump()])

    with structlog.testing.capture_logs() as cap_logs, patch(
        "d1ff.pipeline.verification_pass.call_llm_with_retry",
        new_callable=AsyncMock,
        return_value=(llm_response, _MOCK_COST),
    ), patch("d1ff.pipeline.verification_pass.load_prompt", return_value="prompt"):
        await run_verification_pass(input_findings, _MOCK_CONTEXT, _MOCK_CONFIG)

    complete_event = next(e for e in cap_logs if e["event"] == "verification_pass_complete")
    assert complete_event["filtered_count"] == 0
    assert complete_event["filtered_categories"] == []


async def test_verification_pass_complete_logs_all_filtered():
    """All 2 findings removed by verification → filtered_count=2."""
    input_findings = _mock_findings(_FINDING_1, _FINDING_2)
    # LLM returns empty list (all findings filtered)
    llm_response = json.dumps([])

    with structlog.testing.capture_logs() as cap_logs, patch(
        "d1ff.pipeline.verification_pass.call_llm_with_retry",
        new_callable=AsyncMock,
        return_value=(llm_response, _MOCK_COST),
    ), patch("d1ff.pipeline.verification_pass.load_prompt", return_value="prompt"):
        await run_verification_pass(input_findings, _MOCK_CONTEXT, _MOCK_CONFIG)

    complete_event = next(e for e in cap_logs if e["event"] == "verification_pass_complete")
    assert complete_event["filtered_count"] == 2
