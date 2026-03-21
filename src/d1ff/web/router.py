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
from d1ff.storage.installation_repo import InstallationRepository

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


@router.get("/login")
async def login_page(request: Request) -> Response:
    """Render the login page with a 'Sign in with GitHub' button."""
    return templates.TemplateResponse(request, "login.html")


@router.get("/auth/github/login")
async def github_login(request: Request) -> Response:
    """Initiate GitHub OAuth authorization flow."""
    settings = get_settings()
    redirect_uri = f"{settings.BASE_URL}/auth/github/callback"
    return await oauth.github.authorize_redirect(request, redirect_uri)  # type: ignore[no-any-return]


@router.get("/auth/github/callback", name="github_callback")
async def github_callback(request: Request) -> Response:
    """Handle GitHub OAuth callback, create session, redirect to /settings."""
    try:
        token = await oauth.github.authorize_access_token(request)
    except Exception:
        logger.exception("oauth_callback_failed")
        return RedirectResponse(url="/login", status_code=302)
    resp = await oauth.github.get("user", token=token)
    user_data = resp.json()
    request.session["user"] = {
        "login": user_data["login"],
        "id": user_data["id"],
        "name": user_data.get("name"),
    }
    logger.info("user_logged_in", login=user_data["login"])
    return RedirectResponse(url="/settings", status_code=302)


@router.get("/logout")
async def logout(request: Request) -> Response:
    """Clear session and redirect to login page."""
    login = request.session.get("user", {}).get("login", "unknown")
    request.session.clear()
    logger.info("user_logged_out", login=login)
    return RedirectResponse(url="/login", status_code=302)


@router.get("/settings")
async def settings_page(
    request: Request,
    db: aiosqlite.Connection = Depends(get_db_connection),  # noqa: B008
) -> Response:
    """Render settings page showing installations and API key config for the authenticated user."""
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    installation_repo = InstallationRepository(db)
    all_installations = await installation_repo.list_installations()
    user_installations = [i for i in all_installations if i.account_login == user["login"]]

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
        return RedirectResponse(url="/login", status_code=302)

    # Verify the authenticated user owns this installation
    installation_repo = InstallationRepository(db)
    all_installations = await installation_repo.list_installations()
    user_installations = [i for i in all_installations if i.account_login == user["login"]]
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
