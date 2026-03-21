"""
Per-installation rate limiter using slowapi (AD-7).

Abuse protection for the hosted tier. Disabled on self-hosted deployments
(HOSTED_MODE=False). Uses in-memory storage — no Redis required for MVP.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def _get_installation_id(request: Request) -> str:
    """Key function: rate-limit by GitHub installation_id from webhook payload.

    Falls back to remote IP address if installation_id is not yet parsed
    (e.g., signature verification failures before payload is decoded).
    """
    # The webhook router stores installation_id in request.state after
    # signature verification and payload parsing. If not yet set, fall back
    # to IP address to still provide basic abuse protection.
    installation_id: str | None = getattr(request.state, "installation_id", None)
    if installation_id:
        return str(installation_id)
    return get_remote_address(request)


limiter: Limiter = Limiter(key_func=_get_installation_id)


def get_limiter() -> Limiter:
    """Return the module-level limiter instance for FastAPI dependency injection."""
    return limiter
