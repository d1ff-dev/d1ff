"""JSON API endpoints for the React SPA."""

import aiosqlite
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from d1ff.config import get_settings
from d1ff.github.oauth_handler import oauth
from d1ff.storage.api_key_repo import get_api_key_config, upsert_api_key_for_installation
from d1ff.storage.database import get_db_connection
from d1ff.storage.encryption import decrypt_value, encrypt_value
from d1ff.storage.global_settings_repo import GlobalSettingsRepository
from d1ff.storage.installation_repo import InstallationRepository

logger = structlog.get_logger()

router = APIRouter(prefix="/api", tags=["api"])

ALLOWED_PROVIDERS = {"openai", "anthropic", "google", "deepseek"}


@router.get("/config")
async def get_public_config() -> dict[str, str]:
    """Return public configuration (no auth required)."""
    settings = get_settings()
    return {
        "github_app_install_url": settings.GITHUB_APP_INSTALL_URL,
    }


def _get_session_user(request: Request) -> dict[str, object]:
    user = request.session.get("user")
    if not user or "user_id" not in user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return dict(user)


def _sanitize_config(cfg: dict[str, str | None] | None) -> dict[str, str | bool | None]:
    if not cfg:
        return {"provider": "", "model": "", "has_key": False, "custom_endpoint": None}
    return {
        "provider": cfg.get("provider", ""),
        "model": cfg.get("model", ""),
        "has_key": bool(cfg.get("encrypted_key")),
        "custom_endpoint": cfg.get("custom_endpoint"),
    }


@router.get("/me")
async def get_me(
    request: Request,
    db: aiosqlite.Connection = Depends(get_db_connection),  # noqa: B008
) -> dict[str, object]:
    """Return current authenticated user from session."""
    user = _get_session_user(request)
    repo = GlobalSettingsRepository(db)
    has_settings = await repo.has_settings(user_id=int(str(user["user_id"])))
    return {**user, "hasGlobalSettings": has_settings}


@router.get("/installations")
async def get_installations(
    request: Request,
    db: aiosqlite.Connection = Depends(get_db_connection),  # noqa: B008
) -> list[dict[str, object]]:
    """Return installations and their configs for the authenticated user."""
    user = _get_session_user(request)
    repo = InstallationRepository(db)
    user_installations = await repo.list_installations_for_user(int(str(user["user_id"])))
    result = []
    for inst in user_installations:
        cfg = await get_api_key_config(inst.installation_id)
        result.append(
            {
                "installation": {
                    "installation_id": inst.installation_id,
                    "account_login": inst.account_login,
                    "account_type": inst.account_type,
                },
                "config": _sanitize_config(cfg),
            }
        )
    return result


class GlobalSettingsRequest(BaseModel):
    provider: str
    model: str
    api_key: str
    custom_endpoint: str = ""


class SettingsRequest(BaseModel):
    installation_id: int
    provider: str
    model: str
    api_key: str
    custom_endpoint: str = ""


@router.get("/global-settings")
async def get_global_settings(
    request: Request,
    db: aiosqlite.Connection = Depends(get_db_connection),  # noqa: B008
) -> dict[str, str | bool | None]:
    user = _get_session_user(request)
    repo = GlobalSettingsRepository(db)
    settings = await repo.get(user_id=int(str(user["user_id"])))
    if settings is None:
        raise HTTPException(status_code=404, detail="Global settings not configured")
    return {
        "provider": settings["provider"],
        "model": settings["model"],
        "has_key": bool(settings["encrypted_api_key"]),
        "custom_endpoint": settings["custom_endpoint"],
    }


@router.post("/global-settings")
async def update_global_settings(
    request: Request,
    body: GlobalSettingsRequest,
    db: aiosqlite.Connection = Depends(get_db_connection),  # noqa: B008
) -> dict[str, bool]:
    user = _get_session_user(request)
    if body.provider not in ALLOWED_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Invalid provider: {body.provider}")
    endpoint = body.custom_endpoint.strip() or None
    if endpoint and not (endpoint.startswith("http://") or endpoint.startswith("https://")):
        raise HTTPException(
            status_code=400, detail="Custom endpoint must start with http:// or https://"
        )
    settings = get_settings()
    encrypted_key = encrypt_value(body.api_key, settings.ENCRYPTION_KEY)
    repo = GlobalSettingsRepository(db)
    await repo.upsert(
        user_id=int(str(user["user_id"])),
        provider=body.provider,
        model=body.model,
        encrypted_api_key=encrypted_key,
        custom_endpoint=endpoint,
    )
    logger.info("global_settings_saved", user_id=user["user_id"], provider=body.provider)
    return {"saved": True}


@router.post("/settings")
async def update_settings(
    request: Request,
    body: SettingsRequest,
    db: aiosqlite.Connection = Depends(get_db_connection),  # noqa: B008
) -> dict[str, bool]:
    """Save API key and provider/model config for an installation."""
    user = _get_session_user(request)
    repo = InstallationRepository(db)
    user_installations = await repo.list_installations_for_user(int(str(user["user_id"])))
    user_installation_ids = {i.installation_id for i in user_installations}

    if body.installation_id not in user_installation_ids:
        raise HTTPException(status_code=403, detail="Installation not found or not owned by you.")

    if body.provider not in ALLOWED_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Invalid provider: {body.provider}")

    endpoint = body.custom_endpoint.strip() or None
    if endpoint and not (endpoint.startswith("http://") or endpoint.startswith("https://")):
        raise HTTPException(
            status_code=400,
            detail="Custom endpoint must start with http:// or https://",
        )

    await upsert_api_key_for_installation(
        body.installation_id, body.provider, body.model, body.api_key, custom_endpoint=endpoint
    )
    logger.info("settings_saved", installation_id=body.installation_id, provider=body.provider)
    return {"saved": True}


@router.get("/repositories")
async def get_repositories(
    request: Request,
    db: aiosqlite.Connection = Depends(get_db_connection),  # noqa: B008
) -> list[dict[str, object]]:
    user = _get_session_user(request)
    user_id = int(str(user["user_id"]))

    repo = InstallationRepository(db)
    installations = await repo.list_installations_for_user(user_id)

    # Retrieve user's GitHub token from DB
    cursor = await db.execute("SELECT encrypted_token FROM users WHERE id = ?", (user_id,))
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=500, detail="User record not found")

    settings = get_settings()
    access_token = decrypt_value(row["encrypted_token"], settings.ENCRYPTION_KEY)
    token = {"access_token": access_token, "token_type": "bearer"}

    all_repos: list[dict[str, object]] = []
    for inst in installations:
        page = 1
        while True:
            resp = await oauth.github.get(
                f"user/installations/{inst.installation_id}/repositories",
                token=token,
                params={"per_page": 100, "page": page},
            )
            if resp.status_code != 200:
                logger.warning(
                    "github_repos_fetch_failed",
                    installation_id=inst.installation_id,
                    status=resp.status_code,
                )
                break
            data = resp.json()
            repos = data.get("repositories", [])
            for r in repos:
                all_repos.append(
                    {
                        "name": r["name"],
                        "full_name": r["full_name"],
                        "installation_id": inst.installation_id,
                        "private": r.get("private", False),
                    }
                )
            if len(repos) < 100:
                break
            page += 1

    return all_repos
