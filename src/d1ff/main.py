import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.sessions import SessionMiddleware

from d1ff.config import get_settings
from d1ff.github import GitHubAppClient
from d1ff.github.oauth_handler import register_github_oauth
from d1ff.middleware import limiter
from d1ff.observability import configure_logging
from d1ff.observability.router import router as observability_router
from d1ff.storage.database import (
    dispose_engine,
    ensure_database_exists,
    init_engine,
    run_alembic_upgrade,
)
from d1ff.web import api_router, web_router
from d1ff.webhook import webhook_router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()  # Triggers fail-fast validation
    configure_logging(settings.LOG_LEVEL)
    register_github_oauth()
    logger.info("d1ff starting", version="0.1.0", host=settings.HOST, port=settings.PORT)
    await ensure_database_exists(settings.DATABASE_URL)
    run_alembic_upgrade(settings.DATABASE_URL)
    init_engine(settings.DATABASE_URL)
    logger.info("storage initialized", database_url=settings.DATABASE_URL)

    app.state.github_client = GitHubAppClient(
        app_id=settings.GITHUB_APP_ID,
        private_key=settings.GITHUB_PRIVATE_KEY,
    )
    logger.info("github_app_client_initialized", app_id=settings.GITHUB_APP_ID)

    yield
    await dispose_engine()
    logger.info("d1ff shutting down")


app = FastAPI(title="d1ff", version="0.1.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
_session_secret = os.environ.get("SESSION_SECRET_KEY", "dev-placeholder-not-for-production")
_base_url = os.environ.get("BASE_URL", "http://localhost:8000")
app.add_middleware(
    SessionMiddleware,
    secret_key=_session_secret,
    max_age=30 * 24 * 3600,
    https_only=_base_url.startswith("https://"),
    same_site="lax",
)

# Router registration order matters: specific routes before SPA fallback
app.include_router(observability_router)
app.include_router(api_router)
app.include_router(webhook_router)
app.include_router(web_router)

# Static files + SPA fallback — only registered when the built bundle exists
# (i.e., in Docker). In dev mode (uvicorn from source), this block is skipped
# and the app runs as a pure API server.
_static_dir = Path(__file__).parent.parent.parent / "static"
if _static_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(_static_dir / "assets")), name="assets")

    @app.get("/{path:path}")
    async def spa_fallback(path: str) -> FileResponse:
        return FileResponse(str(_static_dir / "index.html"))
