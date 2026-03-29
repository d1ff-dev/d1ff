"""Authentication utilities for web UI route protection."""

from fastapi import Request
from starlette.responses import RedirectResponse


async def require_login(request: Request) -> dict[str, object] | RedirectResponse:
    """Dependency that returns the current user or redirects to login page.

    Saves the original URL as return_to in the session so the user can be
    redirected back after OAuth.
    """
    user: dict[str, object] | None = request.session.get("user")
    if not user:
        request.session["return_to"] = str(request.url)
        return RedirectResponse(url="/login", status_code=302)
    return user
