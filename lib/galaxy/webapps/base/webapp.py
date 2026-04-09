""" """

import datetime
import inspect
import logging
import os
import re
import socket
import time
from contextlib import ExitStack
from http.cookies import CookieError
from typing import (
    Any,
    Optional,
)
from urllib.parse import urlparse

import mako.lookup
import mako.runtime
from apispec import APISpec
from paste.urlmap import URLMap
from sqlalchemy import select
from sqlalchemy.exc import NoResultFound
from webob.exc import HTTPException

from galaxy import util
from galaxy.exceptions import (
    AuthenticationFailed,
    ConfigurationError,
    MessageException,
    RequestParameterMissingException,
)
from galaxy.managers import context
from galaxy.managers.auth_sessions import AUTH_SESSION_COOKIE_NAME
from galaxy.managers.users import UserManager
from galaxy.model import (
    AuthSession,
    History,
    User,
)
from galaxy.model.base import ensure_object_added_to_session
from galaxy.structured_app import (
    BasicSharedApp,
    MinimalApp,
)
from galaxy.util import (
    asbool,
    safe_makedirs,
    unicodify,
)
from galaxy.util.resources import (
    as_file,
    resource_path,
)
from galaxy.util.sanitize_html import sanitize_html
from galaxy.version import VERSION
from galaxy.web.framework import (
    base,
    helpers,
    url_for,
)
from galaxy.web.framework.middleware.static import CacheableStaticURLParser as Static

try:
    import galaxy.web_client

    default_static_dist_dir = os.path.join(os.path.dirname(galaxy.web_client.__file__), "dist")
except ImportError:
    default_static_dist_dir = None  # type: ignore[assignment]

log = logging.getLogger(__name__)


UCSC_SERVERS = (
    "hgw1.cse.ucsc.edu",
    "hgw2.cse.ucsc.edu",
    "hgw3.cse.ucsc.edu",
    "hgw4.cse.ucsc.edu",
    "hgw5.cse.ucsc.edu",
    "hgw6.cse.ucsc.edu",
    "hgw7.cse.ucsc.edu",
    "hgw8.cse.ucsc.edu",
    "hgw1.soe.ucsc.edu",
    "hgw2.soe.ucsc.edu",
    "hgw3.soe.ucsc.edu",
    "hgw4.soe.ucsc.edu",
    "hgw5.soe.ucsc.edu",
    "hgw6.soe.ucsc.edu",
    "hgw7.soe.ucsc.edu",
    "hgw8.soe.ucsc.edu",
)

TOOL_RUNNER_SESSION_COOKIE = "galaxytoolrunnersession"


class WebApplication(base.WebApplication):
    """
    Base WSGI application instantiated for all Galaxy webapps.

    A web application that:

        * adds API and UI controllers by scanning given directories and
          importing all modules found there.
        * has a security object.
        * builds mako template lookups.
        * generates GalaxyWebTransactions.
    """

    injection_aware: bool = False

    def __init__(self, galaxy_app: MinimalApp, name: Optional[str] = None) -> None:
        super().__init__()
        self.name = name
        galaxy_app.is_webapp = True
        self.set_transaction_factory(lambda e: self.transaction_chooser(e, galaxy_app))
        # Mako support
        self.mako_template_lookup = self.create_mako_template_lookup(galaxy_app, name)
        # Security helper
        self.security = galaxy_app.security

        # We need this to set the REQUEST_ID contextvar in model.base *BEFORE* a GalaxyWebTransaction is created.
        # This will ensure a SQLAlchemy session is request-scoped for legacy (non-fastapi) endpoints.
        self.session_factories.append(galaxy_app.model)

    def build_apispec(self):
        """
        Traverse all route paths starting with "api" and create an APISpec instance.
        """
        # API specification builder
        apispec = APISpec(
            title=self.name,
            version=VERSION,
            openapi_version="3.0.2",
        )
        RE_URL = re.compile(
            r"""
            (?::\(|{)
                (\w*)
                (?::.*)?
            (?:\)|})""",
            re.X,
        )
        DEFAULT_API_RESOURCE_NAMES = ("index", "create", "new", "update", "edit", "show", "delete")
        for rule in self.mapper.matchlist:
            if rule.routepath.endswith(".:(format)") or not rule.routepath.startswith("api/"):
                continue
            # Try to replace routes various ways to encode variables with simple swagger {form}
            swagger_path = "/{}".format(RE_URL.sub(r"{\1}", rule.routepath))
            controller = rule.defaults.get("controller", "")
            action = rule.defaults.get("action", "")
            # Get the list of methods for the route
            methods = []
            if rule.conditions:
                m = rule.conditions.get("method", [])
                methods = [m] if isinstance(m, str) else m
            # Find the controller class
            if controller not in self.api_controllers:
                # Only happens when removing a controller after porting to FastAPI.
                raise Exception(f"No controller class found for '{controller}', remove from buildapp.py ?")
            controller_class = self.api_controllers[controller]
            if not hasattr(controller_class, action):
                if action not in DEFAULT_API_RESOURCE_NAMES:
                    # There's a manually specified action that points to a function that doesn't exist anymore
                    raise Exception(
                        f"No action found for {action} in class {controller_class}, remove from buildapp.py ?"
                    )
                continue
            action_method = getattr(controller_class, action)
            operations = {}
            # Add methods that have routes but are not documents
            for method in methods:
                if method.lower() not in operations:
                    operations[method.lower()] = {
                        "description": f"This route has not yet been ported to FastAPI. The documentation may not be complete.\n{action_method.__doc__}",
                        "tags": ["undocumented"],
                    }
            # Store the swagger path
            apispec.path(path=swagger_path, operations=operations)
        return apispec

    def create_mako_template_lookup(self, galaxy_app, name):
        paths = []
        base_package = (
            "tool_shed.webapp" if galaxy_app.name == "tool_shed" else __name__
        )  # reports has templates in galaxy package
        base_template_path = resource_path(base_package, "templates")
        with ExitStack() as stack:
            # First look in webapp specific directory
            if name is not None:
                path = stack.enter_context(as_file(base_template_path / "webapps" / name))
                paths.append(path)
            # Then look in root directory
            path = stack.enter_context(as_file(base_template_path))
            paths.append(path)
            # Create TemplateLookup with a small cache
            return mako.lookup.TemplateLookup(
                directories=paths, module_directory=galaxy_app.config.template_cache_path, collection_size=500
            )

    def handle_controller_exception(self, e, trans, method, kwargs):
        if not isinstance(e, HTTPException):
            # We're still logging too much here but at least it's not logging webob.exc.HTTPFound and friends
            log.debug(f"Encountered exception in controller method: {method}", exc_info=True)
        if isinstance(e, TypeError):
            method_signature = inspect.signature(method)
            required_parameters = {
                p.name
                for p in method_signature.parameters.values()
                if p.name != "trans" and p.default is inspect._empty
            }
            missing_required_parameters = required_parameters.difference(kwargs)
            if missing_required_parameters:
                e = RequestParameterMissingException(
                    f"Required parameter(s) {', '.join(missing_required_parameters)} not provided in request."
                )
        if isinstance(e, MessageException):
            # In the case of a controller exception, sanitize to make sure
            # unsafe html input isn't reflected back to the user
            trans.response.status = e.status_code
            return trans.show_message(sanitize_html(e.err_msg), e.type)

    def make_body_iterable(self, trans, body):
        return base.WebApplication.make_body_iterable(self, trans, body)

    def transaction_chooser(self, environ, galaxy_app: BasicSharedApp):
        return GalaxyWebTransaction(environ, galaxy_app, self)

    def add_ui_controllers(self, package_name, app):
        """
        Search for UI controllers in `package_name` and add
        them to the webapp.
        """
        from galaxy.webapps.base.controller import BaseUIController

        for name, module in base.walk_controller_modules(package_name):
            # Look for a controller inside the modules
            for key in dir(module):
                T = getattr(module, key)
                if inspect.isclass(T) and T is not BaseUIController and issubclass(T, BaseUIController):
                    controller = self._instantiate_controller(T, app)
                    self.add_ui_controller(name, controller)

    def add_api_controllers(self, package_name, app):
        """
        Search for UI controllers in `package_name` and add
        them to the webapp.
        """
        from galaxy.webapps.base.controller import BaseAPIController

        for name, module in base.walk_controller_modules(package_name):
            for key in dir(module):
                T = getattr(module, key)
                # Exclude classes such as BaseAPIController and BaseTagItemsController
                if inspect.isclass(T) and not key.startswith("Base") and issubclass(T, BaseAPIController):
                    # By default use module_name, but allow controller to override name
                    controller_name = getattr(T, "controller_name", name)
                    controller = self._instantiate_controller(T, app)
                    self.add_api_controller(controller_name, controller)

    def _instantiate_controller(self, T, app):
        """Extension point, allow apps to construct controllers differently,
        really just used to stub out actual controllers for routes testing.
        """
        controller = None
        if self.injection_aware:
            controller = app.resolve_or_none(T)
            if controller is not None:
                for key, value in T.__dict__.items():
                    if hasattr(value, "galaxy_type_depends"):
                        value_type = value.galaxy_type_depends
                        setattr(controller, key, app[value_type])
        if controller is None:
            controller = T(app)
        return controller


def _is_embed_request(path: str, query_string: str) -> bool:
    return path.startswith("/published/") and "embed=true" in query_string


def config_allows_origin(origin_raw, config):
    # boil origin header down to hostname
    origin = urlparse(origin_raw).hostname

    # singular match
    def matches_allowed_origin(origin, allowed_origin):
        if isinstance(allowed_origin, str):
            return origin == allowed_origin
        match = allowed_origin.match(origin)
        return match and match.group() == origin

    # localhost uses no origin header (== null)
    if not origin:
        return False

    # check for '*' or compare to list of allowed
    for allowed_origin in config.allowed_origin_hostnames:
        if allowed_origin == "*" or matches_allowed_origin(origin, allowed_origin):
            return True

    return False


def url_builder(*args, **kwargs) -> str:
    """Wrapper around the WSGI version of the function for reversing URLs."""
    kwargs.update(kwargs.pop("query_params", {}))
    return url_for(*args, **kwargs)


class GalaxyWebTransaction(base.DefaultWebTransaction, context.ProvidesHistoryContext):
    """
    Encapsulates web transaction specific state for the Galaxy application
    (specifically the user's "cookie" session and history)
    """

    def __init__(self, environ: dict[str, Any], app: BasicSharedApp, webapp: WebApplication) -> None:
        self._app = app
        self.webapp = webapp
        self.user_manager = app[UserManager]
        self.auth_session_manager = app.auth_session_manager
        super().__init__(environ)
        config = self.app.config
        self.debug = asbool(config.get("debug", False))
        if x_frame_options := config.get("x_frame_options", None):
            if not _is_embed_request(self.request.path_info, self.environ.get("QUERY_STRING", "")):
                self.response.headers["X-Frame-Options"] = x_frame_options
        # Flag indicating whether we are in workflow building mode (means
        # that the current history should not be used for parameter values
        # and such).
        self.workflow_building_mode = False
        self.__user = None
        self._actor_user = None
        self.auth_session = None
        self.error_message = None
        self.host = self.request.host
        self._short_term_cache: dict[tuple[str, ...], Any] = {}

        # set any cross origin resource sharing headers if configured to do so
        self.set_cors_headers()

        if self.environ.get("is_api_request", False):
            # With API requests, if there's a key, use it and associate the
            # user with the transaction.
            # If not, check for an active session but do not create one.
            # If an error message is set here, it's sent back using
            # trans.show_error in the response -- in expose_api.
            self.error_message = self._authenticate_api()
        elif self.app.name == "reports":
            self.auth_session = None
        else:
            self._ensure_browser_auth_session()

        if self.app.authnz_manager:
            self.app.authnz_manager.refresh_expiring_oidc_tokens(self)

        if self.auth_session:
            # Prevent deleted users from accessing Galaxy.
            if config.get("use_remote_user", False) and self.auth_session.user and self.auth_session.user.deleted:
                self.response.send_redirect(url_for("/static/user_disabled.html"))
        if config.get("require_login", False):
            self._ensure_logged_in_user()
            if config.get("session_duration", None):
                now = datetime.datetime.now()
                if self.auth_session.last_activity:
                    expiration_time = self.auth_session.last_activity + datetime.timedelta(
                        minutes=config.get("session_duration", 0)
                    )
                else:
                    expiration_time = now
                    self.auth_session.last_activity = now - datetime.timedelta(seconds=1)
                    self.sa_session.add(self.auth_session)
                    self.sa_session.commit()
                if expiration_time < now:
                    self.handle_user_logout()
                    if self.environ.get("is_api_request", False):
                        self.response.status = 401
                        self.user = None
                        self.auth_session = None
                    else:
                        self.response.send_redirect(
                            url_for(
                                "/login/start",
                                message="You have been logged out due to inactivity. Please log in again to continue using Galaxy.",
                                status="info",
                            )
                        )
                else:
                    self.auth_session.last_activity = now
                    self.sa_session.add(self.auth_session)
                    self.sa_session.commit()
        elif not self.environ.get("is_api_request", False):
            self._ensure_browser_auth_session()

    @property
    def app(self):
        return self._app

    @property
    def url_builder(self):
        return url_builder

    def set_cors_allow(self, name=None, value=None):
        acr = "Access-Control-Request-"
        if name is None:
            for key in self.request.headers.keys():
                if key.startswith(acr):
                    self.set_cors_allow(name=key[len(acr) :], value=value)
        else:
            resp_name = f"Access-Control-Allow-{name}"
            if value is None:
                value = self.request.headers.get(acr + name, None)
            if value:
                self.response.headers[resp_name] = value
            elif resp_name in self.response.headers:
                del self.response.headers[resp_name]

    def set_cors_origin(self, origin=None):
        if origin is None:
            origin = self.request.headers.get("Origin", None)
        if origin:
            self.response.headers["Access-Control-Allow-Origin"] = origin
        elif "Access-Control-Allow-Origin" in self.response.headers:
            del self.response.headers["Access-Control-Allow-Origin"]

    def set_cors_headers(self):
        """Allow CORS requests if configured to do so by echoing back the
        request's 'Origin' header (if any) as the response header
        'Access-Control-Allow-Origin'

        Preflight OPTIONS requests to the API work by routing all OPTIONS
        requests to a single method in the authenticate API (options method),
        setting CORS headers, and responding OK.

        NOTE: raising some errors (such as httpexceptions), will remove the
        header (e.g. client will get both CORS error and 404 inside that)
        """

        # do not set any access control headers if not configured for it (common case)
        if not self.app.config.get("allowed_origin_hostnames", None):
            return
        # do not set any access control headers if there's no origin header on the request
        origin_header = self.request.headers.get("Origin", None)
        if not origin_header:
            return

        # check against the list of allowed strings/regexp hostnames, echo original if cleared
        if config_allows_origin(origin_header, self.app.config):
            self.set_cors_origin(origin=origin_header)
        else:
            self.response.status = 400

    def get_user(self):
        """Return the current user if logged in or None."""
        user = self.__user
        if not user and self.auth_session:
            user = self.auth_session.user
        if user is not None:
            self.__user = user
        return user

    def set_user(self, user):
        """Set the current user."""
        if self.auth_session:
            self.auth_session.user = user
            self.sa_session.add(self.auth_session)
            self.sa_session.commit()
        self.__user = user
        if self._actor_user is None or user is None:
            self._actor_user = user

    user = property(get_user, set_user)

    def get_actor_user(self):
        return self._actor_user or self.get_user()

    def set_actor_user(self, user):
        self._actor_user = user

    actor_user = property(get_actor_user, set_actor_user)

    @property
    def galaxy_session(self) -> Optional[AuthSession]:
        return self.auth_session

    @galaxy_session.setter
    def galaxy_session(self, auth_session: Optional[AuthSession]) -> None:
        self.auth_session = auth_session

    def set_user_context(self, user, actor_user=None):
        """Set the effective and actor users together."""
        self.set_user(user)
        if actor_user is not None:
            self._actor_user = actor_user

    def get_cookie(self, name: str):
        """Convenience method for getting a session cookie"""
        try:
            # If we've changed the cookie during the request return the new value
            if name in self.response.cookies:
                return self.response.cookies[name].value
            return self.request.cookies[name].value
        except Exception:
            return None

    def set_cookie(self, value, name: str, path="/", age=90, version="1"):
        self._set_cookie(value, name=name, path=path, age=age, version=version)

    def set_auth_cookie(self, refresh_token: str, expires_at: Optional[datetime.datetime]) -> None:
        max_age = 0
        if expires_at is not None:
            max_age = max(0, int((expires_at - datetime.datetime.utcnow()).total_seconds()))
        self.response.cookies[AUTH_SESSION_COOKIE_NAME] = unicodify(refresh_token)
        self.response.cookies[AUTH_SESSION_COOKIE_NAME]["path"] = self.cookie_path
        self.response.cookies[AUTH_SESSION_COOKIE_NAME]["max-age"] = max_age
        tstamp = time.gmtime(time.time() + max_age)
        self.response.cookies[AUTH_SESSION_COOKIE_NAME]["expires"] = time.strftime("%a, %d-%b-%Y %H:%M:%S GMT", tstamp)
        self.response.cookies[AUTH_SESSION_COOKIE_NAME]["version"] = "1"
        if self.request.environ.get("wsgi.url_scheme") == "https":
            self.response.cookies[AUTH_SESSION_COOKIE_NAME]["secure"] = True
        self.response.cookies[AUTH_SESSION_COOKIE_NAME]["httponly"] = True
        if self.app.config.cookie_domain is not None:
            self.response.cookies[AUTH_SESSION_COOKIE_NAME]["domain"] = self.app.config.cookie_domain

    def clear_auth_cookie(self) -> None:
        self.set_auth_cookie("", datetime.datetime.utcnow())

    def _set_cookie(self, value, name: str, path="/", age=90, version="1", encode_value=False):
        """Convenience method for setting a session cookie"""
        if encode_value:
            value = self.security.encode_guid(value)
        self.response.cookies[name] = unicodify(value)
        self.response.cookies[name]["path"] = path
        self.response.cookies[name]["max-age"] = 3600 * 24 * age  # 90 days
        tstamp = time.localtime(time.time() + 3600 * 24 * age)
        self.response.cookies[name]["expires"] = time.strftime("%a, %d-%b-%Y %H:%M:%S GMT", tstamp)
        self.response.cookies[name]["version"] = version
        https = self.request.environ.get("wsgi.url_scheme") == "https"
        if https:
            self.response.cookies[name]["secure"] = True
        try:
            self.response.cookies[name]["httponly"] = True
        except CookieError as e:
            log.warning(f"Error setting httponly attribute in cookie '{name}': {e}")
        if self.app.config.cookie_domain is not None:
            self.response.cookies[name]["domain"] = self.app.config.cookie_domain

    def _authenticate_api(self) -> Optional[str]:
        """
        Authenticate for the API via key or session (if available).
        """
        oidc_access_token = self.request.headers.get("Authorization", None)
        oidc_token_supplied = (
            self.environ.get("is_api_request", False) and oidc_access_token and "Bearer " in oidc_access_token
        )
        api_key = self.request.params.get("key", None) or self.request.headers.get("x-api-key", None)
        api_key_supplied = self.environ.get("is_api_request", False) and api_key
        if api_key_supplied:
            # Sessionless API transaction, we just need to associate a user.
            try:
                user = self.user_manager.by_api_key(api_key)
            except AuthenticationFailed as e:
                return str(e)
            self.set_user(user)
        elif oidc_token_supplied:
            # Sessionless API transaction with oidc token, we just need to associate a user.
            oidc_access_token = oidc_access_token.replace("Bearer ", "")
            try:
                user = self.user_manager.by_oidc_access_token(oidc_access_token)
            except AuthenticationFailed as e:
                return str(e)
            self.set_user(user)
        else:
            # Anonymous API interaction -- anything but @expose_api_anonymous will fail past here.
            self.user = None
            self.auth_session = None
        return None

    def _load_auth_session(self) -> None:
        if self.auth_session_manager is None:
            return
        refresh_token = self.get_cookie(name=AUTH_SESSION_COOKIE_NAME)
        if not refresh_token:
            return
        try:
            self.auth_session = self.auth_session_manager.get_session_for_refresh_token(refresh_token)
        except AuthenticationFailed:
            self.auth_session = None

    def _ensure_browser_auth_session(self) -> None:
        if self.auth_session_manager is None:
            return
        if self.auth_session is None:
            self.auth_session = self.auth_session_manager.create_session(
                auth_source="anonymous",
                remote_host=self.request.remote_host,
                remote_addr=self.request.remote_addr,
                referer=self.request.headers.get("Referer", None),
            )
            refresh_token = self.auth_session_manager.issue_refresh_token(self.auth_session)
            self.sa_session.commit()
            self.set_auth_cookie(refresh_token, self.auth_session.refresh_token_expires_at)

    def _ensure_valid_session(self, create: bool = True) -> None:
        """Deprecated legacy session loader retained for compatibility during migration."""
        self._ensure_browser_auth_session()

    def _ensure_logged_in_user(self) -> None:
        if self.auth_session is None or self.auth_session.user is None:
            # TODO: re-engineer to eliminate the use of allowed_paths
            # as maintenance overhead is far too high.
            allowed_paths = [
                # client app route
                # TODO: might be better as '/:username/login', '/:username/logout'
                url_for("/login"),
                url_for(controller="login", action="start"),
                # mako app routes
                url_for(controller="user", action="login"),
                url_for(controller="user", action="logout"),
                url_for(controller="user", action="reset_password"),
                url_for(controller="user", action="change_password"),
                # TODO: do any of these still need to bypass require login?
                url_for(controller="user", action="api_keys"),
                url_for(controller="user", action="create"),
                url_for(controller="user", action="index"),
                url_for(controller="user", action="manage_user_info"),
                url_for(controller="user", action="set_default_permissions"),
                url_for(controller="api", action="webhooks"),
            ]
            # append the welcome url to allowed paths if we'll show it at the login screen
            if self.app.config.show_welcome_with_login:
                allowed_paths.append(url_for("/welcome"))

            # prevent redirect when UCSC server attempts to get dataset contents as 'anon' user
            display_as = url_for("/display_as")
            if self.app.datatypes_registry.get_display_sites("ucsc") and self.request.path == display_as:
                try:
                    host = socket.gethostbyaddr(self.environ["REMOTE_ADDR"])[0]
                except (OSError, socket.herror, socket.gaierror):
                    host = None
                if host in UCSC_SERVERS:
                    return
            # prevent redirect for external, enabled display applications getting dataset contents
            external_display_path = url_for(controller="", action="display_application")
            if self.request.path.startswith(external_display_path):
                request_path_split = self.request.path.split("/")
                try:
                    if (
                        self.app.datatypes_registry.display_applications.get(request_path_split[-5])
                        and request_path_split[-4]
                        in self.app.datatypes_registry.display_applications.get(request_path_split[-5]).links
                        and request_path_split[-3] != "None"
                    ):
                        return
                except IndexError:
                    pass
            authnz_controller_base = url_for(controller="authnz", action="index")
            if self.request.path.startswith(authnz_controller_base):
                #  All authnz requests pass through
                return
            # redirect to root if the path is not in the list above
            if self.request.path not in allowed_paths:
                login_url = url_for("/login", redirect=self.request.path)
                self.response.send_redirect(login_url)

    @property
    def cookie_path(self):
        # Cookies for non-root paths should not end with `/` -> https://stackoverflow.com/questions/36131023/setting-a-slash-on-cookie-path
        return (self.app.config.cookie_path or url_for("/")).rstrip("/") or "/"

    def check_user_library_import_dir(self, user: User) -> None:
        if self.app.config.get("user_library_import_dir_auto_creation", False):
            # try to create a user library import directory
            try:
                safe_makedirs(os.path.join(self.app.config.user_library_import_dir, user.email))
            except ConfigurationError as e:
                self.log_event(unicodify(e))

    def user_checks(self, user: User) -> None:
        """
        This could contain more checks around a user upon login
        """
        self.check_user_library_import_dir(user)

    def _associate_user_history(self, user: User, prev_galaxy_session=None) -> None:
        """Deprecated legacy helper."""
        return None

    def handle_user_login(self, user: User) -> None:
        """
        Login a new user (possibly newly created)
           - do some 'system' checks (if any) for this user
           - create a new session
           - associate new session with user
           - if old session had a history and it was not associated with a user, associate it with the new session,
             otherwise associate the current session's history with the user
           - add the disk usage of the current session to the user's total disk usage
        """
        self.user_checks(user)
        self.app.security_agent.create_user_role(user, self.app)
        self.issue_auth_session(user=user, auth_source="galaxy_token")
        if self.webapp.name == "galaxy":
            self.get_or_create_default_history()

    def handle_user_logout(self, logout_all: bool = False) -> None:
        """
        Logout the current user:
           - invalidate the current session
           - create a new session with no user associated
        """
        previous_auth_session = self.auth_session
        previous_history = self.history
        self.invalidate_auth_session(logout_all=logout_all)
        if previous_auth_session and logout_all and previous_auth_session.user is not None:
            self.auth_session_manager.invalidate_sessions_for_user(
                previous_auth_session.user, exclude_auth_session_id=previous_auth_session.id
            )
        if self.auth_session_manager is not None:
            self.auth_session = self.auth_session_manager.create_session(
                auth_source="anonymous",
                current_history=previous_history,
                remote_host=self.request.remote_host,
                remote_addr=self.request.remote_addr,
                referer=self.request.headers.get("Referer", None),
            )
            refresh_token = self.auth_session_manager.issue_refresh_token(self.auth_session)
            self.sa_session.commit()
            self.set_auth_cookie(refresh_token, self.auth_session.refresh_token_expires_at)

    def get_galaxy_session(self) -> Optional[AuthSession]:
        """
        Return the current galaxy session
        """
        return self.auth_session

    def issue_auth_session(
        self,
        user: Optional[User] = None,
        auth_source: str = "galaxy_token",
    ) -> Optional[AuthSession]:
        if self.auth_session_manager is None:
            return None
        if self.auth_session is not None:
            self.auth_session_manager.invalidate_session(self.auth_session)
        current_history = self.history
        auth_session = self.auth_session_manager.create_session(
            user=user,
            auth_source=auth_source,
            current_history=current_history,
            remote_host=self.request.remote_host,
            remote_addr=self.request.remote_addr,
            referer=self.request.headers.get("Referer", None),
        )
        refresh_token = self.auth_session_manager.issue_refresh_token(auth_session)
        self.sa_session.commit()
        self.auth_session = auth_session
        self.set_auth_cookie(refresh_token, auth_session.refresh_token_expires_at)
        return auth_session

    def invalidate_auth_session(self, logout_all: bool = False) -> None:
        if self.auth_session_manager is None:
            return
        current_auth_session = self.auth_session
        if current_auth_session is not None:
            self.auth_session_manager.invalidate_session(current_auth_session)
            if logout_all and current_auth_session.user is not None:
                self.auth_session_manager.invalidate_sessions_for_user(
                    current_auth_session.user, exclude_auth_session_id=current_auth_session.id
                )
            self.sa_session.commit()
        self.auth_session = None
        self.clear_auth_cookie()

    def get_history(self, create=False, most_recent=False):
        """
        Load the current history.

            - If that isn't available, we find the most recently updated history.
            - If *that* isn't available, we get or create the default history.

        Transactions will not always have an active history (API requests), so
        None is a valid response.
        """
        history = None
        if self.auth_session and self.auth_session.current_history:
            history = self.auth_session.current_history
        if not history and most_recent:
            history = self.get_most_recent_history()
        if not history and util.string_as_bool(create):
            history = self.get_or_create_default_history()
        return history

    def set_history(self, history: Optional[History]) -> None:
        if history and not history.deleted and self.auth_session:
            self.auth_session.current_history = history
            self.sa_session.add(self.auth_session)
        self.sa_session.commit()

    @property
    def history(self):
        return self.get_history()

    def get_or_create_default_history(self):
        """
        Gets or creates a default history and associates it with the current
        session.
        """
        assert self.auth_session

        # Just return the current history if one exists and is not deleted.
        history = self.auth_session.current_history
        if history and not history.deleted:
            return history

        # Look for an existing history that has the default name, is not
        # deleted, and is empty. If this exists, we associate it with the
        # current session and return it.
        if user := self.auth_session.user:
            stmt = select(History).filter_by(user=user, name=History.default_name, deleted=False)
            unnamed_histories = self.sa_session.scalars(stmt)
            for history in unnamed_histories:
                if history.empty:
                    self.set_history(history)
                    return history

        # Don't create new history if login required and user is anonymous
        if self.app.config.get("require_login", False) and not self.user:
            return None

        # No suitable history found, create a new one.
        return self.new_history()

    def get_most_recent_history(self):
        """
        Gets the most recently updated history.
        """
        # There must be a user to fetch histories, and without a user we have
        # no recent history.
        user = self.get_user()
        if not user:
            return None
        try:
            stmt = select(History).filter_by(user=user, deleted=False).order_by(History.update_time.desc()).limit(1)
            recent_history = self.sa_session.scalars(stmt).first()
        except NoResultFound:
            return None
        self.set_history(recent_history)
        return recent_history

    def new_history(self, name: Optional[str] = None) -> History:
        """
        Create a new history and associate it with the current session and
        its associated user (if set).
        """
        # Create new history
        history = History()
        if name:
            history.name = name
        # Make it the session's current history
        self.auth_session.current_history = history
        # Associate with user
        if self.auth_session.user:
            history.user = self.auth_session.user
        # Track genome_build with history
        history.genome_build = self.app.genome_builds.default_value
        # Set the user's default history permissions
        self.app.security_agent.history_set_default_permissions(history)
        # Save
        self.sa_session.add_all((self.auth_session, history))
        self.sa_session.commit()
        return history

    @base.lazy_property
    def template_context(self):
        return {}

    def set_message(self, message, type=None):
        """
        Convenience method for setting the 'message' and 'message_type'
        element of the template context.
        """
        self.template_context["message"] = message
        if type:
            self.template_context["status"] = type

    def get_message(self):
        """
        Convenience method for getting the 'message' element of the template
        context.
        """
        return self.template_context["message"]

    def show_message(self, message, type="info", refresh_frames=None, cont=None, use_panels=False, active_view=""):
        """
        Convenience method for displaying a simple page with a single message.

        `type`: one of "error", "warning", "info", or "done"; determines the
                type of dialog box and icon displayed with the message

        `refresh_frames`: names of frames in the interface that should be
                          refreshed when the message is displayed
        """
        refresh_frames = refresh_frames or []
        return self.fill_template(
            "message.mako",
            status=type,
            message=message,
            refresh_frames=refresh_frames,
            cont=cont,
            use_panels=use_panels,
            active_view=active_view,
        )

    def show_error_message(self, message, refresh_frames=None, use_panels=False, active_view=""):
        """
        Convenience method for displaying an error message. See `show_message`.
        """
        refresh_frames = refresh_frames or []
        return self.show_message(message, "error", refresh_frames, use_panels=use_panels, active_view=active_view)

    def show_ok_message(self, message, refresh_frames=None, use_panels=False, active_view=""):
        """
        Convenience method for displaying an ok message. See `show_message`.
        """
        refresh_frames = refresh_frames or []
        return self.show_message(message, "done", refresh_frames, use_panels=use_panels, active_view=active_view)

    def show_warn_message(self, message, refresh_frames=None, use_panels=False, active_view=""):
        """
        Convenience method for displaying an warn message. See `show_message`.
        """
        refresh_frames = refresh_frames or []
        return self.show_message(message, "warning", refresh_frames, use_panels=use_panels, active_view=active_view)

    @property
    def session_csrf_token(self):
        token = ""
        if self.auth_session:
            token = self.security.encode_id(self.auth_session.id, kind="csrf")
        return token

    def check_csrf_token(self, payload):
        session_csrf_token = payload.get("session_csrf_token")
        if not session_csrf_token:
            return "No session token set, denying request."
        elif session_csrf_token != self.session_csrf_token:
            return "Wrong session token found, denying request."

    def fill_template(self, filename, **kwargs):
        """
        Fill in a template, putting any keyword arguments on the context.
        """
        # call get_user so we can invalidate sessions from external users,
        # if external auth has been disabled.
        self.get_user()
        assert filename.endswith(".mako")
        return self.fill_template_mako(filename, **kwargs)

    def fill_template_mako(self, filename, template_lookup=None, **kwargs):
        template_lookup = template_lookup or self.webapp.mako_template_lookup
        template = template_lookup.get_template(filename)

        data = dict(
            caller=self,
            t=self,
            trans=self,
            h=helpers,
            util=util,
            request=self.request,
            response=self.response,
            app=self.app,
        )
        data.update(self.template_context)
        data.update(kwargs)
        return template.render(**data)

    def qualified_url_for_path(self, path):
        return url_for(path, qualified=True)


def create_new_session(trans, prev_auth_session=None, user_for_new_session=None):
    """
    Create a new AuthSession for this request, possibly with a connection
    to a previous session (in `prev_auth_session`) and an existing user
    (in `user_for_new_session`).

    Caller is responsible for flushing the returned session.
    """
    auth_session = trans.app.model.AuthSession(
        is_valid=True,
        session_type="browser",
        auth_source="anonymous" if user_for_new_session is None else "galaxy_token",
        remote_host=trans.request.remote_host,
        remote_addr=trans.request.remote_addr,
        referer=trans.request.headers.get("Referer", None),
    )
    if user_for_new_session:
        # The new session should be associated with the user
        auth_session.user = user_for_new_session
        ensure_object_added_to_session(auth_session, object_in_session=user_for_new_session)
    return auth_session


def default_url_path(path):
    return os.path.abspath(os.path.join(os.path.dirname(__file__), path))


def build_url_map(app, global_conf, **local_conf):
    urlmap = URLMap()
    # Merge the global and local configurations
    conf = global_conf.copy()
    conf.update(local_conf)
    # Get cache time in seconds
    cache_time = conf.get("static_cache_time", None)
    if cache_time is not None:
        cache_time = int(cache_time)
    # Send to dynamic app by default
    urlmap["/"] = app

    def get_static_from_config(option_name, default_path, sample=None):
        config_val = conf.get(option_name)
        default = default_url_path(default_path)
        if not config_val:
            if not os.path.exists(default) and sample:
                config_val = os.path.abspath(f"{sample}")
            else:
                config_val = default
        per_host_config_option = f"{option_name}_by_host"
        per_host_config = conf.get(per_host_config_option)
        return Static(config_val, cache_time, directory_per_host=per_host_config)

    # Define static mappings from config
    static_dir = get_static_from_config("static_dir", "static/")
    static_dir_bare = static_dir.directory.rstrip("/")
    static_dist_dir = get_static_from_config(
        "static_dist_dir", default_static_dist_dir or os.path.join(static_dir_bare, "dist/")
    )
    urlmap["/static"] = static_dir
    urlmap["/static/dist"] = static_dist_dir
    urlmap["/images"] = get_static_from_config("static_images_dir", os.path.join(static_dir_bare, "images"))
    urlmap["/static/scripts"] = get_static_from_config("static_scripts_dir", os.path.join(static_dir_bare, "scripts/"))

    urlmap["/static/welcome.html"] = get_static_from_config(
        "static_welcome_html",
        os.path.join(static_dir_bare, "welcome.html"),
        sample=default_url_path("static/welcome.sample.html"),
    )
    urlmap["/favicon.ico"] = get_static_from_config(
        "static_favicon_dir",
        os.path.join(static_dir_bare, "favicon.ico"),
        sample=default_url_path("static/favicon.ico"),
    )
    urlmap["/robots.txt"] = get_static_from_config(
        "static_robots_txt", f"{static_dir_bare}/robots.txt", sample=default_url_path("static/robots.txt")
    )

    if "static_local_dir" in conf:
        urlmap["/static_local"] = Static(conf["static_local_dir"], cache_time)
    return urlmap
