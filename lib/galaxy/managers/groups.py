from sqlalchemy import (
    false,
    select,
)
from sqlalchemy.orm import Session

from galaxy import model
from galaxy.exceptions import (
    Conflict,
    ObjectAttributeMissingException,
    ObjectNotFound,
    RequestParameterInvalidException,
)
from galaxy.managers.context import ProvidesAppContext
from galaxy.managers.roles import get_roles_by_ids
from galaxy.managers.users import get_users_by_ids
from galaxy.model import Group
from galaxy.model.base import transaction
from galaxy.model.scoped_session import galaxy_scoped_session
from galaxy.schema.fields import Security
from galaxy.schema.groups import GroupCreatePayload
from galaxy.structured_app import MinimalManagerApp


class GroupsManager:
    """Interface/service object shared by controllers for interacting with groups."""

    def __init__(self, app: MinimalManagerApp) -> None:
        self._app = app

    def index(self, trans: ProvidesAppContext):
        """
        Displays a collection (list) of groups.
        """
        rval = []
        for group in get_not_deleted_groups(trans.sa_session):
            item = group.to_dict()
            encoded_id = Security.security.encode_id(group.id)
            item["url"] = self._url_for(trans, "group", id=encoded_id)
            rval.append(item)
        return rval

    def create(self, trans: ProvidesAppContext, payload: GroupCreatePayload):
        """
        Creates a new group.
        """
        sa_session = trans.sa_session
        name = payload.name
        if name is None:
            raise ObjectAttributeMissingException("Missing required name")
        self._check_duplicated_group_name(sa_session, name)

        group = model.Group(name=name)
        sa_session.add(group)
        user_ids = payload.user_ids
        users = get_users_by_ids(sa_session, user_ids)
        role_ids = payload.role_ids
        roles = get_roles_by_ids(sa_session, role_ids)
        trans.app.security_agent.set_entity_group_associations(groups=[group], roles=roles, users=users)
        with transaction(sa_session):
            sa_session.commit()

        encoded_id = Security.security.encode_id(group.id)
        item = group.to_dict(view="element")
        item["url"] = self._url_for(trans, "group", id=encoded_id)
        return [item]

    def show(self, trans: ProvidesAppContext, group_id: int):
        """
        Displays information about a group.
        """
        encoded_id = Security.security.encode_id(group_id)
        group = self._get_group(trans.sa_session, group_id)
        item = group.to_dict(view="element")
        item["url"] = self._url_for(trans, "group", id=encoded_id)
        item["users_url"] = self._url_for(trans, "group_users", group_id=encoded_id)
        item["roles_url"] = self._url_for(trans, "group_roles", group_id=encoded_id)
        return item

    def update(self, trans: ProvidesAppContext, group_id: int, payload: GroupCreatePayload):
        """
        Modifies a group.
        """
        sa_session = trans.sa_session
        group = self._get_group(sa_session, group_id)
        if name := payload.name:
            self._check_duplicated_group_name(sa_session, name)
            group.name = name
            sa_session.add(group)
        user_ids = payload.user_ids
        users = get_users_by_ids(sa_session, user_ids)
        role_ids = payload.role_ids
        roles = get_roles_by_ids(sa_session, role_ids)
        self._app.security_agent.set_entity_group_associations(
            groups=[group], roles=roles, users=users, delete_existing_assocs=False
        )
        with transaction(sa_session):
            sa_session.commit()

        encoded_id = Security.security.encode_id(group.id)
        item = group.to_dict(view="element")
        item["url"] = self._url_for(trans, "show_group", group_id=encoded_id)
        return item

    def delete(self, trans: ProvidesAppContext, group_id: int):
        group = self._get_group(trans.sa_session, group_id)
        group.deleted = True
        trans.sa_session.add(group)
        with transaction(trans.sa_session):
            trans.sa_session.commit()

    def purge(self, trans: ProvidesAppContext, group_id: int):
        group = self._get_group(trans.sa_session, group_id)
        if not group.deleted:
            raise RequestParameterInvalidException(
                f"Group '{group.name}' has not been deleted, so it cannot be purged."
            )
        # Delete UserGroupAssociations
        for uga in group.users:
            trans.sa_session.delete(uga)
        # Delete GroupRoleAssociations
        for gra in group.roles:
            trans.sa_session.delete(gra)
        with transaction(trans.sa_session):
            trans.sa_session.commit()

    def undelete(self, trans: ProvidesAppContext, group_id: int):
        group = self._get_group(trans.sa_session, group_id)
        if not group.deleted:
            raise RequestParameterInvalidException(
                f"Group '{group.name}' has not been deleted, so it cannot be undeleted."
            )
        group.deleted = False
        trans.sa_session.add(group)
        with transaction(trans.sa_session):
            trans.sa_session.commit()

    def _url_for(self, trans, name, **kwargs):
        return trans.url_builder(name, **kwargs)

    def _check_duplicated_group_name(self, sa_session: galaxy_scoped_session, group_name: str) -> None:
        if get_group_by_name(sa_session, group_name):
            raise Conflict(f"A group with name '{group_name}' already exists")

    def _get_group(self, sa_session: galaxy_scoped_session, group_id: int) -> model.Group:
        group = sa_session.get(model.Group, group_id)
        if group is None:
            raise ObjectNotFound("Group with the provided id was not found.")
        return group


def get_group_by_name(session: Session, name: str):
    stmt = select(Group).filter(Group.name == name).limit(1)
    return session.scalars(stmt).first()


def get_not_deleted_groups(session: Session):
    stmt = select(Group).where(Group.deleted == false())
    return session.scalars(stmt)
