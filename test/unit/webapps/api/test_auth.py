from galaxy import model
from galaxy.app_unittest_utils import galaxy_mock
from galaxy.managers.auth_sessions import AUTH_SESSION_COOKIE_NAME
from galaxy.webapps.galaxy.api.auth import (
    bootstrap,
    logout,
    refresh,
)
from galaxy.work.context import (
    GalaxyAbstractRequest,
    GalaxyAbstractResponse,
    SessionRequestContext,
)


class MockRequest(GalaxyAbstractRequest):
    def __init__(self):
        self._headers = {}

    @property
    def base(self) -> str:
        return "http://testserver/"

    @property
    def url_path(self) -> str:
        return self.base

    @property
    def host(self) -> str:
        return "testserver"

    @property
    def is_secure(self) -> bool:
        return False

    def get_cookie(self, name):
        return None

    @property
    def url(self):
        return self.base

    @property
    def headers(self):
        return self._headers

    @property
    def remote_host(self) -> str:
        return self.host

    @property
    def remote_addr(self):
        return "127.0.0.1"


class MockResponse(GalaxyAbstractResponse):
    def __init__(self):
        self._headers = {}
        self.cookies = []

    @property
    def headers(self) -> dict:
        return self._headers

    def set_cookie(
        self,
        key: str,
        value: str = "",
        max_age=None,
        expires=None,
        path: str = "/",
        domain=None,
        secure: bool = False,
        httponly: bool = False,
        samesite="lax",
    ) -> None:
        self.cookies.append(
            {
                "key": key,
                "value": value,
                "max_age": max_age,
                "path": path,
                "domain": domain,
                "secure": secure,
                "httponly": httponly,
                "samesite": samesite,
            }
        )


def _build_trans(
    app, *, user=None, actor_user=None, history=None, galaxy_session=None, auth_session=None, auth_source=None
):
    return SessionRequestContext(
        app=app,
        user=user,
        actor_user=actor_user or user,
        history=history,
        galaxy_session=galaxy_session,
        auth_session=auth_session,
        auth_source=auth_source,
        url_builder=lambda *args, **kwargs: "/mock/url",
        request=MockRequest(),
        response=MockResponse(),
    )


def _cookie_value(trans, key):
    for cookie in reversed(trans.response.cookies):
        if cookie["key"] == key:
            return cookie["value"]
    return None


def test_bootstrap_creates_auth_session_from_legacy_session():
    app = galaxy_mock.MockApp()
    user = app.user_manager.create(email="user@example.org", username="user", password="password")
    history = model.History(user=user)
    galaxy_session = model.GalaxySession(session_key="a" * 32, is_valid=True)
    galaxy_session.user = user
    galaxy_session.current_history = history
    app.model.session.add_all((history, galaxy_session))
    app.model.session.commit()
    trans = _build_trans(app, user=user, history=history, galaxy_session=galaxy_session, auth_source="session")

    payload = bootstrap(trans=trans)

    assert payload["authenticated"] is True
    assert payload["access_token"] is not None
    assert payload["auth_source"] == "galaxy_token"
    assert _cookie_value(trans, AUTH_SESSION_COOKIE_NAME)
    assert trans.auth_session is not None


def test_refresh_rotates_cookie_for_existing_auth_session():
    app = galaxy_mock.MockApp()
    user = app.user_manager.create(email="user@example.org", username="user", password="password")
    auth_session = app.auth_session_manager.create_session(user=user, auth_source="galaxy_token")
    old_refresh_token = app.auth_session_manager.issue_refresh_token(auth_session)
    trans = _build_trans(app, user=user, auth_session=auth_session, auth_source="galaxy_token")

    payload = refresh(trans=trans)

    assert payload["access_token"] is not None
    new_refresh_token = _cookie_value(trans, AUTH_SESSION_COOKIE_NAME)
    assert new_refresh_token
    assert new_refresh_token != old_refresh_token


def test_logout_invalidates_current_auth_session_and_clears_cookie():
    app = galaxy_mock.MockApp()
    user = app.user_manager.create(email="user@example.org", username="user", password="password")
    galaxy_session = model.GalaxySession(session_key="a" * 32, is_valid=True)
    galaxy_session.user = user
    app.model.session.add(galaxy_session)
    app.model.session.commit()
    auth_session = app.auth_session_manager.create_session(user=user, auth_source="galaxy_token")
    app.auth_session_manager.issue_refresh_token(auth_session)
    trans = _build_trans(
        app,
        user=user,
        auth_session=auth_session,
        galaxy_session=galaxy_session,
        auth_source="galaxy_token",
    )

    response = logout(trans=trans)

    assert response["message"] == "Success."
    refreshed = app.auth_session_manager.get_session_by_id(auth_session.id)
    assert refreshed is None
    assert _cookie_value(trans, AUTH_SESSION_COOKIE_NAME) == ""
    assert _cookie_value(trans, "galaxysession")
    assert trans.galaxy_session is not None
    assert trans.galaxy_session.id != galaxy_session.id
    assert trans.galaxy_session.user is None
