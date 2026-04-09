from urllib.parse import urljoin

from requests import get

from galaxy_test.base.api_util import baseauth_headers
from galaxy_test.base.decorators import requires_new_user
from galaxy_test.base.populators import skip_without_tool
from ._framework import ApiTestCase

TEST_USER_EMAIL = "auth_user_test@bx.psu.edu"
TEST_USER_PASSWORD = "testpassword1"


class TestAuthenticateApi(ApiTestCase):
    @requires_new_user
    def test_auth(self):
        self._setup_user(TEST_USER_EMAIL, TEST_USER_PASSWORD)
        baseauth_url = self._api_url("authenticate/baseauth", use_key=False)
        headers = baseauth_headers(TEST_USER_EMAIL, TEST_USER_PASSWORD)
        auth_response = get(baseauth_url, headers=headers)
        self._assert_status_code_is(auth_response, 200)
        auth_dict = auth_response.json()
        self._assert_has_keys(auth_dict, "api_key")

        # Verify key...
        random_api_url = self._api_url("users", use_key=False)
        random_api_response = get(random_api_url, params=dict(key=auth_dict["api_key"]))
        self._assert_status_code_is(random_api_response, 200)

    @skip_without_tool("test_data_source")
    def test_tool_runner_session_cookie_handling(self):
        response = get(self.url)
        assert "galaxy_refresh_token" in response.cookies
        response = get(
            urljoin(self.url, "auth/tool_runner?tool_id=test_data_source"),
            cookies=response.cookies,
            allow_redirects=False,
        )
        assert "galaxy_tool_runner_token" in response.cookies
        assert response.headers["Location"].endswith("/tool_runner/data_source_redirect?tool_id=test_data_source")
        tool_runner_response = get(
            urljoin(self.url, "tool_runner/data_source_redirect?tool_id=test_data_source"),
            cookies=response.cookies,
            allow_redirects=False,
        )
        tool_runner_response.raise_for_status()
        assert tool_runner_response.status_code in (302, 307)
        assert "galaxy_tool_runner_token" in tool_runner_response.cookies
        assert tool_runner_response.headers["Location"].startswith("http")

    def test_anon_history_creation(self):
        # First request:
        # We don't create any histories, just return a session cookie
        response = get(self.url)
        cookie = {"galaxysession": response.cookies["galaxysession"]}
        # Check that we don't have any histories (API doesn't auto-create new histories)
        histories_response = get(
            urljoin(
                self.url,
                "api/histories",
            )
        )
        assert not histories_response.json()
        # Second request, we know client follows conventions by including cookies,
        # default history is created.
        get(self.url, cookies=cookie)
        second_histories_response = get(
            urljoin(self.url, "history/current_history_json"),
            cookies=cookie,
        )
        assert second_histories_response.json()
