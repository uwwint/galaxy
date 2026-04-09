from galaxy.app_unittest_utils import galaxy_mock
from galaxy.managers.context import RequestIdentity
from galaxy.managers.users import UserManager
from galaxy.webapps.galaxy.api import (
    get_actor_user,
    get_effective_api_user,
)
from galaxy.work.context import WorkRequestContext


def test_work_request_context_defaults_actor_user_to_effective_user():
    app = galaxy_mock.MockApp()
    user_manager = app[UserManager]
    user = user_manager.create(email="user1@example.org", username="user1", password="password")
    trans = WorkRequestContext(app=app, user=user)

    assert trans.actor_user == user
    assert trans.request_identity == RequestIdentity(
        user=user,
        actor_user=user,
        galaxy_session=None,
        history=None,
        auth_source="api",
    )
    assert trans.async_request_user.user_id == user.id
    assert trans.async_request_user.actor_user_id == user.id


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


def test_effective_api_user_preserves_actor_user_for_run_as():
    app = galaxy_mock.MockApp()
    user_manager = app[UserManager]
    actor_user = user_manager.create(email="admin@example.org", username="admin", password="password")
    target_user = user_manager.create(email="target@example.org", username="target", password="password")
    app.config.api_allow_run_as = actor_user.email

    effective_user = get_effective_api_user(user_manager=user_manager, api_user=actor_user, run_as=target_user.id)
    resolved_actor_user = get_actor_user(galaxy_session=None, api_actor_user=actor_user, effective_user=effective_user)

    assert effective_user == target_user
    assert resolved_actor_user == actor_user
