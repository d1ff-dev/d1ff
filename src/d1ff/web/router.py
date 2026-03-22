"""Web UI OAuth routes for the d1ff application."""

import aiosqlite
import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from starlette.responses import Response

from d1ff.config import get_settings
from d1ff.github.oauth_handler import oauth
from d1ff.storage.encryption import encrypt_value
from d1ff.storage.database import get_db_connection
from d1ff.storage.installation_repo import InstallationRepository
from d1ff.web.auth import GITHUB_APP_INSTALL_URL

logger = structlog.get_logger()

router = APIRouter()


@router.get("/auth/github/login")
async def github_login(request: Request) -> Response:
    """Initiate GitHub OAuth authorization flow."""
    settings = get_settings()
    redirect_uri = f"{settings.BASE_URL}/auth/github/callback"
    return await oauth.github.authorize_redirect(request, redirect_uri)  # type: ignore[no-any-return]


@router.get("/auth/github/callback", name="github_callback")
async def github_callback(
    request: Request,
    db: aiosqlite.Connection = Depends(get_db_connection),  # noqa: B008
) -> Response:
    """Handle GitHub OAuth callback — create/update user, sync installations, redirect to /settings."""
    try:
        token = await oauth.github.authorize_access_token(request)
    except (KeyError, ValueError, OSError) as exc:
        logger.exception("oauth_callback_failed", error=str(exc))
        return RedirectResponse(url=GITHUB_APP_INSTALL_URL, status_code=302)

    access_token = token["access_token"]

    # Fetch user profile from GitHub
    resp = await oauth.github.get("user", token=token)
    if resp.status_code != 200:
        logger.error("github_user_api_failed", status=resp.status_code)
        return RedirectResponse(url=GITHUB_APP_INSTALL_URL, status_code=302)
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
    page = 1
    try:
        while True:
            installations_resp = await oauth.github.get(
                "user/installations", token=token, params={"per_page": 100, "page": page}
            )
            if installations_resp.status_code != 200:
                logger.error("github_installations_api_failed", status=installations_resp.status_code)
                break
            installations_data = installations_resp.json()
            batch = installations_data.get("installations", [])
            installation_ids.extend(inst["id"] for inst in batch)
            if len(batch) < 100:
                break
            page += 1
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

    logger.info("user_logged_in", login=user_data["login"], installations_synced=len(installation_ids))
    return RedirectResponse(url="/settings", status_code=302)


@router.get("/logout")
async def logout(request: Request) -> Response:
    """Clear session and redirect to GitHub App install page."""
    login = request.session.get("user", {}).get("login", "unknown")
    request.session.clear()
    logger.info("user_logged_out", login=login)
    return RedirectResponse(url=GITHUB_APP_INSTALL_URL, status_code=302)
