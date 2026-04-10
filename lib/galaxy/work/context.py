import abc
from typing import (
    Any,
    Literal,
    Optional,
    TYPE_CHECKING,
)

from sqlalchemy import select
from starlette.datastructures import URL

from galaxy import util
from galaxy.managers.context import ProvidesHistoryContext
from galaxy.model import History

if TYPE_CHECKING:
    from galaxy.model import (
        AuthSession,
        GalaxySession,
        History,
        Role,
        User,
    )


class WorkRequestContext(ProvidesHistoryContext):
    """Stripped down implementation of Galaxy web transaction god object for
    work request handling outside of web threads - uses mix-ins shared with
    GalaxyWebTransaction to provide app, user, and history context convenience
    methods - but nothing related to HTTP handling, mako views, etc....

    Things that only need app shouldn't be consuming trans - but there is a
    need for actions potentially tied to users and histories and  hopefully
    this can define that stripped down interface providing access to user and
    history information - but not dealing with web request and response
    objects.
    """

    def __init__(
        self,
        app,
        user=None,
        actor_user=None,
        history: Optional["History"] = None,
        workflow_building_mode=False,
        url_builder=None,
        auth_session: Optional["AuthSession"] = None,
        galaxy_session: Optional["GalaxySession"] = None,
        auth_source: Optional[
            Literal["anonymous", "session", "galaxy_token", "api_key", "external_oidc", "remote_user", "api", "unknown"]
        ] = None,
    ):
        self._app = app
        self.__user = user
        self._actor_user = actor_user or user
        self.__user_current_roles: Optional[list[Role]] = None
        self.__history = history
        self._url_builder = url_builder
        self._short_term_cache: dict[tuple[str, ...], Any] = {}
        self.workflow_building_mode = workflow_building_mode
        self.auth_session = auth_session
        self.galaxy_session = galaxy_session
        self._auth_source = auth_source

    def set_user_context(self, user: Optional["User"], actor_user: Optional["User"] = None) -> None:
        self.__user = user
        self._actor_user = actor_user if actor_user is not None else user
        self.__user_current_roles = None

    def clear_user_context(self) -> None:
        self.set_user_context(None)

    @property
    def app(self):
        return self._app

    @property
    def url_builder(self):
        return self._url_builder

    def get_history(self, create=False, most_recent=False):
        history = self.__history
        if history is None and self.auth_session is not None:
            history = self.auth_session.current_history
        if history is None and most_recent:
            history = self.get_most_recent_history()
        if history is None and util.string_as_bool(create):
            history = self.get_or_create_default_history()
        return history

    @property
    def history(self):
        return self.get_history()

    def get_user(self):
        """Return the current user if logged in or None."""
        if self.__user is not None:
            return self.__user
        if self.auth_session is not None:
            return self.auth_session.user
        if self.galaxy_session is not None:
            return self.galaxy_session.user
        return None

    def get_current_user_roles(self):
        if self.__user_current_roles is None:
            self.__user_current_roles = super().get_current_user_roles()
        return self.__user_current_roles

    def get_galaxy_session(self):
        return self.galaxy_session

    def set_history(self, history):
        if history and not history.deleted and self.auth_session:
            self.auth_session.current_history = history
            self.sa_session.add(self.auth_session)
        self.sa_session.commit()

    def get_or_create_default_history(self):
        """Gets or creates a default history and associates it with the current session."""
        assert self.auth_session

        history = self.auth_session.current_history
        if history and not history.deleted:
            return history

        if user := self.auth_session.user:
            stmt = select(History).filter_by(user=user, name=History.default_name, deleted=False)
            unnamed_histories = self.sa_session.scalars(stmt)
            for history in unnamed_histories:
                if history.empty:
                    self.set_history(history)
                    return history

        if self.app.config.get("require_login", False) and not self.user:
            return None

        return self.new_history()

    def get_most_recent_history(self):
        """Return the most recently updated history for the current user."""
        user = self.get_user()
        if not user:
            return None
        stmt = select(History).filter_by(user=user, deleted=False).order_by(History.update_time.desc()).limit(1)
        recent_history = self.sa_session.scalars(stmt).first()
        if recent_history is not None:
            self.set_history(recent_history)
        return recent_history

    def new_history(self, name: Optional[str] = None) -> History:
        """Create a new history and associate it with the current session."""
        history = History()
        if name:
            history.name = name
        self.auth_session.current_history = history
        if self.auth_session.user:
            history.user = self.auth_session.user
        history.genome_build = self.app.genome_builds.default_value
        self.app.security_agent.history_set_default_permissions(history)
        self.sa_session.add_all((self.auth_session, history))
        self.sa_session.commit()
        return history

    def set_user(self, user):
        """Set the current user."""
        raise NotImplementedError("Cannot change users from a work request context.")

    user = property(get_user, set_user)


class GalaxyAbstractRequest:
    """Abstract interface to provide access to some request properties."""

    @property
    @abc.abstractmethod
    def base(self) -> str:
        """Base URL of the request."""

    @property
    @abc.abstractmethod
    def url_path(self) -> str:
        """Base with optional prefix added."""

    @property
    @abc.abstractmethod
    def host(self) -> str:
        """The host address."""

    @property
    @abc.abstractmethod
    def is_secure(self) -> bool:
        """Was this a secure (https) request."""

    @abc.abstractmethod
    def get_cookie(self, name):
        """Return cookie."""

    @property
    @abc.abstractmethod
    def url(self) -> URL:
        """Full URL of the request."""


class GalaxyAbstractResponse:
    """Abstract interface to provide access to some response utilities."""

    @property
    @abc.abstractmethod
    def headers(self) -> dict:
        """The response headers."""

    def set_content_type(self, content_type: str):
        """
        Sets the Content-Type header
        """
        self.headers["content-type"] = content_type

    def get_content_type(self):
        return self.headers.get("content-type", None)

    @abc.abstractmethod
    def set_cookie(
        self,
        key: str,
        value: str = "",
        max_age: Optional[int] = None,
        expires: Optional[int] = None,
        path: str = "/",
        domain: Optional[str] = None,
        secure: bool = False,
        httponly: bool = False,
        samesite: Optional[Literal["lax", "strict", "none"]] = "lax",
    ) -> None:
        """Set a cookie."""


class SessionRequestContext(WorkRequestContext):
    """Like WorkRequestContext, but provides access to request."""

    def __init__(self, **kwargs):
        self.__request: GalaxyAbstractRequest = kwargs.pop("request")
        self.__response: GalaxyAbstractResponse = kwargs.pop("response")
        super().__init__(**kwargs)

    @property
    def host(self):
        return self.__request.host

    @property
    def request(self) -> GalaxyAbstractRequest:
        return self.__request

    @property
    def response(self) -> GalaxyAbstractResponse:
        return self.__response

    def get_galaxy_session(self):
        return self.galaxy_session

    def set_history(self, history):
        if history and not history.deleted and self.galaxy_session:
            self.galaxy_session.current_history = history
        if history and not history.deleted and self.auth_session:
            self.auth_session.current_history = history
            self.sa_session.add(self.auth_session)
        if self.galaxy_session:
            self.sa_session.add(self.galaxy_session)
        self.sa_session.commit()


def proxy_work_context_for_history(
    trans: ProvidesHistoryContext, history: Optional["History"] = None, workflow_building_mode=False
) -> WorkRequestContext:
    """Create a WorkContext for supplied context with potentially different history.

    This provides semi-structured access to a transaction/work context with a supplied target
    history that is different from the user's current history (which also might change during
    the request).
    """
    return WorkRequestContext(
        app=trans.app,
        user=trans.user,
        actor_user=trans.actor_user,
        history=history or trans.history,
        url_builder=trans.url_builder,
        workflow_building_mode=workflow_building_mode,
        auth_session=trans.auth_session,
        galaxy_session=trans.galaxy_session,
        auth_source=trans.auth_source,
    )
