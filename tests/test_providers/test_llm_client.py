"""Tests for LiteLLM provider client — custom endpoint routing and return type (AC: 1, 6, 7)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from d1ff.providers.cost_tracker import CostRecord
from d1ff.providers.llm_client import call_llm, call_llm_with_retry
from d1ff.providers.models import ProviderConfig


def _make_litellm_response(content: str = "test response") -> MagicMock:
    """Build a minimal mock that mimics litellm.acompletion return value."""
    mock_message = MagicMock()
    mock_message.content = content
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 5
    mock_response.usage.total_tokens = 15
    return mock_response


async def test_call_llm_uses_custom_api_base() -> None:
    """call_llm with custom_endpoint passes api_base to litellm.acompletion."""
    config = ProviderConfig(
        installation_id=1,
        provider="openai",
        model="gpt-4o",
        api_key_encrypted="enc-key",
        custom_endpoint="https://my-proxy.com",
    )
    messages = [{"role": "user", "content": "Hello"}]
    mock_response = _make_litellm_response("Hello back")

    with (
        patch(
            "d1ff.providers.llm_client.litellm.acompletion",
            new=AsyncMock(return_value=mock_response),
        ) as mock_acompletion,
        patch(
            "d1ff.providers.llm_client.decrypt_value",
            return_value="decrypted-api-key",
        ),
        patch(
            "d1ff.providers.llm_client.get_settings",
            return_value=MagicMock(),
        ),
        patch(
            "d1ff.providers.llm_client.litellm.completion_cost",
            return_value=0.001,
        ),
    ):
        result, cost = await call_llm(config, messages)

    assert result == "Hello back"
    assert isinstance(cost, CostRecord)
    assert cost.total_tokens >= 0
    mock_acompletion.assert_called_once()
    call_kwargs = mock_acompletion.call_args[1]
    assert call_kwargs.get("api_base") == "https://my-proxy.com"
    assert call_kwargs.get("model") == "openai/gpt-4o"
    assert call_kwargs.get("messages") == messages
    assert call_kwargs.get("api_key") == "decrypted-api-key"
    assert call_kwargs.get("timeout") == 120


async def test_call_llm_no_api_base_when_no_endpoint() -> None:
    """call_llm with custom_endpoint=None does NOT pass api_base to litellm.acompletion."""
    config = ProviderConfig(
        installation_id=1,
        provider="anthropic",
        model="claude-opus-4-5",
        api_key_encrypted="enc-key",
        custom_endpoint=None,
    )
    messages = [{"role": "user", "content": "Hello"}]
    mock_response = _make_litellm_response("Hi there")

    with (
        patch(
            "d1ff.providers.llm_client.litellm.acompletion",
            new=AsyncMock(return_value=mock_response),
        ) as mock_acompletion,
        patch(
            "d1ff.providers.llm_client.decrypt_value",
            return_value="decrypted-api-key",
        ),
        patch(
            "d1ff.providers.llm_client.get_settings",
            return_value=MagicMock(),
        ),
        patch(
            "d1ff.providers.llm_client.litellm.completion_cost",
            return_value=0.002,
        ),
    ):
        result, cost = await call_llm(config, messages)

    assert result == "Hi there"
    assert isinstance(cost, CostRecord)
    assert cost.total_tokens >= 0
    mock_acompletion.assert_called_once()
    call_kwargs = mock_acompletion.call_args[1]
    assert "api_base" not in call_kwargs
    assert call_kwargs.get("model") == "anthropic/claude-opus-4-5"
    assert call_kwargs.get("api_key") == "decrypted-api-key"
    assert call_kwargs.get("timeout") == 120


async def test_call_llm_with_retry_succeeds_on_first_attempt() -> None:
    """call_llm_with_retry returns result when first attempt succeeds (AC6)."""
    config = ProviderConfig(
        installation_id=1,
        provider="openai",
        model="gpt-4o",
        api_key_encrypted="enc-key",
    )
    messages = [{"role": "user", "content": "Hello"}]
    mock_response = _make_litellm_response("first try")

    with (
        patch(
            "d1ff.providers.llm_client.litellm.acompletion",
            new=AsyncMock(return_value=mock_response),
        ) as mock_acompletion,
        patch(
            "d1ff.providers.llm_client.decrypt_value",
            return_value="decrypted-api-key",
        ),
        patch(
            "d1ff.providers.llm_client.get_settings",
            return_value=MagicMock(),
        ),
        patch(
            "d1ff.providers.llm_client.litellm.completion_cost",
            return_value=0.001,
        ),
    ):
        result, cost = await call_llm_with_retry(config, messages)

    assert result == "first try"
    assert isinstance(cost, CostRecord)
    mock_acompletion.assert_called_once()


async def test_call_llm_with_retry_retries_on_first_failure() -> None:
    """call_llm_with_retry retries once after first failure (AC6, NFR19)."""
    config = ProviderConfig(
        installation_id=1,
        provider="openai",
        model="gpt-4o",
        api_key_encrypted="enc-key",
    )
    messages = [{"role": "user", "content": "Hello"}]
    mock_response = _make_litellm_response("retry success")

    with (
        patch(
            "d1ff.providers.llm_client.litellm.acompletion",
            new=AsyncMock(
                side_effect=[RuntimeError("provider error"), mock_response],
            ),
        ) as mock_acompletion,
        patch(
            "d1ff.providers.llm_client.decrypt_value",
            return_value="decrypted-api-key",
        ),
        patch(
            "d1ff.providers.llm_client.get_settings",
            return_value=MagicMock(),
        ),
        patch(
            "d1ff.providers.llm_client.litellm.completion_cost",
            return_value=0.001,
        ),
        patch("d1ff.providers.llm_client.asyncio.sleep", new=AsyncMock()) as mock_sleep,
    ):
        result, cost = await call_llm_with_retry(config, messages)

    assert result == "retry success"
    assert isinstance(cost, CostRecord)
    assert mock_acompletion.call_count == 2
    mock_sleep.assert_called_once_with(2.0)


async def test_call_llm_with_retry_propagates_on_second_failure() -> None:
    """call_llm_with_retry propagates exception when both attempts fail (AC6)."""
    config = ProviderConfig(
        installation_id=1,
        provider="openai",
        model="gpt-4o",
        api_key_encrypted="enc-key",
    )
    messages = [{"role": "user", "content": "Hello"}]

    with (
        patch(
            "d1ff.providers.llm_client.litellm.acompletion",
            new=AsyncMock(
                side_effect=[RuntimeError("first fail"), RuntimeError("second fail")],
            ),
        ) as mock_acompletion,
        patch(
            "d1ff.providers.llm_client.decrypt_value",
            return_value="decrypted-api-key",
        ),
        patch(
            "d1ff.providers.llm_client.get_settings",
            return_value=MagicMock(),
        ),
        patch("d1ff.providers.llm_client.asyncio.sleep", new=AsyncMock()) as mock_sleep,
        pytest.raises(RuntimeError, match="second fail"),
    ):
        await call_llm_with_retry(config, messages)

    assert mock_acompletion.call_count == 2
    mock_sleep.assert_called_once_with(2.0)
