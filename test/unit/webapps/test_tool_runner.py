from galaxy.app_unittest_utils import galaxy_mock
from galaxy.managers.auth_sessions import (
    TOOL_RUNNER_TOKEN_COOKIE_NAME,
    TOOL_RUNNER_TOKEN_COOKIE_PATH,
)
from galaxy.util.unittest import TestCase
from galaxy.webapps.galaxy.controllers.tool_runner import (
    _resolve_tool_runner_auth_session,
    _set_tool_runner_token_cookie,
    _tool_runner_token_tool_ids,
)


class TestToolRunnerController(TestCase):
    def setUp(self):
        self.app = galaxy_mock.MockApp()
        self.user = self.app.user_manager.create(email="user@example.org", username="user", password="password")
        self.auth_session = self.app.auth_session_manager.create_session(user=self.user, auth_source="galaxy_token")
        self.trans = galaxy_mock.MockTrans(app=self.app, user=self.user)
        self.trans.get_cookie = lambda name: None

    def test_tool_runner_token_cookie_is_path_scoped(self):
        _set_tool_runner_token_cookie(self.trans, "tool-runner-token")

        cookie = self.trans.response.cookies[TOOL_RUNNER_TOKEN_COOKIE_NAME]
        assert cookie.value == "tool-runner-token"
        assert cookie["path"] == TOOL_RUNNER_TOKEN_COOKIE_PATH
        assert cookie["httponly"]
        assert cookie["samesite"] == "None"

    def test_tool_runner_token_scopes_accumulate(self):
        token = self.app.auth_session_manager.mint_tool_runner_token(self.auth_session, tool_ids=["biomart", "ucsc"])
        self.trans.get_cookie = lambda name: token if name == TOOL_RUNNER_TOKEN_COOKIE_NAME else None

        tool_ids = _tool_runner_token_tool_ids(self.trans, "intermine")

        assert tool_ids == {"biomart", "intermine", "ucsc"}

    def test_tool_runner_auth_session_resolves_from_cookie(self):
        token = self.app.auth_session_manager.mint_tool_runner_token(self.auth_session, tool_ids=["biomart"])
        self.trans.get_cookie = lambda name: token if name == TOOL_RUNNER_TOKEN_COOKIE_NAME else None

        resolved_auth_session = _resolve_tool_runner_auth_session(self.trans, "biomart")

        assert resolved_auth_session is not None
        assert resolved_auth_session.id == self.auth_session.id
