"""Tests for CostBadge model and review_poster badge integration (AC: 1, 3).

FR36: review summary includes cost badge showing token count and estimated USD cost.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from d1ff.comments.models import CostBadge, FormattedReview, ReviewSummary
from d1ff.comments.review_poster import post_review
from d1ff.context.models import FileContext, PRMetadata, ReviewContext

# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def make_cost_badge(
    total_tokens: int = 1245,
    prompt_tokens: int = 1024,
    completion_tokens: int = 221,
    estimated_cost_usd: float = 0.0812,
    model: str = "anthropic/claude-3-5-haiku-20241022",
) -> CostBadge:
    return CostBadge(
        total_tokens=total_tokens,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        estimated_cost_usd=estimated_cost_usd,
        model=model,
    )


def make_review_context() -> ReviewContext:
    return ReviewContext(
        installation_id=123,
        pr_metadata=PRMetadata(
            number=42,
            title="Add feature X",
            author="alice",
            base_branch="main",
            head_branch="feat/x",
            html_url="https://github.com/acme/backend/pull/42",
            draft=False,
        ),
        diff="+ def foo(): pass",
        changed_files=[FileContext(path="main.py", content="def foo(): pass")],
    )


def make_formatted_review(body: str = "## Review Summary\n\n🔴 Critical: 0") -> FormattedReview:
    return FormattedReview(
        inline_comments=[],
        summary=ReviewSummary(body=body),
        was_degraded=False,
    )


def make_mock_github_client() -> MagicMock:
    mock_pulls = AsyncMock()
    mock_rest = MagicMock()
    mock_rest.pulls = mock_pulls
    mock_gh = MagicMock()
    mock_gh.rest = mock_rest
    mock_client = AsyncMock()
    mock_client.get_installation_client = AsyncMock(return_value=mock_gh)
    return mock_client


# ---------------------------------------------------------------------------
# CostBadge.format() tests
# ---------------------------------------------------------------------------


def test_cost_badge_format_includes_total_tokens() -> None:
    """Badge string contains the formatted total token count."""
    badge = make_cost_badge(total_tokens=1245)
    result = badge.format()
    assert "1,245 tokens" in result


def test_cost_badge_format_includes_input_output_breakdown() -> None:
    """Badge string contains 'in' and 'out' token counts for breakdown."""
    badge = make_cost_badge(prompt_tokens=1024, completion_tokens=221)
    result = badge.format()
    assert "1,024 in" in result
    assert "221 out" in result


def test_cost_badge_format_includes_cost() -> None:
    """Badge string contains '$' prefix and cost value."""
    badge = make_cost_badge(estimated_cost_usd=0.0812)
    result = badge.format()
    assert "$" in result
    assert "0.0812" in result


def test_cost_badge_format_uses_comma_separator() -> None:
    """Token counts above 1000 use comma thousands separator."""
    badge = make_cost_badge(total_tokens=12345, prompt_tokens=10000, completion_tokens=2345)
    result = badge.format()
    assert "12,345" in result
    assert "10,000" in result
    assert "2,345" in result


def test_cost_badge_format_uses_middle_dot_separator() -> None:
    """Badge uses middle dot (·) as separator, not a dash."""
    badge = make_cost_badge()
    result = badge.format()
    assert "·" in result


def test_cost_badge_format_starts_with_chart_emoji() -> None:
    """Badge format starts with the 📊 chart emoji per spec."""
    badge = make_cost_badge()
    result = badge.format()
    assert result.startswith("📊")


def test_cost_badge_format_four_decimal_places() -> None:
    """Cost uses 4 decimal places (sub-cent reviews need full precision)."""
    badge = make_cost_badge(estimated_cost_usd=0.0001)
    result = badge.format()
    assert "$0.0001" in result


def test_cost_badge_is_frozen() -> None:
    """CostBadge is immutable (frozen Pydantic model)."""
    from pydantic import ValidationError

    badge = make_cost_badge()
    with pytest.raises(ValidationError):
        badge.total_tokens = 999  # type: ignore[misc]


# ---------------------------------------------------------------------------
# review_poster cost_badge integration tests
# ---------------------------------------------------------------------------


async def test_review_poster_appends_badge_when_provided() -> None:
    """Summary comment body includes the cost badge when cost_badge is passed."""
    context = make_review_context()
    body = "## Review Summary"
    formatted = make_formatted_review(body=body)
    badge = make_cost_badge(
        total_tokens=500, prompt_tokens=400, completion_tokens=100, estimated_cost_usd=0.005
    )
    mock_client = make_mock_github_client()

    with patch("d1ff.comments.review_poster.asyncio.sleep", new_callable=AsyncMock):
        await post_review(
            formatted, context, mock_client, owner="acme", repo="backend", cost_badge=badge
        )

    mock_gh = await mock_client.get_installation_client(123)
    call_kwargs = mock_gh.rest.pulls.async_create_review.call_args.kwargs
    posted_body = call_kwargs["body"]

    assert "---" in posted_body
    assert "📊" in posted_body
    assert "500" in posted_body or "500" in posted_body.replace(",", "")
    assert "$" in posted_body
    # Original body is still present
    assert "## Review Summary" in posted_body


async def test_review_poster_omits_badge_when_none() -> None:
    """Summary comment body is unchanged when cost_badge=None (graceful degradation)."""
    context = make_review_context()
    body = "## Review Summary\n\n🔴 Critical: 0"
    formatted = make_formatted_review(body=body)
    mock_client = make_mock_github_client()

    await post_review(
        formatted, context, mock_client, owner="acme", repo="backend", cost_badge=None
    )

    mock_gh = await mock_client.get_installation_client(123)
    call_kwargs = mock_gh.rest.pulls.async_create_review.call_args.kwargs
    posted_body = call_kwargs["body"]

    # Body must be identical to original — no badge appended
    assert posted_body == body
    assert "📊" not in posted_body
    assert "---" not in posted_body
