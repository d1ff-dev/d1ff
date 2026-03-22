"""JSON API endpoints for the React SPA."""

import aiosqlite
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from d1ff.storage.api_key_repo import get_api_key_config, upsert_api_key_for_installation
from d1ff.storage.database import get_db_connection
from d1ff.storage.installation_repo import InstallationRepository

logger = structlog.get_logger()

router = APIRouter(prefix="/api", tags=["api"])

ALLOWED_PROVIDERS = {"openai", "anthropic", "google", "deepseek"}


def _get_session_user(request: Request) -> dict[str, object]:
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user  # type: ignore[return-value]


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
async def get_me(request: Request) -> dict[str, object]:
    """Return current authenticated user from session."""
    return _get_session_user(request)


@router.get("/installations")
async def get_installations(
    request: Request,
    db: aiosqlite.Connection = Depends(get_db_connection),  # noqa: B008
) -> list[dict[str, object]]:
    """Return installations and their configs for the authenticated user."""
    user = _get_session_user(request)
    repo = InstallationRepository(db)
    user_installations = await repo.list_installations_for_user(int(user["user_id"]))  # type: ignore[arg-type]
    result = []
    for inst in user_installations:
        cfg = await get_api_key_config(inst.installation_id)
        result.append({
            "installation": {
                "installation_id": inst.installation_id,
                "account_login": inst.account_login,
                "account_type": inst.account_type,
            },
            "config": _sanitize_config(cfg),
        })
    return result


class SettingsRequest(BaseModel):
    installation_id: int
    provider: str
    model: str
    api_key: str
    custom_endpoint: str = ""


@router.post("/settings")
async def update_settings(
    request: Request,
    body: SettingsRequest,
    db: aiosqlite.Connection = Depends(get_db_connection),  # noqa: B008
) -> dict[str, bool]:
    """Save API key and provider/model config for an installation."""
    user = _get_session_user(request)
    repo = InstallationRepository(db)
    user_installations = await repo.list_installations_for_user(int(user["user_id"]))  # type: ignore[arg-type]
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
