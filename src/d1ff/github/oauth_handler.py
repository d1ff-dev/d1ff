"""GitHub OAuth client setup using authlib."""

from authlib.integrations.starlette_client import OAuth  # type: ignore[import-untyped]

oauth = OAuth()

# Registration is deferred to avoid calling get_settings() at import time.
# Call register_github_oauth() once during app startup (in lifespan).
_github_registered = False


def register_github_oauth() -> None:
    """Register the GitHub OAuth client with settings. Call once at app startup."""
    global _github_registered  # noqa: PLW0603
    if _github_registered:
        return
    from d1ff.config import get_settings  # local import to avoid import-time side effects

    settings = get_settings()
    oauth.register(
        name="github",
        client_id=settings.GITHUB_CLIENT_ID,
        client_secret=settings.GITHUB_CLIENT_SECRET.get_secret_value(),
        access_token_url="https://github.com/login/oauth/access_token",
        access_token_params=None,
        authorize_url="https://github.com/login/oauth/authorize",
        authorize_params=None,
        api_base_url="https://api.github.com/",
        client_kwargs={"scope": "read:org user:email"},
    )
    _github_registered = True


def get_oauth_client():  # type: ignore[no-untyped-def]
    """Return the registered GitHub OAuth client."""
    return oauth.github
