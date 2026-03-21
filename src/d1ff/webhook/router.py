"""FastAPI router for GitHub webhook ingestion."""

import json

import aiosqlite
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from d1ff.config import AppSettings, get_settings
from d1ff.middleware import limiter
from d1ff.storage.database import get_db_connection
from d1ff.storage.installation_repo import InstallationRepository
from d1ff.webhook.event_dispatcher import dispatch_event
from d1ff.webhook.models import WebhookEvent
from d1ff.webhook.signature_verifier import verify_signature

logger = structlog.get_logger()

router = APIRouter()


def _webhook_rate_limit() -> str:
    settings = get_settings()
    if settings.HOSTED_MODE:
        return f"{settings.RATE_LIMIT_PER_MINUTE}/minute"
    return "10000/minute"  # Effectively unlimited for self-hosted


@router.post("/webhook/github", status_code=202, response_model=None)
@limiter.limit(_webhook_rate_limit)
async def receive_webhook(
    request: Request,
    db: aiosqlite.Connection = Depends(get_db_connection),  # noqa: B008
    settings: AppSettings = Depends(get_settings),  # noqa: B008
) -> JSONResponse | dict[str, str]:
    """Receive and process a GitHub App webhook.

    1. Read raw body (must precede any body parsing for HMAC to work).
    2. Verify HMAC-SHA256 signature — reject with 401 if invalid.
    3. Handle ping events immediately (no installation context).
    4. Parse payload and dispatch to the appropriate handler.
    """
    payload_body = await request.body()  # MUST be first — reads raw bytes for HMAC
    signature = request.headers.get("X-Hub-Signature-256")
    delivery_id = request.headers.get("X-GitHub-Delivery", "")
    event_type = request.headers.get("X-GitHub-Event", "")

    secret = settings.GITHUB_WEBHOOK_SECRET.get_secret_value()
    if not verify_signature(payload_body, signature, secret):
        logger.warning(
            "webhook_signature_rejected",
            installation_id=None,
            delivery_id=delivery_id,
            stage="signature_verification",
        )
        raise HTTPException(status_code=401, detail="Invalid signature")

    # ping — GitHub sends this to verify the endpoint on app install
    if event_type == "ping":
        return JSONResponse(content={"status": "pong"}, status_code=200)

    payload: dict = json.loads(payload_body)  # type: ignore[type-arg]

    # Extract installation_id from the payload (may be absent for some event types)
    installation_id: int = 0
    if "installation" in payload and isinstance(payload["installation"], dict):
        installation_id = int(payload["installation"].get("id", 0))

    # Store installation_id in request.state so the rate-limiter key function
    # can key by installation rather than IP (see middleware/rate_limit.py).
    if installation_id:
        request.state.installation_id = str(installation_id)

    logger.info(
        "webhook_received",
        installation_id=installation_id,
        event_type=event_type,
        delivery_id=delivery_id,
        stage="webhook_ingestion",
    )

    event = WebhookEvent(
        event_type=event_type,
        delivery_id=delivery_id,
        installation_id=installation_id,
        payload=payload,
    )

    installation_repo = InstallationRepository(db)
    await dispatch_event(event, installation_repo)

    return {"status": "accepted"}
