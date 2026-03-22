import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.sessions import SessionMiddleware

from d1ff.config import get_settings
from d1ff.github import GitHubAppClient
from d1ff.github.oauth_handler import register_github_oauth
from d1ff.middleware import limiter
from d1ff.observability import configure_logging
from d1ff.observability.router import router as observability_router
from d1ff.storage import init_db
from d1ff.web import api_router, web_router
from d1ff.webhook import webhook_router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()  # Triggers fail-fast validation
    configure_logging(settings.LOG_LEVEL)
    register_github_oauth()
    logger.info("d1ff starting", version="0.1.0", host=settings.HOST, port=settings.PORT)
    await init_db(settings.DATABASE_URL)
    logger.info("storage initialized", database_url=settings.DATABASE_URL)

    # Initialise GitHub App client and store in app state for use by dependencies
    app.state.github_client = GitHubAppClient(
        app_id=settings.GITHUB_APP_ID,
        private_key=settings.GITHUB_PRIVATE_KEY,
    )
    logger.info("github_app_client_initialized", app_id=settings.GITHUB_APP_ID)

    yield
    logger.info("d1ff shutting down")


app = FastAPI(title="d1ff", version="0.1.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
# SessionMiddleware is added at module level using os.environ so that import-time
# side effects are avoided (pydantic settings validation runs only in lifespan).
# The lifespan still calls get_settings() which enforces fail-fast for missing vars.
_session_secret = os.environ.get("SESSION_SECRET_KEY", "dev-placeholder-not-for-production")
app.add_middleware(SessionMiddleware, secret_key=_session_secret)
app.include_router(observability_router)
app.include_router(api_router)
app.include_router(webhook_router)
app.include_router(web_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0"}
