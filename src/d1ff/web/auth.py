"""Authentication utilities for web UI route protection."""

from fastapi import Request
from starlette.responses import RedirectResponse

# Canonical location for the GitHub App install URL — imported by router.py too.
GITHUB_APP_INSTALL_URL = "https://github.com/apps/d1ff-app/installations/new"


async def require_login(request: Request) -> dict[str, object] | RedirectResponse:
    """Dependency that returns the current user or redirects to GitHub App install page.

    Uses the direct session check pattern (not HTTPException) to return a proper
    302 RedirectResponse when the user is not authenticated.
    """
    user: dict[str, object] | None = request.session.get("user")
    if not user:
        return RedirectResponse(url=GITHUB_APP_INSTALL_URL, status_code=302)
    return user
