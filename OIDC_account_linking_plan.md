# OIDC Account Linking Plan

## Goal
Refine Galaxy's OIDC account-linking behavior so it is safe and predictable when local accounts are disabled and when a user already has an identity linked for the same provider.

## Working Assumptions
- Galaxy should continue to support multiple external providers on one account.
- Galaxy should default to a single identity per provider per Galaxy user.
- If local accounts are disabled and there is only one OIDC provider, the UX should favor signing in as that identity instead of silently linking onto a pre-existing session.

## Plan

1. Update the backend policy
   - Add a typed helper on `User` to detect whether a provider is already linked.
   - Guard the OIDC association pipeline so a second identity from the same provider cannot be linked onto the same Galaxy account.
   - Return a user-facing redirect or message when the same-provider relink is rejected.

2. Reflect the rule in the UI
   - Hide providers the current user has already linked on the external identities page.
   - Show a clear warning when the backend rejects a same-provider relink attempt.
   - Keep the normal login flow unchanged for first-time sign-ins.

3. Update documentation
   - Document the rule in the OIDC authentication docs.
   - Clarify that Galaxy supports many providers per account, but not multiple identities from the same provider by default.

4. Add tests
   - Add unit tests for the provider-linking guard.
   - Add integration tests proving a second identity from the same IdP is rejected.
   - Add browser-facing tests for the external identities page and the login/linking UX under the Playwright backend.

5. Verify
   - Run the targeted auth and UI test slices.
   - Fix any formatting or typing issues so the code stays consistent with Galaxy's style.
