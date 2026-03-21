"""FastAPI router for the observability module — exposes GET /health."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from d1ff.config import AppSettings, get_settings
from d1ff.observability.health_checker import run_health_check

router = APIRouter(tags=["observability"])


@router.get("/health")
async def health(settings: AppSettings = Depends(get_settings)) -> JSONResponse:  # noqa: B008
    """Return per-subsystem health status.

    Returns HTTP 200 when all subsystems are healthy, 503 when any subsystem is degraded.
    llm_provider and github_api results are cached for 30 seconds.
    """
    response, status_code = await run_health_check(settings)
    return JSONResponse(content=response.model_dump(exclude_none=True), status_code=status_code)
