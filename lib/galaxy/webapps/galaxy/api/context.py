import logging
from typing import (
    Any,
)

from galaxy.managers.configuration import ConfigurationManager
from galaxy.managers.context import ProvidesUserContext
from galaxy.managers.users import CurrentUserSerializer
from galaxy.schema import SerializationParams
from galaxy.schema.schema import Model
from galaxy.webapps.galaxy.api import (
    depends,
    DependsOnTrans,
    Router,
)

log = logging.getLogger(__name__)

router = Router(tags=["context"])


class ContextResponse(Model):
    config: dict[str, Any]
    user: dict[str, Any]


@router.cbv
class FastAPIContext:
    configuration_manager: ConfigurationManager = depends(ConfigurationManager)
    user_serializer: CurrentUserSerializer = depends(CurrentUserSerializer)

    @router.get("/context", summary="Return bootstrapped client context")
    def index(self, trans: ProvidesUserContext = DependsOnTrans) -> ContextResponse:
        config = self.configuration_manager.get_configuration(trans, SerializationParams(view="all"))
        return ContextResponse(config=config, user=self.user_serializer.serialize_to_view(trans.user, "detailed"))
