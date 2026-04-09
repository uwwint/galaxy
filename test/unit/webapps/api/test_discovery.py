from galaxy.app_unittest_utils import galaxy_mock
from galaxy.webapps.galaxy.api.discovery import (
    jwks,
    oauth_authorization_server_metadata,
)


def test_oauth_authorization_server_metadata():
    app = galaxy_mock.MockApp()

    metadata = oauth_authorization_server_metadata(app=app)

    assert metadata.issuer
    assert metadata.jwks_uri == f"{metadata.issuer}/.well-known/jwks.json"


def test_jwks_route_payload():
    app = galaxy_mock.MockApp()

    payload = jwks(app=app)

    assert len(payload.keys) == 1
    key = payload.keys[0]
    assert key["kty"] == "RSA"
    assert key["use"] == "sig"
    assert key["alg"] == "RS256"
    assert key["kid"]
