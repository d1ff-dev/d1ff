"""Web UI OAuth routes for the d1ff application."""

import aiosqlite
import httpx
import structlog
from authlib.integrations.base_client.errors import (  # type: ignore[import-untyped]
    MismatchingStateError,
)
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from starlette.responses import Response

from d1ff.config import get_settings
from d1ff.github.oauth_handler import oauth
from d1ff.storage.database import get_db_connection
from d1ff.storage.encryption import encrypt_value
from d1ff.storage.installation_repo import InstallationRepository

logger = structlog.get_logger()

router = APIRouter()


@router.get("/auth/github/login")
async def github_login(request: Request) -> Response:
    """Initiate GitHub OAuth authorization flow."""
    settings = get_settings()
    redirect_uri = f"{settings.BASE_URL}/auth/github/callback"
    return await oauth.github.authorize_redirect(request, redirect_uri)  # type: ignore[no-any-return]


async def _exchange_code_for_token(code: str) -> str | None:
    """Exchange an OAuth code for an access token directly via GitHub API.

    Used for the installation flow where authlib state verification is not available.
    """
    settings = get_settings()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://github.com/login/oauth/access_token",
            json={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET.get_secret_value(),
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
        if resp.status_code != 200:
            logger.error("github_token_exchange_failed", status=resp.status_code)
            return None
        data = resp.json()
        return str(data["access_token"]) if "access_token" in data else None


def _determine_redirect(
    session: dict[str, object],
    installation_count: int,
    has_setup_action: bool,
) -> str:
    """Decide where to send the user after OAuth.

    Priority:
    1. return_to URL saved by require_login
    2. /repositories if user has installations OR just completed app installation
    3. /setup if no installations
    """
    return_to = session.pop("return_to", None)
    if return_to and isinstance(return_to, str):
        return return_to
    if installation_count > 0 or has_setup_action:
        return "/repositories"
    return "/setup"


async def _create_session(
    request: Request,
    access_token: str,
    db: aiosqlite.Connection,
) -> Response:
    """Fetch user profile, sync installations, create session, redirect to app."""
    token = {"access_token": access_token, "token_type": "bearer"}

    # Fetch user profile from GitHub
    resp = await oauth.github.get("user", token=token)
    if resp.status_code != 200:
        logger.error("github_user_api_failed", status=resp.status_code)
        return RedirectResponse(url="/login", status_code=302)
    user_data = resp.json()

    # Encrypt access token before storing
    settings = get_settings()
    encrypted_token = encrypt_value(access_token, settings.ENCRYPTION_KEY)

    # Upsert user record
    repo = InstallationRepository(db)
    user_id = await repo.upsert_user(
        github_id=user_data["id"],
        login=user_data["login"],
        email=user_data.get("email"),
        avatar_url=user_data.get("avatar_url"),
        encrypted_token=encrypted_token,
    )

    # Fetch user's installations from GitHub API and sync.
    installation_ids: list[int] = []
    # Query DB BEFORE sync — sync_user_installations wipes the join table,
    # so we need the pre-sync count as a fallback if the API fails.
    db_installations = await repo.list_installations_for_user(user_id)
    db_installation_count = len(db_installations)
    api_succeeded = False
    page = 1
    try:
        while True:
            installations_resp = await oauth.github.get(
                "user/installations", token=token, params={"per_page": 100, "page": page}
            )
            if installations_resp.status_code != 200:
                logger.error(
                    "github_installations_api_failed",
                    status=installations_resp.status_code,
                )
                break
            installations_data = installations_resp.json()
            batch = installations_data.get("installations", [])
            installation_ids.extend(inst["id"] for inst in batch)
            if len(batch) < 100:
                api_succeeded = True
                break
            page += 1
        if api_succeeded:
            await repo.sync_user_installations(user_id, installation_ids)
    except Exception:
        logger.exception("installation_sync_failed")

    # Create session
    request.session["user"] = {
        "login": user_data["login"],
        "github_id": user_data["id"],
        "name": user_data.get("name"),
        "user_id": user_id,
    }

    # Use API count if API succeeded, otherwise fall back to pre-sync DB count.
    # Important: don't use truthiness of installation_ids — an empty list from
    # a successful API call means the user genuinely has 0 installations.
    effective_count = len(installation_ids) if api_succeeded else db_installation_count
    has_setup_action = request.query_params.get("setup_action") == "install"
    redirect_url = _determine_redirect(request.session, effective_count, has_setup_action)

    logger.info(
        "user_logged_in",
        login=user_data["login"],
        installations_synced=len(installation_ids),
        redirect=redirect_url,
    )
    return RedirectResponse(url=redirect_url, status_code=302)


@router.get("/auth/github/callback", name="github_callback")
async def github_callback(
    request: Request,
    db: aiosqlite.Connection = Depends(get_db_connection),  # noqa: B008
) -> Response:
    """Handle GitHub OAuth callback — from both login flow and app installation flow."""
    # Try authlib flow first (normal login via /auth/github/login)
    try:
        token = await oauth.github.authorize_access_token(request)
        return await _create_session(request, token["access_token"], db)
    except (KeyError, ValueError, OSError, MismatchingStateError):
        pass

    # Fallback: installation flow — GitHub sends ?code=xxx&setup_action=install
    code = request.query_params.get("code")
    if not code:
        logger.error("oauth_callback_no_code")
        return RedirectResponse(url="/login", status_code=302)

    access_token = await _exchange_code_for_token(code)
    if not access_token:
        logger.error("oauth_callback_token_exchange_failed")
        return RedirectResponse(url="/login", status_code=302)

    return await _create_session(request, access_token, db)


@router.get("/logout")
async def logout(request: Request) -> Response:
    """Clear session and redirect to login page."""
    login = request.session.get("user", {}).get("login", "unknown")
    request.session.clear()
    logger.info("user_logged_out", login=login)
    return RedirectResponse(url="/login", status_code=302)
