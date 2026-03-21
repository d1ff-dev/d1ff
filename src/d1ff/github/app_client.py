"""GitHub App authentication client using githubkit."""

from githubkit import AppAuthStrategy, AppInstallationAuthStrategy, GitHub


class GitHubAppClient:
    """Provides authenticated GitHub clients for App-level and installation-scoped calls.

    The private key is the raw PEM string from the GITHUB_PRIVATE_KEY env var.
    It is never written to disk. githubkit handles JWT generation (10-minute expiry)
    and installation token refresh (1-hour expiry) automatically.
    """

    def __init__(self, app_id: int, private_key: str) -> None:
        """Initialise the client.

        Args:
            app_id: The GitHub App ID (numeric).
            private_key: The PEM-encoded RSA private key as a plain string.
                         Obtain via ``settings.GITHUB_PRIVATE_KEY.get_secret_value()``.
        """
        self._app_id = app_id
        self._private_key = private_key

    async def get_installation_client(self, installation_id: int) -> GitHub:  # type: ignore[type-arg]
        """Return a GitHub client scoped to the given installation.

        Uses githubkit's AppInstallationAuthStrategy which handles token refresh
        automatically — no manual caching required.
        """
        return GitHub(
            AppInstallationAuthStrategy(
                app_id=self._app_id,
                private_key=self._private_key,
                installation_id=installation_id,
            )
        )

    async def get_app_client(self) -> GitHub:  # type: ignore[type-arg]
        """Return a GitHub client authenticated as the App (not a specific installation).

        Used for app-level API calls such as listing installations or querying app metadata.
        """
        return GitHub(
            AppAuthStrategy(
                app_id=self._app_id,
                private_key=self._private_key,
            )
        )
