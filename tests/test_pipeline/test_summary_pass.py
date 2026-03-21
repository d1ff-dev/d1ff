"""Tests for pipeline/summary_pass.py — Pass 1 summary generation (AC: 2)."""

from unittest.mock import AsyncMock, patch

import pytest

from d1ff.context.models import FileContext, PRMetadata, ReviewContext
from d1ff.pipeline import SummaryResult
from d1ff.pipeline.summary_pass import run_summary_pass
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

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_run_summary_pass_returns_summary_result():
    """Pass 1 returns SummaryResult with the LLM text as summary."""
    with (
        patch(
            "d1ff.pipeline.summary_pass.call_llm_with_retry",
            new_callable=AsyncMock,
        ) as mock_llm,
        patch(
            "d1ff.pipeline.summary_pass.load_prompt",
            return_value="Summarize the PR",
        ),
        patch(
            "d1ff.pipeline.summary_pass.get_provider_family",
            return_value="openai",
        ),
    ):
        mock_llm.return_value = ("This PR adds auth module.", _MOCK_COST)
        result = await run_summary_pass(_MOCK_CONTEXT, _MOCK_CONFIG)

    assert isinstance(result, SummaryResult)
    assert result.summary == "This PR adds auth module."
    assert result.cost is _MOCK_COST


async def test_run_summary_pass_propagates_llm_exception():
    """Pass 1 does NOT swallow LLM exceptions — they propagate to the orchestrator."""
    with (
        patch(
            "d1ff.pipeline.summary_pass.call_llm_with_retry",
            new_callable=AsyncMock,
            side_effect=RuntimeError("LLM timeout"),
        ),
        patch(
            "d1ff.pipeline.summary_pass.load_prompt",
            return_value="Summarize the PR",
        ),
        patch(
            "d1ff.pipeline.summary_pass.get_provider_family",
            return_value="openai",
        ),
        pytest.raises(RuntimeError, match="LLM timeout"),
    ):
        await run_summary_pass(_MOCK_CONTEXT, _MOCK_CONFIG)


async def test_run_summary_pass_uses_correct_pass_type():
    """Pass 1 loads the prompt with pass_type='summary'."""
    with (
        patch(
            "d1ff.pipeline.summary_pass.call_llm_with_retry",
            new_callable=AsyncMock,
            return_value=("summary text", _MOCK_COST),
        ),
        patch(
            "d1ff.pipeline.summary_pass.load_prompt",
            return_value="Summarize the PR",
        ) as mock_load_prompt,
        patch(
            "d1ff.pipeline.summary_pass.get_provider_family",
            return_value="openai",
        ),
    ):
        await run_summary_pass(_MOCK_CONTEXT, _MOCK_CONFIG)

    mock_load_prompt.assert_called_once()
    _, pass_type = mock_load_prompt.call_args[0]
    assert pass_type == "summary"
