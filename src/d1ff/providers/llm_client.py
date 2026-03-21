"""LiteLLM provider client — custom endpoint support added in Story 2.4.

Extended in Story 3.4:
- API key decryption at call time (AD-5, NFR7)
- Return type changed to tuple[str, CostRecord] (FR36)
- Retry once with exponential backoff (NFR19)
- Structured logging for LLM calls (AD-11)
"""

from __future__ import annotations

import asyncio
import time

import litellm
import structlog

from d1ff.config import get_settings
from d1ff.providers.cost_tracker import CostRecord, extract_cost_record
from d1ff.providers.model_router import get_litellm_model_string
from d1ff.providers.models import ProviderConfig
from d1ff.storage.encryption import decrypt_value

logger = structlog.get_logger(__name__)


async def call_llm(
    config: ProviderConfig,
    messages: list[dict[str, str]],
) -> tuple[str, CostRecord]:
    """Call LiteLLM with optional custom endpoint routing.

    Decrypts the API key at call time (NFR7 — key never logged).
    Returns (response_text, CostRecord) tuple.
    """
    # SECURITY: decrypt_value() result must never be logged (NFR7)
    api_key = decrypt_value(config.api_key_encrypted, get_settings().ENCRYPTION_KEY)

    model_string = get_litellm_model_string(config.provider, config.model)
    call_kwargs: dict[str, object] = {
        "model": model_string,
        "messages": messages,
        "timeout": 120,
        "api_key": api_key,
    }
    if config.custom_endpoint:
        call_kwargs["api_base"] = config.custom_endpoint

    start_ms = time.monotonic() * 1000
    response = await litellm.acompletion(**call_kwargs)
    duration_ms = time.monotonic() * 1000 - start_ms

    cost = extract_cost_record(response, model_string)

    logger.info(
        "llm_call_complete",
        installation_id=config.installation_id,
        stage="llm_request",
        model=model_string,
        prompt_tokens=cost.prompt_tokens,
        completion_tokens=cost.completion_tokens,
        estimated_cost_usd=cost.estimated_cost_usd,
        duration_ms=round(duration_ms, 2),
    )

    return response.choices[0].message.content or "", cost


async def call_llm_with_retry(
    config: ProviderConfig,
    messages: list[dict[str, str]],
) -> tuple[str, CostRecord]:
    """Call LiteLLM with one retry on failure (exponential backoff, NFR19).

    The first failure triggers a 2-second wait before retrying.
    If the retry also fails, the exception propagates to the caller.
    """
    try:
        return await call_llm(config, messages)
    except Exception:
        await asyncio.sleep(2.0)  # exponential backoff: 2 seconds before retry
        return await call_llm(config, messages)  # let this exception propagate
