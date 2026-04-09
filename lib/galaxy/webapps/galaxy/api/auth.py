import secrets
from collections.abc import Iterable
from datetime import (
    datetime,
    timedelta,
)
from typing import (
    Any,
    Optional,
)

from fastapi import (
    Body,
    Query,
)
from fastapi.responses import RedirectResponse
from markupsafe import escape

from galaxy import util
from galaxy.exceptions import (
    AuthenticationFailed,
    Conflict,
)
from galaxy.managers.auth_sessions import (
    AUTH_SESSION_COOKIE_NAME,
    AUTH_SESSION_COOKIE_PATH,
    AUTH_SESSION_CSRF_COOKIE_NAME,
    DEFAULT_TOOL_RUNNER_TOKEN_LIFETIME,
    TOOL_RUNNER_TOKEN_COOKIE_NAME,
    TOOL_RUNNER_TOKEN_COOKIE_PATH,
)
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
from galaxy.webapps.galaxy.api import (
    DependsOnTrans,
    Router,
)
from galaxy.work.context import SessionRequestContext

router = Router(tags=["auth"])


def _cookie_path(trans: SessionRequestContext) -> str:
    return AUTH_SESSION_COOKIE_PATH


def _cookie_domain(trans: SessionRequestContext) -> Optional[str]:
    return trans.app.config.cookie_domain


def _csrf_cookie_path() -> str:
    return "/"


def _request_headers(trans: SessionRequestContext) -> Any:
    return trans.request.headers


def _request_cookie(trans: SessionRequestContext, name: str) -> Optional[str]:
    return trans.request.get_cookie(name)


def _request_remote_host(trans: SessionRequestContext) -> Optional[str]:
    return trans.request.remote_host


def _request_remote_addr(trans: SessionRequestContext) -> Optional[str]:
    return trans.request.remote_addr


def _request_is_secure(trans: SessionRequestContext) -> bool:
    return bool(trans.request.is_secure)


def _set_refresh_cookie(trans: SessionRequestContext, refresh_token: str, expires_at: Optional[datetime]) -> None:
    csrf_token = secrets.token_urlsafe(32)
    max_age = 0
    if expires_at is not None:
        max_age = max(0, int((expires_at - datetime.utcnow()).total_seconds()))
    trans.response.set_cookie(
        key=AUTH_SESSION_COOKIE_NAME,
        value=refresh_token,
        max_age=max_age,
        path=_cookie_path(trans),
        domain=_cookie_domain(trans),
        secure=_request_is_secure(trans),
        httponly=True,
        samesite="lax",
    )
    trans.response.set_cookie(
        key=AUTH_SESSION_CSRF_COOKIE_NAME,
        value=csrf_token,
        max_age=max_age,
        path=_csrf_cookie_path(),
        domain=_cookie_domain(trans),
        secure=_request_is_secure(trans),
        httponly=False,
        samesite="lax",
    )


def _clear_refresh_cookie(trans: SessionRequestContext) -> None:
    trans.response.set_cookie(
        key=AUTH_SESSION_COOKIE_NAME,
        value="",
        max_age=0,
        path=_cookie_path(trans),
        domain=_cookie_domain(trans),
        secure=_request_is_secure(trans),
        httponly=True,
        samesite="lax",
    )
    trans.response.set_cookie(
        key=AUTH_SESSION_CSRF_COOKIE_NAME,
        value="",
        max_age=0,
        path=_csrf_cookie_path(),
        domain=_cookie_domain(trans),
        secure=_request_is_secure(trans),
        httponly=False,
        samesite="lax",
    )


def _set_tool_runner_cookie(trans: SessionRequestContext, response: RedirectResponse, token: str) -> None:
    response.set_cookie(
        key=TOOL_RUNNER_TOKEN_COOKIE_NAME,
        value=token,
        max_age=int(DEFAULT_TOOL_RUNNER_TOKEN_LIFETIME.total_seconds()),
        path=TOOL_RUNNER_TOKEN_COOKIE_PATH,
        domain=_cookie_domain(trans),
        secure=_request_is_secure(trans),
        httponly=True,
        samesite="none",
    )


def _serialize_user(trans: SessionRequestContext, user: Optional[User]) -> Optional[dict[str, str]]:
    if user is None:
        return None
    return {
        "id": trans.security.encode_id(user.id),
        "email": user.email,
        "username": user.username,
    }


def _success_payload(
    trans: SessionRequestContext,
    access_token: str,
    *,
    message: str = "Success.",
    status: Optional[str] = None,
    redirect: Optional[str] = None,
) -> dict[str, Any]:
    payload = _bootstrap_payload(trans, access_token=access_token)
    payload["message"] = message
    if status is not None:
        payload["status"] = status
    if redirect is not None:
        payload["redirect"] = redirect
    return payload


def _error_payload(message: str, *, status: Optional[str] = None, **kwd: Any) -> dict[str, Any]:
    payload = {"err_msg": message}
    if status is not None:
        payload["status"] = status
    payload.update(kwd)
    return payload


def _bootstrap_payload(trans: SessionRequestContext, access_token: Optional[str]) -> dict[str, Any]:
    history = trans.history
    return {
        "authenticated": trans.user is not None,
        "access_token": access_token,
        "auth_source": trans.auth_source,
        "user": _serialize_user(trans, trans.user),
        "actor_user": _serialize_user(trans, trans.actor_user),
        "current_history_id": trans.security.encode_id(history.id) if history else None,
    }


@router.get("/auth/tool_runner", summary="Prepare tool runner browser auth state")
def tool_runner(
    trans: SessionRequestContext = DependsOnTrans,
    tool_id: str = Query(..., description="Tool identifier for the scoped tool-runner token"),
) -> RedirectResponse:
    auth_session = trans.auth_session
    if auth_session is None:
        raise AuthenticationFailed("A browser auth session is required to launch a data source tool.")
    tool_runner_token = trans.app.auth_session_manager.mint_tool_runner_token(auth_session, tool_ids=[tool_id])
    redirect_url = f"/tool_runner/data_source_redirect?tool_id={tool_id}"
    response = RedirectResponse(url=redirect_url)
    _set_tool_runner_cookie(trans, response, tool_runner_token)
    return response


def _require_refresh_csrf(trans: SessionRequestContext) -> None:
    csrf_header = _request_headers(trans).get("X-CSRF-Token")
    csrf_cookie = _request_cookie(trans, AUTH_SESSION_CSRF_COOKIE_NAME)
    if not csrf_header or not csrf_cookie or not secrets.compare_digest(csrf_header, csrf_cookie):
        raise AuthenticationFailed("Missing or invalid CSRF token.")


def _ensure_browser_auth_session(trans: SessionRequestContext) -> Optional[AuthSession]:
    current_auth_session = trans.auth_session
    if current_auth_session is not None:
        return current_auth_session
    if trans.user is None or trans.auth_source == "remote_user":
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


def _promote_browser_login_state(trans: SessionRequestContext, user: User) -> None:
    trans.app.security_agent.create_user_role(user, trans.app)
    history = trans.history
    if history is not None:
        if history.user is None:
            history.user = user
            trans.app.security_agent.history_set_default_permissions(
                history, dataset=True, bypass_manage_permission=True
            )
        trans.sa_session.add(history)
    trans.set_user_context(user)


def issue_browser_auth_for_user(
    trans: SessionRequestContext,
    user: User,
    *,
    message: str = "Success.",
    status: Optional[str] = None,
    redirect: Optional[str] = None,
) -> dict[str, Any]:
    current_auth_session = trans.auth_session
    if current_auth_session is not None:
        trans.app.auth_session_manager.invalidate_session(current_auth_session)
    auth_session = trans.app.auth_session_manager.create_session(
        user=user,
        auth_source="galaxy_token",
        current_history=trans.history,
        remote_host=_request_remote_host(trans),
        remote_addr=_request_remote_addr(trans),
        referer=_request_headers(trans).get("Referer", None),
    )
    trans.auth_session = auth_session
    trans._auth_source = "galaxy_token"
    _promote_browser_login_state(trans, user)
    refresh_token = trans.app.auth_session_manager.issue_refresh_token(auth_session)
    trans.sa_session.commit()
    _set_refresh_cookie(trans, refresh_token, auth_session.refresh_token_expires_at)
    access_token = trans.app.auth_session_manager.mint_access_token(auth_session, scopes=["api:*"])
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
            f"Please check your email address <b>{escape(email)}</b> including the spam/trash folder. "
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
            group = (
                trans.sa_session.query(trans.app.model.Group).filter(trans.app.model.Group.name == role_name).first()
            )
            if group is None:
                group = trans.app.model.Group(name=role_name)
                trans.sa_session.add(group)
            trans.app.security_agent.associate_user_group(user, group)
        if auto_assign_roles_to_groups_only and group and role:
            trans.app.security_agent.associate_group_role(group, role)
        elif not auto_assign_roles_to_groups_only and role:
            trans.app.security_agent.associate_user_role(user, role)


def _auto_register_user(
    trans: SessionRequestContext, login: str, password: str
) -> tuple[Optional[User], Optional[str]]:
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
    return trans.app[UserManager]


@router.post("/auth/bootstrap", summary="Bootstrap browser auth state")
def bootstrap(trans: SessionRequestContext = DependsOnTrans):
    auth_session = _ensure_browser_auth_session(trans)
    if auth_session is None:
        return _bootstrap_payload(trans, access_token=None)
    _require_refresh_csrf(trans)
    refresh_token = trans.app.auth_session_manager.issue_refresh_token(auth_session)
    _set_refresh_cookie(trans, refresh_token, auth_session.refresh_token_expires_at)
    access_token = trans.app.auth_session_manager.mint_access_token(auth_session, scopes=["api:*"])
    return _bootstrap_payload(trans, access_token=access_token)


@router.post("/auth/login", summary="Login and issue browser auth state")
def login(payload: Optional[dict[str, Any]] = Body(default=None), trans: SessionRequestContext = DependsOnTrans):
    payload = payload or {}
    login_identifier = payload.get("login")
    password = payload.get("password")
    redirect = payload.get("redirect")
    if not login_identifier or not password:
        return _error_payload("Please specify a username and password.")

    user_manager = _get_user_manager(trans)
    user = user_manager.get_user_by_identity(login_identifier)
    if user is None:
        user, message = _auto_register_user(trans, login_identifier, password)
        if message:
            return _error_payload(message)
        return issue_browser_auth_for_user(trans, user, redirect=_safe_redirect(redirect))
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
        if trans.app.config.activation_grace_period != 0:
            if _is_outside_grace_period(trans, user.create_time):
                return _error_payload(_resend_activation_email(trans, user.email, user.username))
        else:
            return _error_payload(_resend_activation_email(trans, user.email, user.username))

    pw_expires = trans.app.config.password_expiration_period
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
    return issue_browser_auth_for_user(
        trans,
        user,
        message=response_message,
        status=response_status,
        redirect=_safe_redirect(redirect),
    )


@router.post("/auth/refresh", summary="Refresh browser access token")
def refresh(trans: SessionRequestContext = DependsOnTrans):
    auth_session = trans.auth_session
    if auth_session is None:
        raise AuthenticationFailed("No active browser auth session.")
    _require_refresh_csrf(trans)
    refresh_token = trans.app.auth_session_manager.issue_refresh_token(auth_session)
    auth_session = trans.app.auth_session_manager.get_session_by_id(auth_session.id)
    trans.auth_session = auth_session
    _set_refresh_cookie(trans, refresh_token, auth_session.refresh_token_expires_at)
    access_token = trans.app.auth_session_manager.mint_access_token(auth_session, scopes=["api:*"])
    return _bootstrap_payload(trans, access_token=access_token)


@router.post("/auth/register", summary="Register and issue browser auth state")
def register(payload: Optional[dict[str, Any]] = Body(default=None), trans: SessionRequestContext = DependsOnTrans):
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
    return issue_browser_auth_for_user(trans, user)


@router.post("/auth/change_password", summary="Change the current user's password")
def change_password(
    payload: Optional[dict[str, Any]] = Body(default=None), trans: SessionRequestContext = DependsOnTrans
):
    payload = payload or {}
    user, message = _get_user_manager(trans).change_password(trans, **payload)
    if user is None:
        return _error_payload(message)
    if trans.auth_session is None or payload.get("token"):
        return issue_browser_auth_for_user(trans, user, message=message)
    return {"message": message}


@router.post("/auth/reset_password", summary="Request a password reset email")
def reset_password(
    payload: Optional[dict[str, Any]] = Body(default=None), trans: SessionRequestContext = DependsOnTrans
):
    payload = payload or {}
    message = _get_user_manager(trans).send_reset_email(trans, payload)
    if message:
        return _error_payload(message)
    return {"message": "If an account exists for this email address a confirmation email will be dispatched."}


@router.post("/auth/logout", summary="Logout current browser auth session")
def logout(trans: SessionRequestContext = DependsOnTrans, logout_all: bool = False):
    auth_session = trans.auth_session
    if auth_session is not None:
        _require_refresh_csrf(trans)
        auth_session = trans.app.auth_session_manager.get_session_by_id(auth_session.id) or auth_session
        trans.app.auth_session_manager.invalidate_session(auth_session)
        if logout_all and auth_session.user is not None:
            trans.app.auth_session_manager.invalidate_sessions_for_user(
                auth_session.user, exclude_auth_session_id=auth_session.id
            )
    trans.sa_session.commit()
    trans.auth_session = None
    trans.clear_user_context()
    trans._auth_source = "anonymous"
    _clear_refresh_cookie(trans)
    response = {"message": "Success."}
    if trans.app.config.use_remote_user and trans.app.config.remote_user_logout_href:
        response["redirect_uri"] = trans.app.config.remote_user_logout_href
    return response
