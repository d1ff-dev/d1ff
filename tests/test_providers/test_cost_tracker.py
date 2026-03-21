"""Tests for cost_tracker — token counting and cost estimation (FR36, FR37)."""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from d1ff.providers.cost_tracker import (
    CostRecord,
    PassTokens,
    ReviewCost,
    aggregate_costs,
    extract_cost_record,
)


def _make_mock_response(
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
    total_tokens: int = 150,
) -> MagicMock:
    """Build a minimal mock litellm response with usage data."""
    mock_response = MagicMock()
    mock_response.usage.prompt_tokens = prompt_tokens
    mock_response.usage.completion_tokens = completion_tokens
    mock_response.usage.total_tokens = total_tokens
    return mock_response


def test_extract_cost_record_basic() -> None:
    """extract_cost_record returns correct token counts from usage data."""
    mock_response = _make_mock_response(
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
    )
    with patch("d1ff.providers.cost_tracker.litellm.completion_cost", return_value=0.005):
        record = extract_cost_record(mock_response, "openai/gpt-4o")

    assert isinstance(record, CostRecord)
    assert record.prompt_tokens == 100
    assert record.completion_tokens == 50
    assert record.total_tokens == 150
    assert record.estimated_cost_usd == 0.005
    assert record.model == "openai/gpt-4o"


def test_extract_cost_record_cost_calculation_failure() -> None:
    """When litellm.completion_cost raises, estimated_cost_usd defaults to 0.0."""
    mock_response = _make_mock_response(
        prompt_tokens=200,
        completion_tokens=100,
        total_tokens=300,
    )
    with patch(
        "d1ff.providers.cost_tracker.litellm.completion_cost",
        side_effect=Exception("Unknown model"),
    ):
        record = extract_cost_record(mock_response, "custom/unknown-model")

    assert record.estimated_cost_usd == 0.0
    assert record.total_tokens == 300
    assert record.model == "custom/unknown-model"


def test_cost_record_is_frozen() -> None:
    """CostRecord is immutable (frozen Pydantic model)."""
    record = CostRecord(
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        estimated_cost_usd=0.001,
        model="test/model",
    )
    with pytest.raises(ValidationError):
        record.prompt_tokens = 999  # type: ignore[misc]


# ---------------------------------------------------------------------------
# PassTokens and aggregate_costs tests (FR37)
# ---------------------------------------------------------------------------


def test_aggregate_costs_sums_all_passes() -> None:
    """aggregate_costs correctly sums prompt and completion tokens across three passes."""
    passes = [
        PassTokens(pass_name="summary", prompt_tokens=100, completion_tokens=50),
        PassTokens(pass_name="review", prompt_tokens=200, completion_tokens=80),
        PassTokens(pass_name="verification", prompt_tokens=150, completion_tokens=40),
    ]
    with patch(
        "d1ff.providers.cost_tracker.litellm.completion_cost", return_value=0.01
    ):
        result = aggregate_costs(passes, model="anthropic/claude-3-5-haiku-20241022")

    assert result.total_prompt_tokens == 450
    assert result.total_completion_tokens == 170
    assert result.total_tokens == 620
    assert result.estimated_cost_usd == 0.01
    assert result.model == "anthropic/claude-3-5-haiku-20241022"


def test_aggregate_costs_empty_list() -> None:
    """aggregate_costs with no passes returns zero totals."""
    with patch(
        "d1ff.providers.cost_tracker.litellm.completion_cost", return_value=0.0
    ):
        result = aggregate_costs([], model="openai/gpt-4o")

    assert result.total_prompt_tokens == 0
    assert result.total_completion_tokens == 0
    assert result.total_tokens == 0
    assert result.estimated_cost_usd == 0.0


def test_aggregate_costs_unknown_model_defaults_to_zero_cost() -> None:
    """When litellm.completion_cost raises, estimated_cost_usd is 0.0 but tokens are correct."""
    passes = [
        PassTokens(pass_name="summary", prompt_tokens=100, completion_tokens=50),
    ]
    with patch(
        "d1ff.providers.cost_tracker.litellm.completion_cost",
        side_effect=Exception("NotFoundError: model not in pricing registry"),
    ):
        result = aggregate_costs(passes, model="custom/unknown-model")

    assert result.estimated_cost_usd == 0.0
    assert result.total_prompt_tokens == 100
    assert result.total_completion_tokens == 50
    assert result.total_tokens == 150


def test_aggregate_costs_calculates_usd_for_known_model() -> None:
    """aggregate_costs returns non-zero cost for a model with known pricing."""
    passes = [
        PassTokens(pass_name="review", prompt_tokens=1000, completion_tokens=200),
    ]
    with patch(
        "d1ff.providers.cost_tracker.litellm.completion_cost", return_value=0.0025
    ):
        result = aggregate_costs(passes, model="anthropic/claude-3-5-haiku-20241022")

    assert result.estimated_cost_usd > 0.0
    assert result.estimated_cost_usd == 0.0025


def test_review_cost_total_tokens_is_sum() -> None:
    """ReviewCost.total_tokens equals total_prompt_tokens + total_completion_tokens."""
    passes = [
        PassTokens(pass_name="summary", prompt_tokens=300, completion_tokens=120),
        PassTokens(pass_name="review", prompt_tokens=500, completion_tokens=200),
    ]
    with patch(
        "d1ff.providers.cost_tracker.litellm.completion_cost", return_value=0.005
    ):
        result = aggregate_costs(passes, model="openai/gpt-4o")

    assert result.total_tokens == result.total_prompt_tokens + result.total_completion_tokens
    assert result.total_tokens == 800 + 320


def test_pass_tokens_is_frozen() -> None:
    """PassTokens is immutable (frozen Pydantic model)."""
    pt = PassTokens(pass_name="summary", prompt_tokens=10, completion_tokens=5)
    with pytest.raises(ValidationError):
        pt.prompt_tokens = 999  # type: ignore[misc]


def test_review_cost_is_frozen() -> None:
    """ReviewCost is immutable (frozen Pydantic model)."""
    rc = ReviewCost(
        total_prompt_tokens=100,
        total_completion_tokens=50,
        total_tokens=150,
        estimated_cost_usd=0.001,
        model="openai/gpt-4o",
    )
    with pytest.raises(ValidationError):
        rc.total_tokens = 999  # type: ignore[misc]
