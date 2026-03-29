"""Tests for _create_session redirect logic."""

from d1ff.web.router import _determine_redirect


def test_redirect_uses_return_to_when_present() -> None:
    """If session has return_to, redirect there and clear it."""
    session: dict[str, object] = {"return_to": "/settings"}
    url = _determine_redirect(session, installation_count=0, has_setup_action=False)
    assert url == "/settings"
    assert "return_to" not in session


def test_redirect_to_repositories_when_installations_exist() -> None:
    """If user has installations, redirect to /repositories."""
    session: dict[str, object] = {}
    url = _determine_redirect(session, installation_count=3, has_setup_action=False)
    assert url == "/repositories"


def test_redirect_to_setup_when_no_installations() -> None:
    """If user has no installations, redirect to /setup."""
    session: dict[str, object] = {}
    url = _determine_redirect(session, installation_count=0, has_setup_action=False)
    assert url == "/setup"


def test_redirect_to_repositories_when_setup_action_install() -> None:
    """If setup_action=install hint is present, go to /repositories even with 0 installations."""
    session: dict[str, object] = {}
    url = _determine_redirect(session, installation_count=0, has_setup_action=True)
    assert url == "/repositories"
