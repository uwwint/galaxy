import pytest

from galaxy import model


@pytest.fixture(scope="module")
def init_model(engine):
    model.mapper_registry.metadata.create_all(engine)


def test_auth_session_defaults(make_user):
    user = make_user()
    auth_session = model.AuthSession(user=user, is_valid=True)

    assert auth_session.session_type == "browser"
    assert auth_session.auth_source == "anonymous"
    assert auth_session.user == user
    assert auth_session.is_valid is True
    assert auth_session.last_activity is not None


def test_auth_session_impersonation_metadata(make_user):
    user = make_user()
    impersonator = make_user()

    auth_session = model.AuthSession(
        user=user,
        impersonator_user=impersonator,
        impersonation_started_at=model.now(),
        is_valid=True,
    )

    assert auth_session.user == user
    assert auth_session.impersonator_user == impersonator
    assert auth_session.impersonation_started_at is not None
