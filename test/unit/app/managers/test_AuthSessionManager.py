from datetime import timedelta

import pytest

from galaxy import (
    exceptions,
    model,
)
from galaxy.managers.auth_sessions import (
    AuthSessionManager,
    DEFAULT_ACCESS_TOKEN_LIFETIME,
)
from .base import BaseTestCase


class TestAuthSessionManager(BaseTestCase):
    def set_up_managers(self):
        super().set_up_managers()
        self.auth_session_manager: AuthSessionManager = self.app.auth_session_manager

    def test_create_session(self):
        history = model.History(user=self.admin_user)
        self.trans.sa_session.add(history)
        self.trans.sa_session.flush()

        auth_session = self.auth_session_manager.create_session(
            auth_source="galaxy_token",
            user=self.admin_user,
            current_history=history,
            remote_addr="127.0.0.1",
        )

        assert auth_session.id is not None
        assert auth_session.user_id == self.admin_user.id
        assert auth_session.current_history_id == history.id
        assert auth_session.session_type == "browser"
        assert auth_session.auth_source == "galaxy_token"
        assert auth_session.is_valid is True
        assert auth_session.last_activity is not None

    def test_refresh_token_rotation_invalidates_old_value(self):
        auth_session = self.auth_session_manager.create_session(user=self.admin_user, auth_source="session")
        refresh_token = self.auth_session_manager.issue_refresh_token(auth_session)

        resolved_session = self.auth_session_manager.get_session_for_refresh_token(refresh_token)
        assert resolved_session.id == auth_session.id

        rotated_refresh_token = self.auth_session_manager.issue_refresh_token(auth_session)
        assert rotated_refresh_token != refresh_token

        with pytest.raises(exceptions.AuthenticationFailed):
            self.auth_session_manager.get_session_for_refresh_token(refresh_token)

        rotated_session = self.auth_session_manager.get_session_for_refresh_token(rotated_refresh_token)
        assert rotated_session.id == auth_session.id

    def test_invalidate_other_sessions_for_user(self):
        current_session = self.auth_session_manager.create_session(user=self.admin_user, auth_source="session")
        other_session = self.auth_session_manager.create_session(user=self.admin_user, auth_source="session")
        self.auth_session_manager.issue_refresh_token(current_session)
        other_refresh_token = self.auth_session_manager.issue_refresh_token(other_session)

        invalidated_count = self.auth_session_manager.invalidate_sessions_for_user(
            self.admin_user, exclude_auth_session_id=current_session.id
        )

        assert invalidated_count == 1
        assert (
            self.auth_session_manager.get_session_for_refresh_token(
                self.auth_session_manager.issue_refresh_token(current_session)
            ).id
            == current_session.id
        )
        with pytest.raises(exceptions.AuthenticationFailed):
            self.auth_session_manager.get_session_for_refresh_token(other_refresh_token)

    def test_access_token_round_trip(self):
        auth_session = self.auth_session_manager.create_session(user=self.admin_user, auth_source="session")
        access_token = self.auth_session_manager.mint_access_token(
            auth_session, scopes=["api:*"], expires_in=DEFAULT_ACCESS_TOKEN_LIFETIME
        )

        payload = self.auth_session_manager.decode_access_token(access_token, required_scopes=["api:*"])

        assert payload["sid"] == str(auth_session.id)
        assert payload["user_id"] == str(self.admin_user.id)
        assert "api:*" in payload["scope"].split()

    def test_tool_runner_token_requires_matching_scope(self):
        auth_session = self.auth_session_manager.create_session(user=self.admin_user, auth_source="session")
        access_token = self.auth_session_manager.mint_tool_runner_token(auth_session, tool_ids=["biomart", "ucsc"])

        payload = self.auth_session_manager.decode_access_token(access_token, required_scopes=["tool_runner:biomart"])
        assert set(payload["scope"].split()) == {"tool_runner:biomart", "tool_runner:ucsc"}

        with pytest.raises(exceptions.AuthenticationFailed):
            self.auth_session_manager.decode_access_token(access_token, required_scopes=["tool_runner:intermine"])

    def test_refresh_token_expiry_is_enforced(self):
        auth_session = self.auth_session_manager.create_session(user=self.admin_user, auth_source="session")
        refresh_token = self.auth_session_manager.issue_refresh_token(auth_session, expires_in=timedelta(seconds=0))

        with pytest.raises(exceptions.AuthenticationFailed):
            self.auth_session_manager.get_session_for_refresh_token(refresh_token)
