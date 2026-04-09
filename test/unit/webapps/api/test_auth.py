from datetime import (
    datetime,
    timedelta,
)

from galaxy import model
from galaxy.app_unittest_utils import galaxy_mock
from galaxy.managers.auth_sessions import AUTH_SESSION_COOKIE_NAME
from galaxy.managers.users import UserManager
from galaxy.webapps.galaxy.api.auth import (
    bootstrap,
    change_password,
    login,
    logout,
    reset_password,
    register,
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


def test_login_issues_browser_auth_state():
    app = galaxy_mock.MockApp()
    user = app.user_manager.create(email="user@example.org", username="user", password="password")
    history = model.History()
    galaxy_session = model.GalaxySession(session_key="a" * 32, is_valid=True)
    galaxy_session.current_history = history
    app.model.session.add_all((history, galaxy_session))
    app.model.session.commit()
    trans = _build_trans(app, history=history, galaxy_session=galaxy_session, auth_source="session")

    response = login(trans=trans, payload={"login": "user", "password": "password"})

    assert response["message"] == "Success."
    assert response["access_token"] is not None
    assert response["auth_source"] == "galaxy_token"
    assert response["user"]["email"] == user.email
    assert _cookie_value(trans, AUTH_SESSION_COOKIE_NAME)
    assert trans.auth_session is not None
    assert trans.user == user
    assert history.user == user


def test_register_issues_browser_auth_state():
    app = galaxy_mock.MockApp()
    trans = _build_trans(app, auth_source="anonymous")

    response = register(
        trans=trans,
        payload={
            "email": "new@example.org",
            "username": "newuser",
            "password": "password",
            "confirm": "password",
        },
    )

    assert response["message"] == "Success."
    assert response["access_token"] is not None
    assert response["auth_source"] == "galaxy_token"
    assert response["user"]["email"] == "new@example.org"
    assert _cookie_value(trans, AUTH_SESSION_COOKIE_NAME)
    assert trans.auth_session is not None
    assert trans.user is not None


def test_change_password_issues_browser_auth_state_when_no_existing_auth_session():
    app = galaxy_mock.MockApp()
    user = app.user_manager.create(email="user@example.org", username="user", password="password")
    trans = _build_trans(app, user=user, auth_source="anonymous")

    response = change_password(
        trans=trans,
        payload={
            "id": app.security.encode_id(user.id),
            "current": "password",
            "password": "new_password",
            "confirm": "new_password",
        },
    )

    assert response["message"] == "Password has been changed."
    assert response["access_token"] is not None
    assert trans.auth_session is not None


def test_reset_password_returns_message_when_email_is_accepted():
    app = galaxy_mock.MockApp()
    app.user_manager.send_reset_email = lambda trans, payload: None
    trans = _build_trans(app, auth_source="anonymous")

    response = reset_password(trans=trans, payload={"email": "user@example.org"})

    assert response["message"] == "If an account exists for this email address a confirmation email will be dispatched."


def test_login_auto_registers_when_auth_manager_allows_it():
    app = galaxy_mock.MockApp()
    app.auth_manager.check_auto_registration = lambda trans, login, password: {
        "auto_reg": True,
        "email": "auto@example.org",
        "username": "autouser",
    }
    trans = _build_trans(app, auth_source="session")

    response = login(trans=trans, payload={"login": "autouser", "password": "password"})

    assert response["message"] == "Success."
    assert response["user"]["email"] == "auto@example.org"
    assert response["access_token"] is not None
    assert trans.user is not None
    assert trans.user.email == "auto@example.org"


def test_login_resends_activation_email_outside_grace_period():
    app = galaxy_mock.MockApp()
    app.config.user_activation_on = True
    app.config.activation_grace_period = 1
    user_manager = app[UserManager]
    user = user_manager.create(email="inactive@example.org", username="inactive", password="password")
    user.active = False
    user.create_time = datetime.utcnow() - timedelta(hours=2)
    app.model.session.add(user)
    app.model.session.commit()
    user_manager.send_activation_email = lambda trans, email, username: True
    trans = _build_trans(app, auth_source="session")

    response = login(trans=trans, payload={"login": "inactive", "password": "password"})

    assert "This account has not been activated yet" in response["err_msg"]
    assert trans.auth_session is None


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
