"""Tests for pipeline/review_pass.py — Pass 2 line-by-line review (AC: 3)."""

import json
from unittest.mock import AsyncMock, patch

from d1ff.context.models import FileContext, PRMetadata, ReviewContext
from d1ff.pipeline import ReviewFindings
from d1ff.pipeline.review_pass import run_review_pass
from d1ff.providers.cost_tracker import CostRecord
from d1ff.providers.models import ProviderConfig

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_MOCK_COST = CostRecord(
    prompt_tokens=20,
    completion_tokens=10,
    total_tokens=30,
    estimated_cost_usd=0.002,
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

_VALID_FINDING = {
    "severity": "warning",
    "category": "bug",
    "confidence": "high",
    "file": "src/auth.py",
    "line": 42,
    "message": "Potential null dereference",
    "suggestion": "Add null check before accessing .user_id",
}


def _llm_patch(return_value: str):
    return patch(
        "d1ff.pipeline.review_pass.call_llm_with_retry",
        new_callable=AsyncMock,
        return_value=(return_value, _MOCK_COST),
    )


def _prompt_patch():
    return patch(
        "d1ff.pipeline.review_pass.load_prompt",
        return_value="Review the PR line by line",
    )


def _family_patch():
    return patch(
        "d1ff.pipeline.review_pass.get_provider_family",
        return_value="openai",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_run_review_pass_returns_review_findings():
    """Pass 2 returns ReviewFindings with parsed findings from LLM JSON."""
    payload = json.dumps([_VALID_FINDING])
    with _llm_patch(payload), _prompt_patch(), _family_patch():
        result = await run_review_pass(_MOCK_CONTEXT, _MOCK_CONFIG)

    assert isinstance(result, ReviewFindings)
    assert len(result.findings) == 1
    assert result.findings[0].severity == "warning"
    assert result.findings[0].file == "src/auth.py"
    assert result.cost is _MOCK_COST


async def test_run_review_pass_handles_json_parse_failure_gracefully():
    """Pass 2 returns empty findings (not an exception) when LLM returns non-JSON."""
    with _llm_patch("not json"), _prompt_patch(), _family_patch():
        result = await run_review_pass(_MOCK_CONTEXT, _MOCK_CONFIG)

    assert isinstance(result, ReviewFindings)
    assert result.findings == []
    assert result.cost is _MOCK_COST


async def test_run_review_pass_strips_markdown_code_fences():
    """Pass 2 strips ```json ... ``` fences before parsing."""
    payload = "```json\n[]\n```"
    with _llm_patch(payload), _prompt_patch(), _family_patch():
        result = await run_review_pass(_MOCK_CONTEXT, _MOCK_CONFIG)

    assert isinstance(result, ReviewFindings)
    assert result.findings == []


async def test_run_review_pass_skips_invalid_findings():
    """Pass 2 skips findings that fail Pydantic validation, keeps valid ones."""
    invalid_finding = {**_VALID_FINDING, "severity": "UNKNOWN_VALUE"}
    payload = json.dumps([_VALID_FINDING, invalid_finding])
    with _llm_patch(payload), _prompt_patch(), _family_patch():
        result = await run_review_pass(_MOCK_CONTEXT, _MOCK_CONFIG)

    assert len(result.findings) == 1
    assert result.findings[0].severity == "warning"


async def test_run_review_pass_uses_correct_pass_type():
    """Pass 2 loads the prompt with pass_type='review'."""
    payload = json.dumps([])
    with (
        _llm_patch(payload),
        patch(
            "d1ff.pipeline.review_pass.load_prompt",
            return_value="Review the PR",
        ) as mock_load_prompt,
        _family_patch(),
    ):
        await run_review_pass(_MOCK_CONTEXT, _MOCK_CONFIG)

    mock_load_prompt.assert_called_once()
    _, pass_type = mock_load_prompt.call_args[0]
    assert pass_type == "review"
