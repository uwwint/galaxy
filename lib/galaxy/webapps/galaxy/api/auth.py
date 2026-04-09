<<<<<<< HEAD
from collections.abc import Iterable
=======
>>>>>>> a577d90995 (Add auth login and registration endpoints)
from datetime import (
    datetime,
    timedelta,
)
<<<<<<< HEAD
from typing import (
    Any,
    Optional,
)

from fastapi import Body
from markupsafe import escape

from galaxy import util
from galaxy.exceptions import (
    AuthenticationFailed,
    Conflict,
)
from galaxy.managers.auth_sessions import AUTH_SESSION_COOKIE_NAME
from galaxy.managers.users import UserManager
from galaxy.model import (
    AuthSession,
    User,
)
from galaxy.security.validate_user_input import (
    validate_email,
    validate_publicname,
)
from galaxy.web import url_for
=======
from typing import Optional

from fastapi import Body

from galaxy.exceptions import AuthenticationFailed
from galaxy.managers.auth_sessions import AUTH_SESSION_COOKIE_NAME
from galaxy.managers.users import UserManager
>>>>>>> a577d90995 (Add auth login and registration endpoints)
from galaxy.webapps.galaxy.api import (
    DependsOnTrans,
    Router,
)
from galaxy.work.context import SessionRequestContext

router = Router(tags=["auth"])


def _cookie_path(trans: SessionRequestContext) -> str:
    return (trans.app.config.cookie_path or "/").rstrip("/") or "/"


def _cookie_domain(trans: SessionRequestContext) -> Optional[str]:
    return trans.app.config.cookie_domain


def _request_headers(trans: SessionRequestContext) -> Any:
    return trans.request.headers


def _request_remote_host(trans: SessionRequestContext) -> Optional[str]:
    return trans.request.remote_host


def _request_remote_addr(trans: SessionRequestContext) -> Optional[str]:
    return trans.request.remote_addr


def _set_refresh_cookie(trans: SessionRequestContext, refresh_token: str, expires_at: Optional[datetime]) -> None:
    response = trans.response
    max_age = 0
    if expires_at is not None:
        max_age = max(0, int((expires_at - datetime.utcnow()).total_seconds()))
    response.set_cookie(
        key=AUTH_SESSION_COOKIE_NAME,
        value=refresh_token,
        max_age=max_age,
        path=_cookie_path(trans),
        domain=_cookie_domain(trans),
        secure=trans.request.is_secure,
        httponly=True,
        samesite="lax",
    )


def _clear_refresh_cookie(trans: SessionRequestContext) -> None:
    response = trans.response
    response.set_cookie(
        key=AUTH_SESSION_COOKIE_NAME,
        value="",
        max_age=0,
        path=_cookie_path(trans),
        domain=_cookie_domain(trans),
        secure=trans.request.is_secure,
        httponly=True,
        samesite="lax",
    )


def _set_legacy_session_cookie(trans: SessionRequestContext, galaxy_session) -> None:
    response = trans.response
    response.set_cookie(
        key="galaxysession",
        value=trans.security.encode_guid(galaxy_session.session_key),
        max_age=3600 * 24 * 90,
        path=_cookie_path(trans),
        domain=_cookie_domain(trans),
        secure=trans.request.is_secure,
        httponly=True,
        samesite="lax",
    )


def _rotate_legacy_galaxy_session(trans: SessionRequestContext, *, logout_all: bool = False) -> None:
    galaxy_session = trans.galaxy_session
    if galaxy_session is None:
        return
    galaxy_session.is_valid = False
    new_galaxy_session = trans.app.model.GalaxySession(
        session_key=trans.security.get_new_guid(),
        is_valid=True,
        remote_host=_request_remote_host(trans),
        remote_addr=_request_remote_addr(trans),
        referer=_request_headers(trans).get("Referer", None),
        prev_session_id=galaxy_session.id,
    )
    trans.sa_session.add_all((galaxy_session, new_galaxy_session))
    if logout_all and galaxy_session.user_id is not None:
        stmt = trans.sa_session.query(trans.app.model.GalaxySession).filter(
            trans.app.model.GalaxySession.user_id == galaxy_session.user_id,
            trans.app.model.GalaxySession.is_valid.is_(True),
            trans.app.model.GalaxySession.id != galaxy_session.id,
        )
        for other_galaxy_session in stmt:
            other_galaxy_session.is_valid = False
            trans.sa_session.add(other_galaxy_session)
    trans.sa_session.commit()
    trans.galaxy_session = new_galaxy_session
    _set_legacy_session_cookie(trans, new_galaxy_session)


def _serialize_user(trans: SessionRequestContext, user: Optional[User]) -> Optional[dict[str, str]]:
    if user is None:
        return None
    return {
        "id": trans.security.encode_id(user.id),
        "email": user.email,
        "username": user.username,
    }


<<<<<<< HEAD
def _success_payload(
    trans: SessionRequestContext,
    access_token: str,
    *,
    message: str = "Success.",
    status: Optional[str] = None,
    redirect: Optional[str] = None,
) -> dict[str, Any]:
=======
def _success_payload(trans, access_token: str, *, message: str = "Success.", status: Optional[str] = None):
>>>>>>> a577d90995 (Add auth login and registration endpoints)
    payload = _bootstrap_payload(trans, access_token=access_token)
    payload["message"] = message
    if status is not None:
        payload["status"] = status
<<<<<<< HEAD
    if redirect is not None:
        payload["redirect"] = redirect
    return payload


def _error_payload(message: str, *, status: Optional[str] = None, **kwd: Any) -> dict[str, Any]:
=======
    return payload


def _error_payload(message: str, *, status: Optional[str] = None, **kwd):
>>>>>>> a577d90995 (Add auth login and registration endpoints)
    payload = {"err_msg": message}
    if status is not None:
        payload["status"] = status
    payload.update(kwd)
    return payload


<<<<<<< HEAD
def _bootstrap_payload(trans: SessionRequestContext, access_token: Optional[str]) -> dict[str, Any]:
=======
def _bootstrap_payload(trans, access_token: Optional[str]):
>>>>>>> a577d90995 (Add auth login and registration endpoints)
    history = trans.history
    return {
        "authenticated": trans.user is not None,
        "access_token": access_token,
        "auth_source": trans.auth_source,
        "user": _serialize_user(trans, trans.user),
        "actor_user": _serialize_user(trans, trans.actor_user),
        "current_history_id": trans.security.encode_id(history.id) if history else None,
    }


def _ensure_browser_auth_session(trans: SessionRequestContext) -> Optional[AuthSession]:
    current_auth_session = trans.auth_session
    if current_auth_session is not None:
        return current_auth_session
    if trans.user is None or trans.galaxy_session is None or trans.auth_source == "remote_user":
        return None
    auth_session = trans.app.auth_session_manager.create_session(
        user=trans.user,
        auth_source="galaxy_token",
        current_history=trans.history,
        remote_host=_request_remote_host(trans),
        remote_addr=_request_remote_addr(trans),
        referer=_request_headers(trans).get("Referer", None),
    )
    trans.auth_session = auth_session
    trans._auth_source = "galaxy_token"
    return auth_session


<<<<<<< HEAD
def _promote_browser_login_state(trans: SessionRequestContext, user: User) -> None:
=======
def _promote_browser_login_state(trans, user) -> None:
>>>>>>> a577d90995 (Add auth login and registration endpoints)
    trans.app.security_agent.create_user_role(user, trans.app)
    history = trans.history
    if history is not None:
        if history.user is None:
            history.user = user
            trans.app.security_agent.history_set_default_permissions(
                history, dataset=True, bypass_manage_permission=True
            )
        trans.sa_session.add(history)
    if trans.galaxy_session is not None:
        trans.galaxy_session.user = user
        if history is not None:
            trans.galaxy_session.current_history = history
            if history not in trans.galaxy_session.histories:
                trans.galaxy_session.add_history(history)
        trans.sa_session.add(trans.galaxy_session)
<<<<<<< HEAD
    trans.set_user_context(user)


def _issue_browser_auth_for_user(
    trans: SessionRequestContext,
    user: User,
    *,
    message: str = "Success.",
    status: Optional[str] = None,
    redirect: Optional[str] = None,
) -> dict[str, Any]:
    _promote_browser_login_state(trans, user)
    current_auth_session = trans.auth_session
    if current_auth_session is not None:
        trans.app.auth_session_manager.invalidate_session(current_auth_session)
=======
    trans._WorkRequestContext__user = user
    trans._actor_user = user


def _issue_browser_auth_for_user(trans, user, *, message: str = "Success.", status: Optional[str] = None):
    _promote_browser_login_state(trans, user)
    if trans.auth_session is not None:
        trans.app.auth_session_manager.invalidate_session(trans.auth_session)
>>>>>>> a577d90995 (Add auth login and registration endpoints)
    auth_session = trans.app.auth_session_manager.create_session(
        user=user,
        auth_source="galaxy_token",
        current_history=trans.history,
<<<<<<< HEAD
        remote_host=_request_remote_host(trans),
        remote_addr=_request_remote_addr(trans),
        referer=_request_headers(trans).get("Referer", None),
=======
        remote_host=trans.request.remote_host,
        remote_addr=trans.request.remote_addr,
        referer=trans.request.headers.get("Referer", None),
>>>>>>> a577d90995 (Add auth login and registration endpoints)
    )
    refresh_token = trans.app.auth_session_manager.issue_refresh_token(auth_session)
    trans.sa_session.commit()
    trans.auth_session = auth_session
    trans._auth_source = "galaxy_token"
    _set_refresh_cookie(trans, refresh_token, auth_session.refresh_token_expires_at)
    access_token = trans.app.auth_session_manager.mint_access_token(auth_session, scopes=["api:*"])
<<<<<<< HEAD
    return _success_payload(trans, access_token, message=message, status=status, redirect=redirect)


def _is_outside_grace_period(trans: SessionRequestContext, create_time: datetime) -> bool:
    activation_grace_period = trans.app.config.activation_grace_period
    delta = timedelta(hours=int(activation_grace_period))
    time_difference = datetime.utcnow() - create_time
    return time_difference > delta or activation_grace_period == 0


def _resend_activation_email(trans: SessionRequestContext, email: str, username: str) -> str:
    is_activation_sent = _get_user_manager(trans).send_activation_email(trans, email, username)
    if is_activation_sent:
        message = (
            f"This account has not been activated yet. The activation link has been sent again. "
            f'Please check your email address <b>{escape(email)}</b> including the spam/trash folder. '
            f'<a target="_top" href="{url_for("/")}">Return to the home page</a>.'
        )
    else:
        message = (
            "This account has not been activated yet but we are unable to send the activation link. "
            f'Please contact your local Galaxy administrator. <a target="_top" href="{url_for("/")}">'
            "Return to the home page</a>."
        )
        if trans.app.config.error_email_to is not None:
            message += f" Error contact: {trans.app.config.error_email_to}."
    return message


def _safe_redirect(redirect: Optional[str]) -> Optional[str]:
    if not redirect or redirect == "None":
        return None
    root_url = url_for("/", qualified=True)
    logout_url = url_for(controller="user", action="logout", qualified=True)
    if not util.compare_urls(root_url, redirect, compare_path=False) or util.compare_urls(logout_url, redirect):
        redirect = root_url
    return redirect


def _handle_role_and_group_auto_creation(
    trans: SessionRequestContext,
    user: User,
    roles: Iterable[str],
    auto_create_roles: bool = False,
    auto_create_groups: bool = False,
    auto_assign_roles_to_groups_only: bool = False,
) -> None:
    for role_name in roles:
        role = None
        group = None
        if auto_create_roles:
            try:
                role = trans.app.security_agent.get_role(role_name)
            except Exception:
                role, _ = trans.app.security_agent.create_role(
                    role_name,
                    "Auto created upon user registration",
                    [],
                    [],
                    create_group_for_role=auto_create_groups,
                )
        if auto_create_groups:
            group = trans.sa_session.query(trans.app.model.Group).filter(trans.app.model.Group.name == role_name).first()
            if group is None:
                group = trans.app.model.Group(name=role_name)
                trans.sa_session.add(group)
            trans.app.security_agent.associate_user_group(user, group)
        if auto_assign_roles_to_groups_only and group and role:
            trans.app.security_agent.associate_group_role(group, role)
        elif not auto_assign_roles_to_groups_only and role:
            trans.app.security_agent.associate_user_role(user, role)


def _auto_register_user(trans: SessionRequestContext, login: str, password: str) -> tuple[Optional[User], Optional[str]]:
    try:
        autoreg = trans.app.auth_manager.check_auto_registration(trans, login, password)
    except Conflict as conflict:
        return None, f"Auto-registration failed, {conflict}"
    if not autoreg["auto_reg"]:
        return None, "No such user or invalid password."
    email = autoreg["email"]
    username = autoreg["username"]
    message = " ".join((validate_email(trans, email, allow_empty=True), validate_publicname(trans, username))).rstrip()
    if message:
        return None, f"Auto-registration failed, contact your local Galaxy administrator. {message}"
    user = _get_user_manager(trans).create(email=email, username=username, password="")
    if trans.app.config.user_activation_on:
        _get_user_manager(trans).send_activation_email(trans, email, username)
    if "attributes" in autoreg and "roles" in autoreg["attributes"]:
        _handle_role_and_group_auto_creation(
            trans,
            user,
            autoreg["attributes"]["roles"],
            auto_create_groups=autoreg["auto_create_groups"],
            auto_create_roles=autoreg["auto_create_roles"],
            auto_assign_roles_to_groups_only=autoreg["auto_assign_roles_to_groups_only"],
        )
    return user, None


def _get_user_manager(trans: SessionRequestContext) -> UserManager:
=======
    return _success_payload(trans, access_token, message=message, status=status)


def _get_user_manager(trans) -> UserManager:
>>>>>>> a577d90995 (Add auth login and registration endpoints)
    return trans.app[UserManager]


@router.post("/auth/bootstrap", summary="Bootstrap browser auth state")
def bootstrap(trans: SessionRequestContext = DependsOnTrans):
    auth_session = _ensure_browser_auth_session(trans)
    if auth_session is None:
        return _bootstrap_payload(trans, access_token=None)
    refresh_token = trans.app.auth_session_manager.issue_refresh_token(auth_session)
    _set_refresh_cookie(trans, refresh_token, auth_session.refresh_token_expires_at)
    access_token = trans.app.auth_session_manager.mint_access_token(auth_session, scopes=["api:*"])
    return _bootstrap_payload(trans, access_token=access_token)


@router.post("/auth/login", summary="Login and issue browser auth state")
<<<<<<< HEAD
def login(payload: Optional[dict[str, Any]] = Body(default=None), trans: SessionRequestContext = DependsOnTrans):
    payload = payload or {}
    login_identifier = payload.get("login")
    password = payload.get("password")
    redirect = payload.get("redirect")
=======
def login(payload: Optional[dict] = Body(default=None), trans=DependsOnTrans):
    payload = payload or {}
    login_identifier = payload.get("login")
    password = payload.get("password")
>>>>>>> a577d90995 (Add auth login and registration endpoints)
    if not login_identifier or not password:
        return _error_payload("Please specify a username and password.")

    user_manager = _get_user_manager(trans)
    user = user_manager.get_user_by_identity(login_identifier)
    if user is None:
<<<<<<< HEAD
        user, message = _auto_register_user(trans, login_identifier, password)
        if message:
            return _error_payload(message)
        return _issue_browser_auth_for_user(trans, user, redirect=_safe_redirect(redirect))
=======
        return _error_payload("No such user or invalid password.")
>>>>>>> a577d90995 (Add auth login and registration endpoints)
    if user.purged:
        return _error_payload("This account has been permanently deleted.")
    if user.deleted:
        message = (
            "This account has been marked deleted, contact your local Galaxy administrator to restore the account."
        )
        if trans.app.config.error_email_to is not None:
            message += f" Contact: {trans.app.config.error_email_to}."
        return _error_payload(message)
    if user.external:
        message = (
            "This account was created for use with an external authentication method, contact your local Galaxy "
            "administrator to activate it."
        )
        if trans.app.config.error_email_to is not None:
            message += f" Contact: {trans.app.config.error_email_to}."
        return _error_payload(message)
    if not trans.app.auth_manager.check_password(user, password, trans.request):
        return _error_payload("Invalid password.")
    if trans.app.config.user_activation_on and not user.active:
<<<<<<< HEAD
        if trans.app.config.activation_grace_period != 0:
            if _is_outside_grace_period(trans, user.create_time):
                return _error_payload(_resend_activation_email(trans, user.email, user.username))
        else:
            return _error_payload(_resend_activation_email(trans, user.email, user.username))

    pw_expires = trans.app.config.password_expiration_period
=======
        return _error_payload("This account has not been activated yet.")

    pw_expires = getattr(trans.app.config, "password_expiration_period", None)
>>>>>>> a577d90995 (Add auth login and registration endpoints)
    if pw_expires and user.last_password_change < datetime.today() - pw_expires:
        return {
            "message": "Your password has expired. Please reset or change it to access Galaxy.",
            "status": "warning",
            "expired_user": trans.security.encode_id(user.id),
        }

    response_message = "Success."
    response_status = None
    if pw_expires and user.last_password_change < datetime.today() - timedelta(days=pw_expires.days / 10):
        expiredate = datetime.today() - user.last_password_change + pw_expires
        response_message = f"Your password will expire in {expiredate.days} day(s)."
        response_status = "warning"
<<<<<<< HEAD
    return _issue_browser_auth_for_user(
        trans,
        user,
        message=response_message,
        status=response_status,
        redirect=_safe_redirect(redirect),
    )
=======
    return _issue_browser_auth_for_user(trans, user, message=response_message, status=response_status)
>>>>>>> a577d90995 (Add auth login and registration endpoints)


@router.post("/auth/refresh", summary="Refresh browser access token")
def refresh(trans: SessionRequestContext = DependsOnTrans):
    auth_session = trans.auth_session
    if auth_session is None:
        raise AuthenticationFailed("No active browser auth session.")
    refresh_token = trans.app.auth_session_manager.issue_refresh_token(auth_session)
    auth_session = trans.app.auth_session_manager.get_session_by_id(auth_session.id)
    trans.auth_session = auth_session
    _set_refresh_cookie(trans, refresh_token, auth_session.refresh_token_expires_at)
    access_token = trans.app.auth_session_manager.mint_access_token(auth_session, scopes=["api:*"])
    return _bootstrap_payload(trans, access_token=access_token)


@router.post("/auth/register", summary="Register and issue browser auth state")
<<<<<<< HEAD
def register(payload: Optional[dict[str, Any]] = Body(default=None), trans: SessionRequestContext = DependsOnTrans):
=======
def register(payload: Optional[dict] = Body(default=None), trans=DependsOnTrans):
>>>>>>> a577d90995 (Add auth login and registration endpoints)
    payload = payload or {}
    user_manager = _get_user_manager(trans)
    user, message = user_manager.register(
        trans,
        email=payload.get("email"),
        username=payload.get("username"),
        password=payload.get("password"),
        confirm=payload.get("confirm"),
        subscribe=payload.get("subscribe", False),
    )
    if message:
        return _error_payload(message)
    if user is None:
        return _error_payload("User registration failed.")
    return _issue_browser_auth_for_user(trans, user)


@router.post("/auth/logout", summary="Logout current browser auth session")
def logout(trans: SessionRequestContext = DependsOnTrans, logout_all: bool = False):
    auth_session = trans.auth_session
    if auth_session is not None:
        auth_session = trans.app.auth_session_manager.get_session_by_id(auth_session.id) or auth_session
        trans.app.auth_session_manager.invalidate_session(auth_session)
        if logout_all and auth_session.user is not None:
            trans.app.auth_session_manager.invalidate_sessions_for_user(
                auth_session.user, exclude_auth_session_id=auth_session.id
            )
    if trans.galaxy_session is not None:
        _rotate_legacy_galaxy_session(trans, logout_all=logout_all)
    else:
        trans.sa_session.commit()
    trans.auth_session = None
    trans.clear_user_context()
    trans._auth_source = "anonymous"
    _clear_refresh_cookie(trans)
    response = {"message": "Success."}
    if trans.app.config.use_remote_user and trans.app.config.remote_user_logout_href:
        response["redirect_uri"] = trans.app.config.remote_user_logout_href
    return response
