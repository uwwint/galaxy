from types import SimpleNamespace
from unittest.mock import MagicMock

from galaxy.managers.auth_sessions import (
    AUTH_SESSION_COOKIE_NAME,
    AUTH_SESSION_CSRF_COOKIE_NAME,
)
from galaxy.selenium.navigates_galaxy import NavigatesGalaxy
from galaxy.util import DEFAULT_SOCKET_TIMEOUT


class _TestNavigatesGalaxy(NavigatesGalaxy):
    def __init__(self, cookies: list[dict[str, str]]):
        self._driver_impl = SimpleNamespace(get_cookies=MagicMock(return_value=cookies))

    @property
    def _driver_impl(self):
        return self.__driver_impl

    @_driver_impl.setter
    def _driver_impl(self, driver_impl):
        self.__driver_impl = driver_impl

    def build_url(self, url: str, for_selenium: bool = True) -> str:
        return f"https://example.test/{url}"

    def screenshot(self, label: str) -> None:
        raise NotImplementedError


def _make_masthead() -> SimpleNamespace:
    return SimpleNamespace(
        _=SimpleNamespace(wait_for_visible=MagicMock()),
        logged_in_only=SimpleNamespace(wait_for_visible=MagicMock()),
        login_masthead_button=SimpleNamespace(wait_for_present=MagicMock()),
    )


def test_wait_for_masthead_waits_for_logged_out_controls() -> None:
    masthead = _make_masthead()
    nav = SimpleNamespace(components=SimpleNamespace(masthead=masthead), is_logged_in=MagicMock(return_value=False))

    NavigatesGalaxy.wait_for_masthead(nav)

    masthead._.wait_for_visible.assert_called_once()
    masthead.login_masthead_button.wait_for_present.assert_called_once()
    masthead.logged_in_only.wait_for_visible.assert_not_called()


def test_wait_for_masthead_waits_for_logged_in_controls() -> None:
    masthead = _make_masthead()
    nav = SimpleNamespace(components=SimpleNamespace(masthead=masthead), is_logged_in=MagicMock(return_value=True))

    NavigatesGalaxy.wait_for_masthead(nav)

    masthead._.wait_for_visible.assert_called_once()
    masthead.logged_in_only.wait_for_visible.assert_called_once()
    masthead.login_masthead_button.wait_for_present.assert_not_called()


def test_get_access_token_bootstraps_from_refresh_cookie(monkeypatch) -> None:
    nav = _TestNavigatesGalaxy(
        [
            {"name": AUTH_SESSION_COOKIE_NAME, "value": "refresh-token"},
            {"name": AUTH_SESSION_CSRF_COOKIE_NAME, "value": "csrf-token"},
        ]
    )
    post = MagicMock(
        return_value=SimpleNamespace(ok=True, json=MagicMock(return_value={"access_token": "access-token"}))
    )
    monkeypatch.setattr("galaxy.selenium.navigates_galaxy.requests.post", post)

    access_token = nav.get_access_token()

    assert access_token == "access-token"
    post.assert_called_once_with(
        "https://example.test/auth/bootstrap",
        cookies={AUTH_SESSION_COOKIE_NAME: "refresh-token"},
        headers={"X-CSRF-Token": "csrf-token"},
        timeout=DEFAULT_SOCKET_TIMEOUT,
    )


def test_get_access_token_uses_cache(monkeypatch) -> None:
    nav = _TestNavigatesGalaxy(
        [
            {"name": AUTH_SESSION_COOKIE_NAME, "value": "refresh-token"},
            {"name": AUTH_SESSION_CSRF_COOKIE_NAME, "value": "csrf-token"},
        ]
    )
    nav._selenium_access_token_cache = "cached-token"
    post = MagicMock()
    monkeypatch.setattr("galaxy.selenium.navigates_galaxy.requests.post", post)

    access_token = nav.get_access_token()

    assert access_token == "cached-token"
    post.assert_not_called()


def test_get_access_token_returns_none_without_refresh_cookie(monkeypatch) -> None:
    nav = _TestNavigatesGalaxy([])
    post = MagicMock()
    monkeypatch.setattr("galaxy.selenium.navigates_galaxy.requests.post", post)

    assert nav.get_access_token() is None
    post.assert_not_called()


def test_get_access_token_returns_none_for_bootstrap_without_access_token(monkeypatch) -> None:
    nav = _TestNavigatesGalaxy(
        [
            {"name": AUTH_SESSION_COOKIE_NAME, "value": "refresh-token"},
            {"name": AUTH_SESSION_CSRF_COOKIE_NAME, "value": "csrf-token"},
        ]
    )
    post = MagicMock(return_value=SimpleNamespace(ok=True, json=MagicMock(return_value={})))
    monkeypatch.setattr("galaxy.selenium.navigates_galaxy.requests.post", post)

    assert nav.get_access_token() is None
    post.assert_called_once()


def test_get_access_token_returns_none_without_csrf_cookie(monkeypatch) -> None:
    nav = _TestNavigatesGalaxy([{"name": AUTH_SESSION_COOKIE_NAME, "value": "refresh-token"}])
    post = MagicMock()
    monkeypatch.setattr("galaxy.selenium.navigates_galaxy.requests.post", post)

    assert nav.get_access_token() is None
    post.assert_not_called()


def test_get_access_token_returns_none_for_failed_bootstrap(monkeypatch) -> None:
    nav = _TestNavigatesGalaxy(
        [
            {"name": AUTH_SESSION_COOKIE_NAME, "value": "refresh-token"},
            {"name": AUTH_SESSION_CSRF_COOKIE_NAME, "value": "csrf-token"},
        ]
    )
    post = MagicMock(
        return_value=SimpleNamespace(ok=False, json=MagicMock(return_value={"access_token": "access-token"}))
    )
    monkeypatch.setattr("galaxy.selenium.navigates_galaxy.requests.post", post)

    assert nav.get_access_token() is None
    post.assert_called_once()


def test_selenium_to_requests_headers_include_both_tokens() -> None:
    nav = _TestNavigatesGalaxy(
        [
            {"name": AUTH_SESSION_COOKIE_NAME, "value": "refresh-token"},
            {"name": AUTH_SESSION_CSRF_COOKIE_NAME, "value": "csrf-token"},
        ]
    )
    nav._selenium_access_token_cache = "access-token"

    assert nav.selenium_to_requests_headers() == {
        "Authorization": "Bearer access-token",
        "X-CSRF-Token": "csrf-token",
    }
