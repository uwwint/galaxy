from typing import Any

from galaxy.managers.auth_sessions import AuthSessionManager
from galaxy.schema.schema import Model
from galaxy.structured_app import StructuredApp
from galaxy.webapps.galaxy.api import (
    DependsOnApp,
    Router,
)

router = Router(tags=["discovery"])


class OAuthAuthorizationServerMetadata(Model):
    issuer: str
    jwks_uri: str


class JsonWebKeySet(Model):
    keys: list[dict[str, Any]]


@router.get(
    "/.well-known/oauth-authorization-server",
    public=True,
    summary="Return Galaxy issuer metadata for validating Galaxy-issued JWTs",
)
def oauth_authorization_server_metadata(app: StructuredApp = DependsOnApp) -> OAuthAuthorizationServerMetadata:
    auth_session_manager: AuthSessionManager = app.auth_session_manager
    return OAuthAuthorizationServerMetadata(**auth_session_manager.get_authorization_server_metadata())


@router.get(
    "/.well-known/jwks.json",
    public=True,
    summary="Return the Galaxy JWT verification keys",
)
def jwks(app: StructuredApp = DependsOnApp) -> JsonWebKeySet:
    auth_session_manager: AuthSessionManager = app.auth_session_manager
    return JsonWebKeySet(**auth_session_manager.get_jwks())
