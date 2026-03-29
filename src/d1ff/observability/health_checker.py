"""Per-subsystem health check logic."""

import asyncio
import time
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text

from d1ff.config import AppSettings

HealthStatus = Literal["ok", "error"]

_health_cache: dict[str, tuple["SubsystemHealth", float]] = {}
_CACHE_TTL = 30.0


class SubsystemHealth(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: HealthStatus
    detail: str | None = None


class HealthResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    service: SubsystemHealth
    database: SubsystemHealth
    llm_provider: SubsystemHealth
    github_api: SubsystemHealth


async def check_database() -> SubsystemHealth:
    """Check PostgreSQL reachability via the connection pool."""
    from d1ff.storage.database import get_engine

    try:
        engine = get_engine()
        async with asyncio.timeout(3.0):
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        return SubsystemHealth(status="ok")
    except Exception as exc:  # noqa: BLE001
        return SubsystemHealth(status="error", detail=str(exc))


async def check_llm_provider(
    settings: AppSettings, custom_endpoint: str | None = None
) -> SubsystemHealth:
    """Check LLM provider API reachability with a minimal HTTP request.

    When ``custom_endpoint`` is set the check targets that URL instead of the
    default OpenAI API endpoint.  On failure the endpoint URL is included in the
    error detail — it is safe to expose (not a secret).  The API key is NEVER
    included in any response field.
    """
    base_url = custom_endpoint or "https://api.openai.com"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(base_url)
            if resp.status_code < 500:
                return SubsystemHealth(status="ok")
            return SubsystemHealth(
                status="error",
                detail=f"HTTP {resp.status_code} from {base_url}",
            )
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        return SubsystemHealth(
            status="error",
            detail=f"{exc} (endpoint: {base_url})",
        )


async def check_github_api() -> SubsystemHealth:
    """Check GitHub API reachability with a minimal HTTP request."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get("https://api.github.com")
            if resp.status_code < 500:
                return SubsystemHealth(status="ok")
            return SubsystemHealth(status="error", detail=f"HTTP {resp.status_code}")
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        return SubsystemHealth(status="error", detail=str(exc))


def _get_cached(key: str) -> SubsystemHealth | None:
    """Return cached SubsystemHealth if still within TTL, else None."""
    now = time.monotonic()
    if key in _health_cache:
        result, expiry = _health_cache[key]
        if now < expiry:
            return result
    return None


def _set_cached(key: str, result: SubsystemHealth) -> None:
    """Store result in cache with TTL."""
    _health_cache[key] = (result, time.monotonic() + _CACHE_TTL)


async def run_health_check(settings: AppSettings) -> tuple[HealthResponse, int]:
    """Run all subsystem health checks concurrently and return response with HTTP status.

    `service` and `database` are checked live on every call.
    `llm_provider` and `github_api` results are cached for 30 seconds.
    All uncached checks run concurrently via asyncio.gather.
    """
    service_check = SubsystemHealth(status="ok")

    cached_llm = _get_cached("llm_provider")
    cached_github = _get_cached("github_api")

    run_llm = cached_llm is None
    run_github = cached_github is None

    if run_llm and run_github:
        db_result, llm_result, github_result = await asyncio.gather(
            check_database(),
            check_llm_provider(settings),
            check_github_api(),
        )
        _set_cached("llm_provider", llm_result)
        _set_cached("github_api", github_result)
    elif run_llm:
        db_result, llm_result = await asyncio.gather(
            check_database(),
            check_llm_provider(settings),
        )
        github_result = cached_github  # type: ignore[assignment]
        _set_cached("llm_provider", llm_result)
    elif run_github:
        db_result, github_result = await asyncio.gather(
            check_database(),
            check_github_api(),
        )
        llm_result = cached_llm  # type: ignore[assignment]
        _set_cached("github_api", github_result)
    else:
        db_result = await check_database()
        llm_result = cached_llm  # type: ignore[assignment]
        github_result = cached_github  # type: ignore[assignment]

    response = HealthResponse(
        service=service_check,
        database=db_result,
        llm_provider=llm_result,
        github_api=github_result,
    )
    status_code = (
        200
        if all(s.status == "ok" for s in [service_check, db_result, llm_result, github_result])
        else 503
    )
    return response, status_code
