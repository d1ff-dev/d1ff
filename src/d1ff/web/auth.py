"""Authentication utilities for web UI route protection."""

from fastapi import Request
from starlette.responses import RedirectResponse


async def require_login(request: Request) -> dict[str, object] | RedirectResponse:
    """Dependency that returns the current user or redirects to /login.

    Uses the direct session check pattern (not HTTPException) to return a proper
    302 RedirectResponse when the user is not authenticated.
    """
    user: dict[str, object] | None = request.session.get("user")
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return user
