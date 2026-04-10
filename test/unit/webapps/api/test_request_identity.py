from datetime import timedelta

import pytest
from fastapi import (
    APIRouter,
    FastAPI,
)
from fastapi.security import HTTPAuthorizationCredentials
from starlette.testclient import TestClient

from galaxy import (
    app as galaxy_app_module,
    exceptions,
)
from galaxy.app_unittest_utils import galaxy_mock
from galaxy.managers.context import RequestIdentity
from galaxy.managers.users import UserManager
from galaxy.webapps.base.api import add_request_id_middleware
from galaxy.webapps.galaxy.api import (
    DependsOnTrans,
    get_actor_user,
    get_api_user,
    get_auth_session_from_bearer_token,
    get_auth_session_from_refresh_cookie,
    get_auth_source,
    get_effective_api_user,
    get_user,
)
from galaxy.work.context import WorkRequestContext


def _make_galaxy_access_token(app, user):
    auth_session = app.auth_session_manager.create_session(user=user, auth_source="galaxy_token")
    access_token = app.auth_session_manager.mint_access_token(auth_session, scopes=["api:*"])
    return auth_session, access_token


def _build_auth_context_app():
    app = FastAPI()
    add_request_id_middleware(app)
    router = APIRouter()

    @router.get("/api/test/auth-context")
    def auth_context(trans=DependsOnTrans):
        return {
            "auth_session_id": trans.auth_session.id if trans.auth_session else None,
            "auth_source": trans.auth_source,
            "actor_user_id": trans.actor_user.id if trans.actor_user else None,
            "user_id": trans.user.id if trans.user else None,
        }

    app.include_router(router)
    return app


def test_work_request_context_defaults_actor_user_to_effective_user():
    app = galaxy_mock.MockApp()
    user_manager = app[UserManager]
    user = user_manager.create(email="user1@example.org", username="user1", password="password")
    trans = WorkRequestContext(app=app, user=user)

    assert trans.actor_user == user
    assert trans.request_identity == RequestIdentity(
        user=user,
        actor_user=user,
        auth_session=None,
        galaxy_session=None,
        history=None,
        auth_source="api",
    )
    assert trans.async_request_user.user_id == user.id
    assert trans.async_request_user.actor_user_id == user.id
    assert trans.async_request_user.auth_session_id is None


def test_work_request_context_serializes_distinct_actor_user():
    app = galaxy_mock.MockApp()
    user_manager = app[UserManager]
    actor_user = user_manager.create(email="admin@example.org", username="admin", password="password")
    target_user = user_manager.create(email="target@example.org", username="target", password="password")
    trans = WorkRequestContext(app=app, user=target_user, actor_user=actor_user)

    assert trans.actor_user == actor_user
    assert trans.request_identity.actor_user == actor_user
    assert trans.request_identity.user == target_user
    assert trans.async_request_user.user_id == target_user.id
    assert trans.async_request_user.actor_user_id == actor_user.id
    assert trans.async_request_user.auth_session_id is None


def test_work_request_context_uses_auth_session_user():
    app = galaxy_mock.MockApp()
    user_manager = app[UserManager]
    user = user_manager.create(email="user2@example.org", username="user2", password="password")
    auth_session = app.auth_session_manager.create_session(user=user, auth_source="galaxy_token")
    trans = WorkRequestContext(app=app, auth_session=auth_session, auth_source="galaxy_token")

    assert trans.get_user() == user
    assert trans.request_identity.auth_session == auth_session
    assert trans.request_identity.auth_source == "galaxy_token"
    assert trans.async_request_user.user_id == user.id
    assert trans.async_request_user.auth_session_id == auth_session.id


def test_effective_api_user_preserves_actor_user_for_run_as():
    app = galaxy_mock.MockApp()
    user_manager = app[UserManager]
    actor_user = user_manager.create(email="admin@example.org", username="admin", password="password")
    target_user = user_manager.create(email="target@example.org", username="target", password="password")
    app.config.api_allow_run_as = actor_user.email

    effective_user = get_effective_api_user(user_manager=user_manager, api_actor_user=actor_user, run_as=target_user.id)
    resolved_actor_user = get_actor_user(
        bearer_auth_session=None,
        cookie_auth_session=None,
        api_actor_user=actor_user,
        effective_user=effective_user,
    )

    assert effective_user == target_user
    assert resolved_actor_user == actor_user


def test_galaxy_bearer_token_resolves_auth_session():
    app = galaxy_mock.MockApp()
    user_manager = app[UserManager]
    user = user_manager.create(email="user1@example.org", username="user1", password="password")
    auth_session, access_token = _make_galaxy_access_token(app, user)

    resolved_auth_session = get_auth_session_from_bearer_token(
        auth_session_manager=app.auth_session_manager,
        bearer_token=HTTPAuthorizationCredentials(scheme="Bearer", credentials=access_token),
    )

    assert resolved_auth_session is not None
    assert resolved_auth_session.id == auth_session.id
    assert resolved_auth_session.user == user


def test_galaxy_access_token_is_accepted_by_normal_api_user_resolution():
    app = galaxy_mock.MockApp()
    user_manager = app[UserManager]
    user = user_manager.create(email="user1@example.org", username="user1", password="password")
    auth_session, access_token = _make_galaxy_access_token(app, user)

    resolved_user = get_user(
        bearer_auth_session=auth_session,
        cookie_auth_session=None,
        api_user=None,
    )

    assert resolved_user == user


def test_galaxy_access_token_builds_auth_context_on_real_fastapi_request(monkeypatch, tmp_path):
    db_path = tmp_path / "galaxy.sqlite"
    config = galaxy_mock.MockAppConfig(root=str(tmp_path), database_connection=f"sqlite:///{db_path}")
    mock_app = galaxy_mock.MockApp(config=config)
    user_manager = mock_app[UserManager]
    user = user_manager.create(email="user1@example.org", username="user1", password="password")
    auth_session, access_token = _make_galaxy_access_token(mock_app, user)
    mock_app.model.session.commit()
    monkeypatch.setattr(galaxy_app_module, "app", mock_app)
    test_app = _build_auth_context_app()

    with TestClient(test_app) as client:
        response = client.get(
            "/api/test/auth-context",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "auth_session_id": auth_session.id,
        "auth_source": "galaxy_token",
        "actor_user_id": user.id,
        "user_id": user.id,
    }


def test_invalid_galaxy_bearer_token_does_not_fall_through_to_external_oidc():
    app = galaxy_mock.MockApp()
    user_manager = app[UserManager]
    user = user_manager.create(email="user1@example.org", username="user1", password="password")
    _, access_token = _make_galaxy_access_token(app, user)
    invalid_access_token = f"{access_token.rsplit('.', 1)[0]}.invalidsignature"

    with pytest.raises(exceptions.AuthenticationFailed):
        get_auth_session_from_bearer_token(
            auth_session_manager=app.auth_session_manager,
            bearer_token=HTTPAuthorizationCredentials(scheme="Bearer", credentials=invalid_access_token),
        )


def test_refresh_cookie_resolves_auth_session():
    app = galaxy_mock.MockApp()
    user_manager = app[UserManager]
    user = user_manager.create(email="user1@example.org", username="user1", password="password")
    auth_session = app.auth_session_manager.create_session(user=user, auth_source="galaxy_token")
    refresh_token = app.auth_session_manager.issue_refresh_token(auth_session)

    resolved_auth_session = get_auth_session_from_refresh_cookie(
        auth_session_manager=app.auth_session_manager,
        refresh_token=refresh_token,
    )

    assert resolved_auth_session is not None
    assert resolved_auth_session.id == auth_session.id
    assert resolved_auth_session.user == user


def test_expired_refresh_cookie_does_not_resolve_auth_session():
    app = galaxy_mock.MockApp()
    user_manager = app[UserManager]
    user = user_manager.create(email="user1@example.org", username="user1", password="password")
    auth_session = app.auth_session_manager.create_session(user=user, auth_source="galaxy_token")
    refresh_token = app.auth_session_manager.issue_refresh_token(auth_session, expires_in=timedelta(seconds=0))

    resolved_auth_session = get_auth_session_from_refresh_cookie(
        auth_session_manager=app.auth_session_manager,
        refresh_token=refresh_token,
    )

    assert resolved_auth_session is None


def test_external_oidc_bearer_token_still_resolves_via_oidc_path(monkeypatch):
    app = galaxy_mock.MockApp()
    user_manager = app[UserManager]
    user = user_manager.create(email="user1@example.org", username="user1", password="password")
    monkeypatch.setattr(user_manager, "by_oidc_access_token", lambda access_token: user)

    resolved_user = get_api_user(
        user_manager=user_manager,
        bearer_auth_session=None,
        key=None,
        x_api_key=None,
        bearer_token=HTTPAuthorizationCredentials(scheme="Bearer", credentials="opaque-external-token"),
    )

    assert resolved_user == user


def test_auth_source_prefers_galaxy_token():
    app = galaxy_mock.MockApp()
    user_manager = app[UserManager]
    user = user_manager.create(email="user1@example.org", username="user1", password="password")
    auth_session, _ = _make_galaxy_access_token(app, user)

    auth_source = get_auth_source(
        key=None,
        x_api_key=None,
        bearer_auth_session=auth_session,
        cookie_auth_session=None,
        api_user=None,
    )

    assert auth_source == "galaxy_token"
