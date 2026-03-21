"""Tests for pipeline/orchestrator.py — parallel execution and semaphore (AC: 1, 4)."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
import structlog.testing

from d1ff.comments.models import CostBadge
from d1ff.context.models import FileContext, PRMetadata, ReviewContext
from d1ff.pipeline import ReviewFindings, SummaryResult, VerifiedFindings
from d1ff.pipeline.models import ReviewFinding
from d1ff.pipeline.orchestrator import run_pipeline
from d1ff.providers.cost_tracker import CostRecord
from d1ff.providers.models import ProviderConfig

# ---------------------------------------------------------------------------
# Fixtures
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

_MOCK_SUMMARY = SummaryResult(summary="This PR adds auth.", cost=_MOCK_COST)
_MOCK_FINDINGS = ReviewFindings(findings=[], cost=_MOCK_COST)
_MOCK_VERIFIED = VerifiedFindings(findings=[], cost=_MOCK_COST, was_degraded=False)


def _reset_semaphore():
    """Reset the module-level semaphore between tests."""
    import d1ff.pipeline.orchestrator as orch
    orch._review_semaphore = None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_run_pipeline_runs_passes_in_parallel():
    """Both run_summary_pass and run_review_pass are called by run_pipeline."""
    _reset_semaphore()
    with (
        patch(
            "d1ff.pipeline.orchestrator.run_summary_pass",
            new_callable=AsyncMock,
            return_value=_MOCK_SUMMARY,
        ) as mock_summary,
        patch(
            "d1ff.pipeline.orchestrator.run_review_pass",
            new_callable=AsyncMock,
            return_value=_MOCK_FINDINGS,
        ) as mock_review,
        patch(
            "d1ff.pipeline.orchestrator.run_verification_pass",
            new_callable=AsyncMock,
            return_value=_MOCK_VERIFIED,
        ),
        patch(
            "d1ff.pipeline.orchestrator.get_settings",
            return_value=type("S", (), {"MAX_CONCURRENT_REVIEWS": 5})(),
        ),
        patch(
            "d1ff.pipeline.orchestrator.aggregate_costs",
        ) as mock_agg,
    ):
        mock_agg.return_value = type(
            "RC",
            (),
            {
                "total_tokens": 30,
                "total_prompt_tokens": 20,
                "total_completion_tokens": 10,
                "estimated_cost_usd": 0.001,
                "model": "openai/gpt-4o",
            },
        )()
        summary, verified, cost_badge = await run_pipeline(_MOCK_CONTEXT, _MOCK_CONFIG)

    mock_summary.assert_called_once_with(_MOCK_CONTEXT, _MOCK_CONFIG)
    mock_review.assert_called_once_with(_MOCK_CONTEXT, _MOCK_CONFIG)
    assert summary is _MOCK_SUMMARY
    assert verified is _MOCK_VERIFIED


async def test_run_pipeline_summary_failure_returns_none_summary():
    """If Pass 1 raises, returns (None, verified_findings) — no exception propagated."""
    _reset_semaphore()
    with (
        patch(
            "d1ff.pipeline.orchestrator.run_summary_pass",
            new_callable=AsyncMock,
            side_effect=RuntimeError("summary failed"),
        ),
        patch(
            "d1ff.pipeline.orchestrator.run_review_pass",
            new_callable=AsyncMock,
            return_value=_MOCK_FINDINGS,
        ),
        patch(
            "d1ff.pipeline.orchestrator.run_verification_pass",
            new_callable=AsyncMock,
            return_value=_MOCK_VERIFIED,
        ),
        patch(
            "d1ff.pipeline.orchestrator.get_settings",
            return_value=type("S", (), {"MAX_CONCURRENT_REVIEWS": 5})(),
        ),
        patch(
            "d1ff.pipeline.orchestrator.aggregate_costs",
        ) as mock_agg,
    ):
        mock_agg.return_value = type(
            "RC",
            (),
            {
                "total_tokens": 15,
                "total_prompt_tokens": 10,
                "total_completion_tokens": 5,
                "estimated_cost_usd": 0.0,
                "model": "openai/gpt-4o",
            },
        )()
        summary, verified, cost_badge = await run_pipeline(_MOCK_CONTEXT, _MOCK_CONFIG)

    assert summary is None
    assert verified is _MOCK_VERIFIED


async def test_run_pipeline_review_failure_raises():
    """If Pass 2 raises, run_pipeline re-raises the exception."""
    _reset_semaphore()
    with (
        patch(
            "d1ff.pipeline.orchestrator.run_summary_pass",
            new_callable=AsyncMock,
            return_value=_MOCK_SUMMARY,
        ),
        patch(
            "d1ff.pipeline.orchestrator.run_review_pass",
            new_callable=AsyncMock,
            side_effect=RuntimeError("review failed"),
        ),
        patch(
            "d1ff.pipeline.orchestrator.get_settings",
            return_value=type("S", (), {"MAX_CONCURRENT_REVIEWS": 5})(),
        ),
        pytest.raises(RuntimeError, match="review failed"),
    ):
        await run_pipeline(_MOCK_CONTEXT, _MOCK_CONFIG)


async def test_run_pipeline_semaphore_bounds_concurrency():
    """With MAX_CONCURRENT_REVIEWS=1, the semaphore enforces one-at-a-time execution."""
    _reset_semaphore()

    # Track how many pipelines are executing concurrently inside the semaphore
    active_count = 0
    max_observed_active = 0
    async def counting_summary(ctx, cfg):
        nonlocal active_count, max_observed_active
        active_count += 1
        max_observed_active = max(max_observed_active, active_count)
        # Yield control so the second coroutine can attempt to enter if semaphore is wrong
        await asyncio.sleep(0)
        active_count -= 1
        return _MOCK_SUMMARY

    with (
        patch(
            "d1ff.pipeline.orchestrator.get_settings",
            return_value=type("S", (), {"MAX_CONCURRENT_REVIEWS": 1})(),
        ),
        patch(
            "d1ff.pipeline.orchestrator.run_summary_pass",
            side_effect=counting_summary,
        ),
        patch(
            "d1ff.pipeline.orchestrator.run_review_pass",
            new_callable=AsyncMock,
            return_value=_MOCK_FINDINGS,
        ),
        patch(
            "d1ff.pipeline.orchestrator.run_verification_pass",
            new_callable=AsyncMock,
            return_value=_MOCK_VERIFIED,
        ),
        patch(
            "d1ff.pipeline.orchestrator.aggregate_costs",
        ) as mock_agg,
    ):
        mock_agg.return_value = type(
            "RC",
            (),
            {
                "total_tokens": 30,
                "total_prompt_tokens": 20,
                "total_completion_tokens": 10,
                "estimated_cost_usd": 0.001,
                "model": "openai/gpt-4o",
            },
        )()
        # Reset after patching get_settings so semaphore uses MAX_CONCURRENT_REVIEWS=1
        _reset_semaphore()

        task1 = asyncio.create_task(run_pipeline(_MOCK_CONTEXT, _MOCK_CONFIG))
        task2 = asyncio.create_task(run_pipeline(_MOCK_CONTEXT, _MOCK_CONFIG))
        await asyncio.gather(task1, task2)

    # With semaphore=1, at most 1 pipeline should be active at once
    assert max_observed_active <= 1


async def test_run_pipeline_returns_verified_findings():
    """All three passes succeed → returns (SummaryResult, VerifiedFindings, CostBadge)."""
    _reset_semaphore()
    with (
        patch(
            "d1ff.pipeline.orchestrator.run_summary_pass",
            new_callable=AsyncMock,
            return_value=_MOCK_SUMMARY,
        ),
        patch(
            "d1ff.pipeline.orchestrator.run_review_pass",
            new_callable=AsyncMock,
            return_value=_MOCK_FINDINGS,
        ),
        patch(
            "d1ff.pipeline.orchestrator.run_verification_pass",
            new_callable=AsyncMock,
            return_value=_MOCK_VERIFIED,
        ),
        patch(
            "d1ff.pipeline.orchestrator.get_settings",
            return_value=type("S", (), {"MAX_CONCURRENT_REVIEWS": 5})(),
        ),
        patch(
            "d1ff.pipeline.orchestrator.aggregate_costs",
        ) as mock_agg,
    ):
        mock_agg.return_value = type(
            "RC",
            (),
            {
                "total_tokens": 30,
                "total_prompt_tokens": 20,
                "total_completion_tokens": 10,
                "estimated_cost_usd": 0.001,
                "model": "openai/gpt-4o",
            },
        )()
        result = await run_pipeline(_MOCK_CONTEXT, _MOCK_CONFIG)

    summary, verified, cost_badge = result
    assert isinstance(summary, SummaryResult)
    assert isinstance(verified, VerifiedFindings)
    assert verified.was_degraded is False
    assert isinstance(cost_badge, CostBadge)


async def test_run_pipeline_verification_failure_returns_unverified():
    """Pass 3 raises RuntimeError → run_pipeline does NOT raise, returns was_degraded=True."""
    _reset_semaphore()
    with (
        patch(
            "d1ff.pipeline.orchestrator.run_summary_pass",
            new_callable=AsyncMock,
            return_value=_MOCK_SUMMARY,
        ),
        patch(
            "d1ff.pipeline.orchestrator.run_review_pass",
            new_callable=AsyncMock,
            return_value=_MOCK_FINDINGS,
        ),
        patch(
            "d1ff.pipeline.orchestrator.run_verification_pass",
            new_callable=AsyncMock,
            side_effect=RuntimeError("verification timeout"),
        ),
        patch(
            "d1ff.pipeline.orchestrator.get_settings",
            return_value=type("S", (), {"MAX_CONCURRENT_REVIEWS": 5})(),
        ),
        patch(
            "d1ff.pipeline.orchestrator.aggregate_costs",
        ) as mock_agg,
    ):
        mock_agg.return_value = type(
            "RC",
            (),
            {
                "total_tokens": 15,
                "total_prompt_tokens": 10,
                "total_completion_tokens": 5,
                "estimated_cost_usd": 0.0,
                "model": "openai/gpt-4o",
            },
        )()
        # Must NOT raise
        summary, verified, cost_badge = await run_pipeline(_MOCK_CONTEXT, _MOCK_CONFIG)

    assert summary is _MOCK_SUMMARY
    assert isinstance(verified, VerifiedFindings)
    assert verified.was_degraded is True
    assert verified.findings == _MOCK_FINDINGS.findings


async def test_run_pipeline_pass2_failure_still_raises():
    """Pass 2 raises → run_pipeline still re-raises (regression guard for existing behavior)."""
    _reset_semaphore()
    with (
        patch(
            "d1ff.pipeline.orchestrator.run_summary_pass",
            new_callable=AsyncMock,
            return_value=_MOCK_SUMMARY,
        ),
        patch(
            "d1ff.pipeline.orchestrator.run_review_pass",
            new_callable=AsyncMock,
            side_effect=RuntimeError("review pass fatal error"),
        ),
        patch(
            "d1ff.pipeline.orchestrator.get_settings",
            return_value=type("S", (), {"MAX_CONCURRENT_REVIEWS": 5})(),
        ),
        pytest.raises(RuntimeError, match="review pass fatal error"),
    ):
        await run_pipeline(_MOCK_CONTEXT, _MOCK_CONFIG)


async def test_run_pipeline_cost_badge_none_on_aggregate_failure():
    """If aggregate_costs raises, cost_badge is None — pipeline still succeeds."""
    _reset_semaphore()
    with (
        patch(
            "d1ff.pipeline.orchestrator.run_summary_pass",
            new_callable=AsyncMock,
            return_value=_MOCK_SUMMARY,
        ),
        patch(
            "d1ff.pipeline.orchestrator.run_review_pass",
            new_callable=AsyncMock,
            return_value=_MOCK_FINDINGS,
        ),
        patch(
            "d1ff.pipeline.orchestrator.run_verification_pass",
            new_callable=AsyncMock,
            return_value=_MOCK_VERIFIED,
        ),
        patch(
            "d1ff.pipeline.orchestrator.get_settings",
            return_value=type("S", (), {"MAX_CONCURRENT_REVIEWS": 5})(),
        ),
        patch(
            "d1ff.pipeline.orchestrator.aggregate_costs",
            side_effect=RuntimeError("cost aggregation failed"),
        ),
    ):
        summary, verified, cost_badge = await run_pipeline(_MOCK_CONTEXT, _MOCK_CONFIG)

    assert summary is _MOCK_SUMMARY
    assert isinstance(verified, VerifiedFindings)
    assert cost_badge is None


# ---------------------------------------------------------------------------
# Story 5.3: Tests for pipeline_verification_stats log event (AC: 1, 2)
# ---------------------------------------------------------------------------


def _make_finding(
    file: str,
    line: int,
    category: str = "bug",
    severity: str = "warning",
) -> ReviewFinding:
    return ReviewFinding(
        severity=severity,  # type: ignore[arg-type]
        category=category,  # type: ignore[arg-type]
        confidence="high",
        file=file,
        line=line,
        message="Test finding.",
        suggestion=None,
    )


_FINDING_A = _make_finding("src/a.py", 1, "bug", "warning")
_FINDING_B = _make_finding("src/a.py", 2, "style", "nitpick")
_FINDING_C = _make_finding("src/a.py", 3, "maintainability", "suggestion")

_FINDINGS_3 = ReviewFindings(
    findings=[_FINDING_A, _FINDING_B, _FINDING_C], cost=_MOCK_COST
)
_VERIFIED_2 = VerifiedFindings(
    findings=[_FINDING_A, _FINDING_B], cost=_MOCK_COST, was_degraded=False
)


_AGG_RESULT = type(
    "RC",
    (),
    {
        "total_tokens": 30,
        "total_prompt_tokens": 20,
        "total_completion_tokens": 10,
        "estimated_cost_usd": 0.001,
        "model": "openai/gpt-4o",
    },
)()


async def test_orchestrator_logs_pipeline_verification_stats():
    """3 pre/2 post-verification → pipeline_verification_stats event logged."""
    _reset_semaphore()
    with (
        patch(
            "d1ff.pipeline.orchestrator.run_summary_pass",
            new_callable=AsyncMock,
            return_value=_MOCK_SUMMARY,
        ),
        patch(
            "d1ff.pipeline.orchestrator.run_review_pass",
            new_callable=AsyncMock,
            return_value=_FINDINGS_3,
        ),
        patch(
            "d1ff.pipeline.orchestrator.run_verification_pass",
            new_callable=AsyncMock,
            return_value=_VERIFIED_2,
        ),
        patch(
            "d1ff.pipeline.orchestrator.get_settings",
            return_value=type("S", (), {"MAX_CONCURRENT_REVIEWS": 5})(),
        ),
        patch(
            "d1ff.pipeline.orchestrator.aggregate_costs",
            return_value=_AGG_RESULT,
        ),
        structlog.testing.capture_logs() as cap_logs,
    ):
        await run_pipeline(_MOCK_CONTEXT, _MOCK_CONFIG)

    stats_event = next(
        e for e in cap_logs if e["event"] == "pipeline_verification_stats"
    )
    assert stats_event["pre_verification_count"] == 3
    assert stats_event["post_verification_count"] == 2
    assert stats_event["filtered_count"] == 1
    assert stats_event["was_degraded"] is False


async def test_orchestrator_logs_pipeline_verification_stats_degraded():
    """Verification fails → orchestrator falls back; was_degraded=True logged."""
    _reset_semaphore()
    with (
        patch(
            "d1ff.pipeline.orchestrator.run_summary_pass",
            new_callable=AsyncMock,
            return_value=_MOCK_SUMMARY,
        ),
        patch(
            "d1ff.pipeline.orchestrator.run_review_pass",
            new_callable=AsyncMock,
            return_value=_FINDINGS_3,
        ),
        patch(
            "d1ff.pipeline.orchestrator.run_verification_pass",
            new_callable=AsyncMock,
            side_effect=RuntimeError("verification failed"),
        ),
        patch(
            "d1ff.pipeline.orchestrator.get_settings",
            return_value=type("S", (), {"MAX_CONCURRENT_REVIEWS": 5})(),
        ),
        patch(
            "d1ff.pipeline.orchestrator.aggregate_costs",
            return_value=_AGG_RESULT,
        ),
        structlog.testing.capture_logs() as cap_logs,
    ):
        await run_pipeline(_MOCK_CONTEXT, _MOCK_CONFIG)

    stats_event = next(
        e for e in cap_logs if e["event"] == "pipeline_verification_stats"
    )
    assert stats_event["was_degraded"] is True


async def test_orchestrator_verification_stats_zero_findings():
    """Empty findings → pre/post/filtered all 0 in pipeline_verification_stats."""
    _reset_semaphore()
    empty_findings = ReviewFindings(findings=[], cost=_MOCK_COST)
    empty_verified = VerifiedFindings(findings=[], cost=_MOCK_COST, was_degraded=False)
    with (
        patch(
            "d1ff.pipeline.orchestrator.run_summary_pass",
            new_callable=AsyncMock,
            return_value=_MOCK_SUMMARY,
        ),
        patch(
            "d1ff.pipeline.orchestrator.run_review_pass",
            new_callable=AsyncMock,
            return_value=empty_findings,
        ),
        patch(
            "d1ff.pipeline.orchestrator.run_verification_pass",
            new_callable=AsyncMock,
            return_value=empty_verified,
        ),
        patch(
            "d1ff.pipeline.orchestrator.get_settings",
            return_value=type("S", (), {"MAX_CONCURRENT_REVIEWS": 5})(),
        ),
        patch(
            "d1ff.pipeline.orchestrator.aggregate_costs",
            return_value=_AGG_RESULT,
        ),
        structlog.testing.capture_logs() as cap_logs,
    ):
        await run_pipeline(_MOCK_CONTEXT, _MOCK_CONFIG)

    stats_event = next(
        e for e in cap_logs if e["event"] == "pipeline_verification_stats"
    )
    assert stats_event["pre_verification_count"] == 0
    assert stats_event["post_verification_count"] == 0
    assert stats_event["filtered_count"] == 0
