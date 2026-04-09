from unittest.mock import MagicMock, patch

from galaxy.app_unittest_utils import galaxy_mock
from galaxy.managers.users import UserManager
from galaxy.util.unittest import TestCase
from galaxy.webapps.galaxy.controllers.authnz import (
    LOGIN_NEXT_COOKIE_NAME,
    OIDC,
    PROVIDER_COOKIE_NAME,
)


class TestOIDCController(TestCase):
    def setUp(self):
        self.trans = galaxy_mock.MockTrans(enable_oidc=True)
        self.trans.response.send_redirect = MagicMock(side_effect=lambda url: url)
        self.trans.set_cookie = MagicMock()
        self.trans.get_cookie = MagicMock(return_value=None)
        self.trans.url_builder = MagicMock(side_effect=lambda path, **kwargs: f"{path}?redirect={kwargs['redirect']}")
        self.app = self.trans.app
        self.app.authnz_manager = MagicMock()
        self.user_manager = self.app[UserManager]
        self.user = self.user_manager.create(email="user@example.org", username="user", password="password")

    def test_callback_issues_browser_auth_state_and_redirects_to_callback_route(self):
        self.app.authnz_manager.callback.return_value = (True, "", ("/tools?foo=1", self.user))
        controller = OIDC(self.app)

        with patch("galaxy.webapps.galaxy.controllers.authnz.auth_api.issue_browser_auth_for_user") as mock_issue:
            result = controller.callback(self.trans, "oidc", code="code", state="state")

        mock_issue.assert_called_once_with(self.trans, self.user)
        self.trans.set_cookie.assert_any_call(value="oidc", name=PROVIDER_COOKIE_NAME)
        self.trans.set_cookie.assert_any_call(value="/", name=LOGIN_NEXT_COOKIE_NAME)
        self.trans.url_builder.assert_called_once_with("/login/callback", redirect="%2Ftools%3Ffoo%3D1")
        assert result == "/login/callback?redirect=%2Ftools%3Ffoo%3D1"
