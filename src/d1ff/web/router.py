"""Web UI OAuth routes for the d1ff application."""

import os

import aiosqlite
import structlog
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.responses import Response

from d1ff.config import get_settings
from d1ff.github.oauth_handler import oauth
from d1ff.storage.api_key_repo import get_api_key_config, upsert_api_key_for_installation
from d1ff.storage.database import get_db_connection
from d1ff.storage.encryption import encrypt_value
from d1ff.storage.installation_repo import InstallationRepository
from d1ff.web.auth import GITHUB_APP_INSTALL_URL

logger = structlog.get_logger()

router = APIRouter()

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

ALLOWED_PROVIDERS = {"openai", "anthropic", "google", "deepseek"}


def _sanitize_config(cfg: dict[str, str | None] | None) -> dict[str, str | bool | None]:
    """Strip encrypted_key from config before passing to template context.

    Replaces the encrypted ciphertext with a boolean ``has_key`` flag so the
    template can conditionally adjust the form without ever receiving the
    encrypted key material.

    The ``custom_endpoint`` URL is NOT a secret and is safe to expose in the template.
    """
    if not cfg:
        return {}
    return {
        "provider": cfg.get("provider", ""),
        "model": cfg.get("model", ""),
        "has_key": bool(cfg.get("encrypted_key")),
        "custom_endpoint": cfg.get("custom_endpoint"),
    }


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
    # Paginate through all pages; on API error skip sync (preserve existing links).
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
        # On error, skip sync — preserve existing user_installations links

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


@router.get("/settings")
async def settings_page(
    request: Request,
    db: aiosqlite.Connection = Depends(get_db_connection),  # noqa: B008
) -> Response:
    """Render settings page showing installations for the authenticated user."""
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url=GITHUB_APP_INSTALL_URL, status_code=302)

    installation_repo = InstallationRepository(db)
    user_installations = await installation_repo.list_installations_for_user(user["user_id"])

    configs: dict[int, dict[str, str | bool | None]] = {}
    for inst in user_installations:
        cfg = await get_api_key_config(inst.installation_id)
        configs[inst.installation_id] = _sanitize_config(cfg)

    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "user": user,
            "installations": user_installations,
            "configs": configs,
        },
    )


@router.post("/settings")
async def update_settings(
    request: Request,
    installation_id: int = Form(...),  # noqa: B008
    provider: str = Form(...),  # noqa: B008
    model: str = Form(...),  # noqa: B008
    api_key: str = Form(...),  # noqa: B008
    custom_endpoint: str = Form(default=""),  # noqa: B008
    db: aiosqlite.Connection = Depends(get_db_connection),  # noqa: B008
) -> Response:
    """Handle settings form submission — store encrypted API key and provider/model config."""
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url=GITHUB_APP_INSTALL_URL, status_code=302)

    # Verify the authenticated user owns this installation
    installation_repo = InstallationRepository(db)
    user_installations = await installation_repo.list_installations_for_user(user["user_id"])
    user_installation_ids = {i.installation_id for i in user_installations}

    if installation_id not in user_installation_ids:
        configs: dict[int, dict[str, str | bool | None]] = {}
        for inst in user_installations:
            cfg = await get_api_key_config(inst.installation_id)
            configs[inst.installation_id] = _sanitize_config(cfg)
        return templates.TemplateResponse(
            request,
            "settings.html",
            {
                "user": user,
                "installations": user_installations,
                "configs": configs,
                "error": "Installation not found or not owned by you.",
            },
            status_code=403,
        )

    if provider not in ALLOWED_PROVIDERS:
        configs = {}
        for inst in user_installations:
            cfg = await get_api_key_config(inst.installation_id)
            configs[inst.installation_id] = _sanitize_config(cfg)
        return templates.TemplateResponse(
            request,
            "settings.html",
            {
                "user": user,
                "installations": user_installations,
                "configs": configs,
                "error": f"Invalid provider: {provider}",
            },
            status_code=400,
        )

    # Normalize empty string to None; validate URL scheme if provided
    endpoint = custom_endpoint.strip() or None
    if endpoint and not (endpoint.startswith("http://") or endpoint.startswith("https://")):
        configs = {}
        for inst in user_installations:
            cfg = await get_api_key_config(inst.installation_id)
            configs[inst.installation_id] = _sanitize_config(cfg)
        return templates.TemplateResponse(
            request,
            "settings.html",
            {
                "user": user,
                "installations": user_installations,
                "configs": configs,
                "error": "Custom endpoint must start with http:// or https://",
            },
            status_code=400,
        )

    await upsert_api_key_for_installation(
        installation_id, provider, model, api_key, custom_endpoint=endpoint
    )
    logger.info("settings_saved", installation_id=installation_id, provider=provider, model=model)
    return RedirectResponse(url="/settings?saved=true", status_code=303)
