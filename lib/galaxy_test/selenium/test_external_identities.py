from urllib.parse import quote

from .framework import (
    SeleniumTestCase,
    selenium_test,
)


class TestExternalIdentities(SeleniumTestCase):
    @selenium_test
    def test_external_identities_shows_duplicate_provider_message(self):
        email = self._get_random_email()
        self.register(email)
        self.logout_if_needed()

        self.home()
        self.submit_login(email, assert_valid=True)

        message = quote(
            "This Galaxy account already has a linked Keycloak identity. "
            "Disconnect it before linking another identity from the same provider."
        )
        self.navigate_to(self.build_url(f"user/external_ids?message={message}&status=danger"))

        self.assert_error_message(contains="already has a linked Keycloak identity")
