from requests import post

from ._framework import ApiTestCase

TEST_USER_EMAIL = "auth_user_test@bx.psu.edu"
TEST_USER_PASSWORD = "testpassword1"


class TestCurrentHistoryApi(ApiTestCase):
    def test_current_history_round_trip(self):
        self._setup_user(TEST_USER_EMAIL, TEST_USER_PASSWORD)
        login_response = post(
            urljoin(self.url, "auth/login"),
            json={"login": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD},
        )
        login_response.raise_for_status()
        access_token = login_response.json()["access_token"]

        current_history_response = self._get(
            "histories/current",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self._assert_status_code_is(current_history_response, 200)
        current_history = current_history_response.json()
        assert current_history["id"]

        create_response = self._post(
            "histories",
            data={"name": "frontend current history test"},
            json=True,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self._assert_status_code_is(create_response, 200)
        new_history = create_response.json()
        assert new_history["id"]

        set_current_response = self._put(
            f"histories/current/{new_history['id']}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self._assert_status_code_is(set_current_response, 200)
        assert set_current_response.json()["id"] == new_history["id"]

        updated_current_history_response = self._get(
            "histories/current",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self._assert_status_code_is(updated_current_history_response, 200)
        assert updated_current_history_response.json()["id"] == new_history["id"]
