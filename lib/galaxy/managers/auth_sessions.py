import hashlib
import json
import logging
import secrets
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from functools import cached_property
from typing import (
    Any,
    Optional,
)

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import (
    RSAPrivateKey,
    RSAPublicKey,
)
from jwt.algorithms import RSAAlgorithm
from sqlalchemy import (
    select,
    true,
)
from sqlalchemy.orm import joinedload

from galaxy import exceptions
from galaxy.model import (
    AuthSession,
    History,
    User,
)
from galaxy.structured_app import MinimalManagerApp

DEFAULT_ACCESS_TOKEN_LIFETIME = timedelta(minutes=20)
DEFAULT_REFRESH_TOKEN_LIFETIME = timedelta(days=30)
DEFAULT_TOOL_RUNNER_TOKEN_LIFETIME = timedelta(hours=1)
REFRESH_TOKEN_KIND = "auth_refresh"
AUTH_SESSION_COOKIE_NAME = "galaxy_refresh_token"
AUTH_SESSION_CSRF_COOKIE_NAME = "galaxy_refresh_csrf_token"
AUTH_SESSION_COOKIE_PATH = "/auth"
TOOL_RUNNER_TOKEN_COOKIE_NAME = "galaxy_tool_runner_token"
TOOL_RUNNER_TOKEN_COOKIE_PATH = "/tool_runner"

log = logging.getLogger(__name__)
JWT_SIGNING_ALGORITHM = "RS256"
JWT_SIGNING_PRIVATE_KEY_FILE_OPTION = "galaxy_jwt_signing_private_key_file"


def _utcnow() -> datetime:
    return datetime.utcnow()


@dataclass(frozen=True)
class GalaxyJwtKeyPair:
    private_key: RSAPrivateKey
    public_key: RSAPublicKey
    kid: str
    jwk: dict[str, Any]


class AuthSessionManager:
    """Manage persisted auth-session rows and Galaxy-issued browser tokens."""

    def __init__(self, app: MinimalManagerApp):
        self.app = app
        self.model = app.model
        self.sa_session = app.model.context
        self.security = app.security

    def create_session(
        self,
        *,
        session_type: str = "browser",
        auth_source: str = "anonymous",
        user: Optional[User] = None,
        current_history: Optional[History] = None,
        impersonator_user: Optional[User] = None,
        remote_host: Optional[str] = None,
        remote_addr: Optional[str] = None,
        referer: Optional[str] = None,
    ) -> AuthSession:
        auth_session = self.model.AuthSession(
            session_type=session_type,
            auth_source=auth_source,
            user_id=user.id if user is not None else None,
            current_history_id=current_history.id if current_history is not None else None,
            impersonator_user_id=impersonator_user.id if impersonator_user is not None else None,
            impersonation_started_at=_utcnow() if impersonator_user else None,
            remote_host=remote_host,
            remote_addr=remote_addr,
            referer=referer,
            is_valid=True,
        )
        self.sa_session.add(auth_session)
        self.sa_session.flush()
        return auth_session

    def issue_refresh_token(
        self,
        auth_session: AuthSession,
        *,
        expires_in: timedelta = DEFAULT_REFRESH_TOKEN_LIFETIME,
    ) -> str:
        auth_session = self._attach_auth_session(auth_session)
        now = _utcnow()
        secret = self.security.get_new_guid()
        session_id = self.security.encode_id(auth_session.id, kind=REFRESH_TOKEN_KIND)
        refresh_token = f"{session_id}.{secret}"
        auth_session.refresh_token_hash = self._hash_token(refresh_token)
        auth_session.refresh_token_iat = now
        auth_session.refresh_token_expires_at = now + expires_in
        auth_session.last_activity = now
        auth_session.is_valid = True
        self.sa_session.add(auth_session)
        return refresh_token

    def get_session_for_refresh_token(self, refresh_token: str) -> AuthSession:
        auth_session = self._session_from_refresh_token(refresh_token)
        expected_hash = auth_session.refresh_token_hash
        if not expected_hash:
            raise exceptions.AuthenticationFailed("Refresh token is not available for this session.")
        if not secrets.compare_digest(expected_hash, self._hash_token(refresh_token)):
            raise exceptions.AuthenticationFailed("Invalid refresh token.")
        if not auth_session.is_valid:
            raise exceptions.AuthenticationFailed("Session is invalid.")
        if auth_session.refresh_token_expires_at and auth_session.refresh_token_expires_at <= _utcnow():
            raise exceptions.AuthenticationFailed("Refresh token has expired.")
        auth_session.last_activity = _utcnow()
        self.sa_session.add(auth_session)
        return auth_session

    def get_session_by_id(self, auth_session_id: int) -> Optional[AuthSession]:
        stmt = (
            select(self.model.AuthSession)
            .where(self.model.AuthSession.id == auth_session_id)
            .where(self.model.AuthSession.is_valid == true())
            .options(
                joinedload(self.model.AuthSession.user),
                joinedload(self.model.AuthSession.current_history),
            )
            .limit(1)
        )
        return self.sa_session.scalars(stmt).first()

    def invalidate_session(self, auth_session: AuthSession) -> None:
        auth_session = self._attach_auth_session(auth_session)
        auth_session.is_valid = False
        auth_session.refresh_token_hash = None
        auth_session.refresh_token_iat = None
        auth_session.refresh_token_expires_at = None
        self.sa_session.add(auth_session)
        log.debug("Invalidated auth session %s", auth_session.id)

    def invalidate_sessions_for_user(self, user: User, *, exclude_auth_session_id: Optional[int] = None) -> int:
        stmt = select(self.model.AuthSession).where(self.model.AuthSession.user_id == user.id)
        if exclude_auth_session_id is not None:
            stmt = stmt.where(self.model.AuthSession.id != exclude_auth_session_id)
        sessions = list(self.sa_session.scalars(stmt))
        for auth_session in sessions:
            self.invalidate_session(auth_session)
        return len(sessions)

    def mint_access_token(
        self,
        auth_session: AuthSession,
        *,
        scopes: Optional[Iterable[str]] = None,
        expires_in: timedelta = DEFAULT_ACCESS_TOKEN_LIFETIME,
    ) -> str:
        return self._mint_jwt(auth_session, scopes=scopes, expires_in=expires_in)

    def mint_tool_runner_token(
        self,
        auth_session: AuthSession,
        *,
        tool_ids: Iterable[str],
        expires_in: timedelta = DEFAULT_TOOL_RUNNER_TOKEN_LIFETIME,
    ) -> str:
        scopes = [f"tool_runner:{tool_id}" for tool_id in tool_ids]
        return self._mint_jwt(auth_session, scopes=scopes, expires_in=expires_in)

    def decode_access_token(self, access_token: str, *, required_scopes: Optional[Iterable[str]] = None) -> dict:
        try:
            payload = jwt.decode(
                access_token,
                key=self._jwt_key_pair.public_key,
                algorithms=[JWT_SIGNING_ALGORITHM],
                audience=self._token_audience(),
                issuer=self._token_issuer(),
            )
        except jwt.PyJWTError as exc:
            raise exceptions.AuthenticationFailed("Invalid Galaxy access token.") from exc
        if required_scopes:
            token_scopes = set((payload.get("scope") or "").split())
            missing_scopes = [scope for scope in required_scopes if scope not in token_scopes]
            if missing_scopes:
                raise exceptions.AuthenticationFailed(
                    f"Galaxy access token is missing required scopes: {', '.join(missing_scopes)}."
                )
        return payload

    def get_access_token_scopes(self, access_token: str) -> set[str]:
        payload = self.decode_access_token(access_token)
        return set((payload.get("scope") or "").split())

    def is_galaxy_access_token(self, access_token: str) -> bool:
        """Return True if the token is one of Galaxy's own browser/access JWTs.

        This intentionally does not verify the signature, expiry, audience, or issuer.
        The method is used only as a cheap classifier so request resolution can decide
        whether to use the Galaxy auth-session path or fall back to trusted external OIDC
        bearer-token handling. The real validation happens later in
        :meth:`decode_access_token` / :meth:`get_session_for_access_token`.
        """
        try:
            payload = jwt.decode(
                access_token,
                options={
                    "verify_signature": False,
                    "verify_exp": False,
                    "verify_iat": False,
                    "verify_aud": False,
                    "verify_iss": False,
                },
            )
        except jwt.PyJWTError:
            return False
        return payload.get("auth_source") == "galaxy_token"

    def get_session_for_access_token(
        self, access_token: str, *, required_scopes: Optional[Iterable[str]] = None
    ) -> AuthSession:
        payload = self.decode_access_token(access_token, required_scopes=required_scopes)
        try:
            auth_session_id = int(payload["sid"])
        except (KeyError, TypeError, ValueError) as exc:
            raise exceptions.AuthenticationFailed("Galaxy access token is missing a valid session binding.") from exc
        auth_session = self.get_session_by_id(auth_session_id)
        if auth_session is None:
            raise exceptions.AuthenticationFailed("Galaxy access token session was not found.")
        return auth_session

    def _mint_jwt(
        self,
        auth_session: AuthSession,
        *,
        scopes: Optional[Iterable[str]],
        expires_in: timedelta,
    ) -> str:
        now = datetime.now(timezone.utc)
        user = auth_session.user
        payload = {
            "iss": self._token_issuer(),
            "aud": self._token_audience(),
            "sub": self._subject(auth_session),
            "iat": int(now.timestamp()),
            "exp": int((now + expires_in).timestamp()),
            "sid": str(auth_session.id),
            "session_type": auth_session.session_type,
            "auth_source": auth_session.auth_source,
            "scope": " ".join(sorted(set(scopes or []))),
        }
        if user:
            payload["user_id"] = str(user.id)
            payload["email"] = user.email
            if user.username:
                payload["preferred_username"] = user.username
        return jwt.encode(
            payload,
            key=self._jwt_key_pair.private_key,
            algorithm=JWT_SIGNING_ALGORITHM,
            headers={"kid": self._jwt_key_pair.kid},
        )

    def _subject(self, auth_session: AuthSession) -> str:
        if auth_session.user_id is not None:
            return f"user:{auth_session.user_id}"
        return f"session:{auth_session.id}"

    def _token_issuer(self) -> str:
        issuer = self.app.config.galaxy_infrastructure_url or "galaxy"
        return issuer.rstrip("/") or "galaxy"

    def _token_audience(self) -> str:
        return self._token_issuer()

    def get_authorization_server_metadata(self) -> dict[str, str]:
        issuer = self._token_issuer()
        return {
            "issuer": issuer,
            "jwks_uri": f"{issuer}/.well-known/jwks.json",
        }

    def get_jwks(self) -> dict[str, list[dict[str, Any]]]:
        return {"keys": [self._jwt_key_pair.jwk]}

    @cached_property
    def _jwt_key_pair(self) -> GalaxyJwtKeyPair:
        private_key_file = self.app.config.get(JWT_SIGNING_PRIVATE_KEY_FILE_OPTION, None)
        if private_key_file:
            return self._load_jwt_key_pair_from_file(private_key_file)
        log.warning("Galaxy JWT signing private key is not configured; generating an ephemeral in-memory RSA keypair.")
        return self._generate_jwt_key_pair()

    def _session_from_refresh_token(self, refresh_token: str) -> AuthSession:
        try:
            encoded_id, _ = refresh_token.split(".", 1)
        except ValueError as exc:
            raise exceptions.AuthenticationFailed("Malformed refresh token.") from exc
        try:
            auth_session_id = self.security.decode_id(encoded_id, kind=REFRESH_TOKEN_KIND)
        except exceptions.MalformedId as exc:
            raise exceptions.AuthenticationFailed("Malformed refresh token.") from exc
        stmt = (
            select(self.model.AuthSession)
            .where(self.model.AuthSession.id == auth_session_id)
            .where(self.model.AuthSession.is_valid == true())
            .options(
                joinedload(self.model.AuthSession.user),
                joinedload(self.model.AuthSession.current_history),
            )
            .limit(1)
        )
        auth_session = self.sa_session.scalars(stmt).first()
        if auth_session is None:
            raise exceptions.AuthenticationFailed("Refresh token session was not found.")
        return auth_session

    def _attach_auth_session(self, auth_session: AuthSession) -> AuthSession:
        if auth_session.id is None:
            self.sa_session.add(auth_session)
            self.sa_session.flush()
            return auth_session
        managed_auth_session = self.get_session_by_id(auth_session.id)
        if managed_auth_session is None:
            managed_auth_session = self.sa_session.merge(auth_session)
            self.sa_session.flush()
        return managed_auth_session

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _load_jwt_key_pair_from_file(self, private_key_file: str) -> GalaxyJwtKeyPair:
        try:
            with open(private_key_file, "rb") as handle:
                private_key = serialization.load_pem_private_key(handle.read(), password=None)
        except OSError as exc:
            raise exceptions.ConfigurationError(
                f"Galaxy JWT signing private key file could not be read: {private_key_file}"
            ) from exc
        if not isinstance(private_key, RSAPrivateKey):
            raise exceptions.ConfigurationError(
                "Galaxy JWT signing private key must be an RSA private key in PEM format."
            )
        return self._build_jwt_key_pair(private_key)

    def _generate_jwt_key_pair(self) -> GalaxyJwtKeyPair:
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        return self._build_jwt_key_pair(private_key)

    def _build_jwt_key_pair(self, private_key: RSAPrivateKey) -> GalaxyJwtKeyPair:
        public_key = private_key.public_key()
        public_key_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        kid = hashlib.sha256(public_key_bytes).hexdigest()
        jwk = json.loads(RSAAlgorithm.to_jwk(public_key))
        jwk["alg"] = JWT_SIGNING_ALGORITHM
        jwk["kid"] = kid
        jwk["use"] = "sig"
        jwk.pop("key_ops", None)
        return GalaxyJwtKeyPair(
            private_key=private_key,
            public_key=public_key,
            kid=kid,
            jwk=jwk,
        )
