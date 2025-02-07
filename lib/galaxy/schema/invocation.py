from datetime import datetime
from enum import Enum
from typing import (
    Any,
    Dict,
    Generic,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    UUID1,
    UUID4,
)
from pydantic.json_schema import GenerateJsonSchema
from typing_extensions import (
    Annotated,
    Literal,
)

from galaxy.schema import schema
from galaxy.schema.fields import (
    EncodedDatabaseIdField,
    literal_to_value,
    ModelClassField,
)
from galaxy.schema.schema import (
    CreateTimeField,
    DataItemSourceType,
    IMPLICIT_COLLECTION_JOBS_MODEL_CLASS,
    INVOCATION_MODEL_CLASS,
    INVOCATION_STEP_MODEL_CLASS,
    JOB_MODEL_CLASS,
    JobState,
    Model,
    UpdateTimeField,
    WithModelClass,
)

INVOCATION_STEP_OUTPUT_SRC = Literal["hda"]
INVOCATION_STEP_COLLECTION_OUTPUT_SRC = Literal["hdca"]
REPORT_RENDER_FORMAT_MARKDOWN = Literal["markdown"]


InvocationStepActionField = Field(
    title="Action",
    description="Whether to take action on the invocation step.",
)

InvocationIdField: EncodedDatabaseIdField = Field(
    default=...,
    title="ID",
    description="The encoded ID of the workflow invocation.",
)


class WarningReason(str, Enum):
    workflow_output_not_found = "workflow_output_not_found"


class FailureReason(str, Enum):
    dataset_failed = "dataset_failed"
    collection_failed = "collection_failed"
    job_failed = "job_failed"
    output_not_found = "output_not_found"
    expression_evaluation_failed = "expression_evaluation_failed"
    when_not_boolean = "when_not_boolean"
    unexpected_failure = "unexpected_failure"


class CancelReason(str, Enum):
    """Possible reasons for a cancelled workflow."""

    history_deleted = "history_deleted"
    user_request = "user_request"
    cancelled_on_review = "cancelled_on_review"


DatabaseIdT = TypeVar("DatabaseIdT")

ref_to_name = {}


class InvocationMessageBase(BaseModel):
    reason: Union[CancelReason, FailureReason, WarningReason]
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @classmethod
    def model_parametrized_name(cls, params: Tuple[Type[Any], ...]) -> str:
        suffix = "Response" if params[0] is EncodedDatabaseIdField else "Incoming"
        class_name = cls.__name__.split("Generic", 1)[-1]
        return f"{class_name}{suffix}"

    @classmethod
    def __get_pydantic_core_schema__(cls, *args, **kwargs):
        result = super().__get_pydantic_core_schema__(*args, **kwargs)
        ref_to_name[result["ref"]] = cls.__name__
        return result


class CustomJsonSchema(GenerateJsonSchema):
    def get_defs_ref(self, core_mode_ref):
        full_def = super().get_defs_ref(core_mode_ref)
        choices = self._prioritized_defsref_choices[full_def]
        ref, mode = core_mode_ref
        if ref in ref_to_name:
            for i, choice in enumerate(choices):
                choices[i] = choice.replace(choices[0], ref_to_name[ref])  # type: ignore[call-overload]
        return full_def


class GenericInvocationCancellationReviewFailed(InvocationMessageBase, Generic[DatabaseIdT]):
    reason: Literal[CancelReason.cancelled_on_review]
    workflow_step_id: int = Field(
        ...,
        description="Workflow step id of paused step that did not pass review.",
        validation_alias="workflow_step_index",
    )


class GenericInvocationCancellationHistoryDeleted(InvocationMessageBase, Generic[DatabaseIdT]):
    reason: Literal[CancelReason.history_deleted]
    history_id: DatabaseIdT = Field(..., title="History ID", description="History ID of history that was deleted.")


class GenericInvocationCancellationUserRequest(InvocationMessageBase, Generic[DatabaseIdT]):
    reason: Literal[CancelReason.user_request]


class InvocationFailureMessageBase(InvocationMessageBase, Generic[DatabaseIdT]):
    workflow_step_id: int = Field(
        ..., description="Workflow step id of step that failed.", validation_alias="workflow_step_index"
    )


class GenericInvocationFailureDatasetFailed(InvocationFailureMessageBase[DatabaseIdT], Generic[DatabaseIdT]):
    reason: Literal[FailureReason.dataset_failed]
    hda_id: DatabaseIdT = Field(
        ..., title="HistoryDatasetAssociation ID", description="HistoryDatasetAssociation ID that relates to failure."
    )
    dependent_workflow_step_id: Optional[int] = Field(None, description="Workflow step id of step that caused failure.")


class GenericInvocationFailureCollectionFailed(InvocationFailureMessageBase[DatabaseIdT], Generic[DatabaseIdT]):
    reason: Literal[FailureReason.collection_failed]
    hdca_id: DatabaseIdT = Field(
        ...,
        title="HistoryDatasetCollectionAssociation ID",
        description="HistoryDatasetCollectionAssociation ID that relates to failure.",
    )
    dependent_workflow_step_id: int = Field(
        ...,
        description="Workflow step id of step that caused failure.",
        validation_alias="dependent_workflow_step_index",
    )


class GenericInvocationFailureJobFailed(InvocationFailureMessageBase[DatabaseIdT], Generic[DatabaseIdT]):
    reason: Literal[FailureReason.job_failed]
    job_id: DatabaseIdT = Field(..., title="Job ID", description="Job ID that relates to failure.")
    dependent_workflow_step_id: int = Field(
        ...,
        description="Workflow step id of step that caused failure.",
        validation_alias="dependent_workflow_step_index",
    )


class GenericInvocationFailureOutputNotFound(InvocationFailureMessageBase[DatabaseIdT], Generic[DatabaseIdT]):
    reason: Literal[FailureReason.output_not_found]
    output_name: str = Field(..., title="Tool or module output name that was referenced but not produced")
    dependent_workflow_step_id: int = Field(
        ...,
        description="Workflow step id of step that caused failure.",
        validation_alias="dependent_workflow_step_index",
    )


class GenericInvocationFailureExpressionEvaluationFailed(
    InvocationFailureMessageBase[DatabaseIdT], Generic[DatabaseIdT]
):
    reason: Literal[FailureReason.expression_evaluation_failed]
    details: Optional[str] = Field(None, description="May contain details to help troubleshoot this problem.")


class GenericInvocationFailureWhenNotBoolean(InvocationFailureMessageBase[DatabaseIdT], Generic[DatabaseIdT]):
    reason: Literal[FailureReason.when_not_boolean]
    details: str = Field(..., description="Contains details to help troubleshoot this problem.")


class GenericInvocationUnexpectedFailure(InvocationMessageBase, Generic[DatabaseIdT]):
    reason: Literal[FailureReason.unexpected_failure]
    details: Optional[str] = Field(None, description="May contains details to help troubleshoot this problem.")
    workflow_step_id: Optional[int] = Field(
        None, description="Workflow step id of step that failed.", validation_alias="workflow_step_index"
    )


class GenericInvocationWarning(InvocationMessageBase, Generic[DatabaseIdT]):
    reason: WarningReason = Field(..., title="Failure Reason", description="Reason for warning")
    workflow_step_id: Optional[int] = Field(
        None, title="Workflow step id of step that caused a warning.", validation_alias="workflow_step_index"
    )


class GenericInvocationEvaluationWarningWorkflowOutputNotFound(
    GenericInvocationWarning[DatabaseIdT], Generic[DatabaseIdT]
):
    reason: Literal[WarningReason.workflow_output_not_found]
    workflow_step_id: int = Field(
        ..., title="Workflow step id of step that caused a warning.", validation_alias="workflow_step_index"
    )
    output_name: str = Field(
        ..., description="Output that was designated as workflow output but that has not been found"
    )


InvocationCancellationReviewFailed = GenericInvocationCancellationReviewFailed[int]
InvocationCancellationHistoryDeleted = GenericInvocationCancellationHistoryDeleted[int]
InvocationCancellationUserRequest = GenericInvocationCancellationUserRequest[int]
InvocationFailureDatasetFailed = GenericInvocationFailureDatasetFailed[int]
InvocationFailureCollectionFailed = GenericInvocationFailureCollectionFailed[int]
InvocationFailureJobFailed = GenericInvocationFailureJobFailed[int]
InvocationFailureOutputNotFound = GenericInvocationFailureOutputNotFound[int]
InvocationFailureExpressionEvaluationFailed = GenericInvocationFailureExpressionEvaluationFailed[int]
InvocationFailureWhenNotBoolean = GenericInvocationFailureWhenNotBoolean[int]
InvocationUnexpectedFailure = GenericInvocationUnexpectedFailure[int]
InvocationWarningWorkflowOutputNotFound = GenericInvocationEvaluationWarningWorkflowOutputNotFound[int]

InvocationMessageUnion = Union[
    InvocationCancellationReviewFailed,
    InvocationCancellationHistoryDeleted,
    InvocationCancellationUserRequest,
    InvocationFailureDatasetFailed,
    InvocationFailureCollectionFailed,
    InvocationFailureJobFailed,
    InvocationFailureOutputNotFound,
    InvocationFailureExpressionEvaluationFailed,
    InvocationFailureWhenNotBoolean,
    InvocationUnexpectedFailure,
    InvocationWarningWorkflowOutputNotFound,
]

InvocationCancellationReviewFailedResponseModel = GenericInvocationCancellationReviewFailed[EncodedDatabaseIdField]
InvocationCancellationHistoryDeletedResponseModel = GenericInvocationCancellationHistoryDeleted[EncodedDatabaseIdField]
InvocationCancellationUserRequestResponseModel = GenericInvocationCancellationUserRequest[EncodedDatabaseIdField]
InvocationFailureDatasetFailedResponseModel = GenericInvocationFailureDatasetFailed[EncodedDatabaseIdField]
InvocationFailureCollectionFailedResponseModel = GenericInvocationFailureCollectionFailed[EncodedDatabaseIdField]
InvocationFailureJobFailedResponseModel = GenericInvocationFailureJobFailed[EncodedDatabaseIdField]
InvocationFailureOutputNotFoundResponseModel = GenericInvocationFailureOutputNotFound[EncodedDatabaseIdField]
InvocationFailureExpressionEvaluationFailedResponseModel = GenericInvocationFailureExpressionEvaluationFailed[
    EncodedDatabaseIdField
]
InvocationFailureWhenNotBooleanResponseModel = GenericInvocationFailureWhenNotBoolean[EncodedDatabaseIdField]
InvocationUnexpectedFailureResponseModel = GenericInvocationUnexpectedFailure[EncodedDatabaseIdField]
InvocationWarningWorkflowOutputNotFoundResponseModel = GenericInvocationEvaluationWarningWorkflowOutputNotFound[
    EncodedDatabaseIdField
]

InvocationMessageResponseUnion = Annotated[
    Union[
        InvocationCancellationReviewFailedResponseModel,
        InvocationCancellationHistoryDeletedResponseModel,
        InvocationCancellationUserRequestResponseModel,
        InvocationFailureDatasetFailedResponseModel,
        InvocationFailureCollectionFailedResponseModel,
        InvocationFailureJobFailedResponseModel,
        InvocationFailureOutputNotFoundResponseModel,
        InvocationFailureExpressionEvaluationFailedResponseModel,
        InvocationFailureWhenNotBooleanResponseModel,
        InvocationUnexpectedFailureResponseModel,
        InvocationWarningWorkflowOutputNotFoundResponseModel,
    ],
    Field(discriminator="reason"),
]


class InvocationMessageResponseModel(RootModel):
    root: InvocationMessageResponseUnion
    model_config = ConfigDict(from_attributes=True)


class InvocationState(str, Enum):
    NEW = "new"  # Brand new workflow invocation... maybe this should be same as READY
    READY = "ready"  # Workflow ready for another iteration of scheduling.
    SCHEDULED = "scheduled"  # Workflow has been scheduled.
    CANCELLED = "cancelled"
    CANCELLING = "cancelling"  # invocation scheduler will cancel job in next iteration.
    FAILED = "failed"


class InvocationStepState(str, Enum):
    NEW = "new"  # Brand new workflow invocation step
    READY = "ready"  # Workflow invocation step ready for another iteration of scheduling.
    SCHEDULED = "scheduled"  # Workflow invocation step has been scheduled.
    # CANCELLED = 'cancelled',  TODO: implement and expose
    # FAILED = 'failed',  TODO: implement and expose


class ExtendedInvocationStepState(str, Enum):
    NEW = "new"  # Brand new workflow invocation step
    READY = "ready"  # Workflow invocation step ready for another iteration of scheduling.
    SCHEDULED = "scheduled"  # Workflow invocation step has been scheduled.
    # CANCELLED = 'cancelled',  TODO: implement and expose
    # FAILED = 'failed',  TODO: implement and expose
    OK = "ok"  # Workflow invocation step has completed successfully - TODO: is this a correct description?


class InvocationStepOutput(Model):
    src: INVOCATION_STEP_OUTPUT_SRC = Field(
        literal_to_value(INVOCATION_STEP_OUTPUT_SRC),
        title="src",
        description="The source model of the output.",
    )
    id: EncodedDatabaseIdField = Field(
        ...,
        title="Dataset ID",
        description="Dataset ID of the workflow step output.",
    )
    uuid: Optional[UUID4] = Field(
        None,
        title="UUID",
        description="Universal unique identifier of the workflow step output dataset.",
    )


class InvocationStepCollectionOutput(Model):
    src: INVOCATION_STEP_COLLECTION_OUTPUT_SRC = Field(
        literal_to_value(INVOCATION_STEP_COLLECTION_OUTPUT_SRC),
        title="src",
        description="The source model of the output.",
    )
    id: EncodedDatabaseIdField = Field(
        ...,
        title="Dataset Collection ID",
        description="Dataset Collection ID of the workflow step output.",
    )


class InvocationStep(Model, WithModelClass):
    """Information about workflow invocation step"""

    model_class: INVOCATION_STEP_MODEL_CLASS = ModelClassField(INVOCATION_STEP_MODEL_CLASS)
    id: Annotated[EncodedDatabaseIdField, Field(..., title="Invocation Step ID")]
    update_time: Optional[datetime] = schema.UpdateTimeField
    job_id: Optional[
        Annotated[
            EncodedDatabaseIdField,
            Field(
                default=None,
                title="Job ID",
                description="The encoded ID of the job associated with this workflow invocation step.",
            ),
        ]
    ]
    workflow_step_id: Annotated[
        EncodedDatabaseIdField,
        Field(
            ...,
            title="Workflow step ID",
            description="The encoded ID of the workflow step associated with this workflow invocation step.",
        ),
    ]
    subworkflow_invocation_id: Optional[
        Annotated[
            EncodedDatabaseIdField,
            Field(
                default=None,
                title="Subworkflow invocation ID",
                description="The encoded ID of the subworkflow invocation.",
            ),
        ]
    ]
    # TODO The state can differ from InvocationStepState is this intended?
    # InvocationStepState is equal to the states attribute of the WorkflowInvocationStep class
    state: Optional[ExtendedInvocationStepState] = Field(
        default=None,
        title="State of the invocation step",
        description="Describes where in the scheduling process the workflow invocation step is.",
    )
    action: Optional[bool] = InvocationStepActionField
    order_index: int = Field(
        ...,
        title="Order index",
        description="The index of the workflow step in the workflow.",
    )
    workflow_step_label: Optional[str] = Field(
        default=None,
        title="Step label",
        description="The label of the workflow step",
    )
    workflow_step_uuid: Optional[UUID4] = Field(
        None,
        title="UUID",
        description="Universal unique identifier of the workflow step.",
    )
    outputs: Dict[str, InvocationStepOutput] = Field(
        {},
        title="Outputs",
        description="The outputs of the workflow invocation step.",
    )
    output_collections: Dict[str, InvocationStepCollectionOutput] = Field(
        {},
        title="Output collections",
        description="The dataset collection outputs of the workflow invocation step.",
    )
    jobs: List[schema.JobBaseModel] = Field(
        [],
        title="Jobs",
        description="Jobs associated with the workflow invocation step.",
    )


class InvocationReport(Model, WithModelClass):
    """Report describing workflow invocation"""

    render_format: REPORT_RENDER_FORMAT_MARKDOWN = Field(
        literal_to_value(REPORT_RENDER_FORMAT_MARKDOWN),
        title="Render format",
        description="Format of the invocation report.",
    )
    markdown: Optional[str] = Field(
        default="",
        title="Markdown",
        description="Raw galaxy-flavored markdown contents of the report.",
    )
    invocation_markdown: Optional[str] = Field(
        default="",
        title="Markdown",
        description="Raw galaxy-flavored markdown contents of the report.",
    )
    model_class: schema.INVOCATION_REPORT_MODEL_CLASS = ModelClassField(schema.INVOCATION_REPORT_MODEL_CLASS)
    id: EncodedDatabaseIdField = Field(
        ...,
        title="Workflow ID",
        description="The workflow this invocation has been triggered for.",
    )
    username: str = Field(
        ...,
        title="Username",
        description="The name of the user who owns this report.",
    )
    title: str = Field(
        ...,
        title="Title",
        description="The name of the report.",
    )
    generate_time: Optional[str] = schema.GenerateTimeField
    generate_version: Optional[str] = schema.GenerateVersionField
    model_config = ConfigDict(extra="allow")


class InvocationUpdatePayload(Model):
    action: bool = InvocationStepActionField


class InvocationIOBase(Model):
    # TODO - resolve
    # the tests in test/integration/test_workflow_tasks.py ,
    # between line 42 and 56 fail, if this id is not allowed be None
    # They all fail, when trying to populate the response of the show_invocation operation
    # Is it intended to allow None here?
    id: Optional[EncodedDatabaseIdField] = Field(
        default=None, title="ID", description="The encoded ID of the dataset/dataset collection."
    )
    workflow_step_id: EncodedDatabaseIdField = Field(
        ...,
        title="Workflow step ID",
        description="The encoded ID of the workflow step associated with the dataset/dataset collection.",
    )


class InvocationInput(InvocationIOBase):
    label: Optional[str] = Field(
        default=None,
        title="Label",
        description="Label of the workflow step associated with the input dataset/dataset collection.",
    )
    src: Union[Literal[DataItemSourceType.hda], Literal[DataItemSourceType.hdca]] = Field(
        default=..., title="Source", description="Source type of the input dataset/dataset collection."
    )


class InvocationInputParameter(Model):
    # TODO - Change the type of parameter_value, when all valid types are known
    parameter_value: Any = Field(default=..., title="Parameter value", description="Value of the input parameter.")
    label: str = Field(
        default=..., title="Label", description="Label of the workflow step associated with the input parameter."
    )
    workflow_step_id: EncodedDatabaseIdField = Field(
        default=...,
        title="Workflow step ID",
        description="The encoded ID of the workflow step associated with the input parameter.",
    )


class InvocationOutput(InvocationIOBase):
    src: Literal[DataItemSourceType.hda] = Field(
        default=..., title="Source", description="Source model of the output dataset."
    )


class InvocationOutputCollection(InvocationIOBase):
    src: Literal[DataItemSourceType.hdca] = Field(
        default=..., title="Source", description="Source model of the output dataset collection."
    )


class WorkflowInvocationCollectionView(Model, WithModelClass):
    id: EncodedDatabaseIdField = InvocationIdField
    create_time: datetime = CreateTimeField
    update_time: datetime = UpdateTimeField
    workflow_id: EncodedDatabaseIdField = Field(
        title="Workflow ID", description="The encoded Workflow ID associated with the invocation."
    )
    history_id: EncodedDatabaseIdField = Field(
        default=...,
        title="History ID",
        description="The encoded ID of the history associated with the invocation.",
    )
    # The uuid version here is 1, which deviates from the other UUIDs used as they are version 4.
    uuid: Optional[Union[UUID4, UUID1]] = Field(
        default=None, title="UUID", description="Universal unique identifier of the workflow invocation."
    )
    state: InvocationState = Field(default=..., title="Invocation state", description="State of workflow invocation.")
    model_class: INVOCATION_MODEL_CLASS = ModelClassField(INVOCATION_MODEL_CLASS)


class WorkflowInvocationElementView(WorkflowInvocationCollectionView):
    steps: List[InvocationStep] = Field(default=..., title="Steps", description="Steps of the workflow invocation.")
    inputs: Dict[str, InvocationInput] = Field(
        default=..., title="Inputs", description="Input datasets/dataset collections of the workflow invocation."
    )
    input_step_parameters: Dict[str, InvocationInputParameter] = Field(
        default=..., title="Input step parameters", description="Input step parameters of the workflow invocation."
    )
    outputs: Dict[str, InvocationOutput] = Field(
        default=..., title="Outputs", description="Output datasets of the workflow invocation."
    )
    output_collections: Dict[str, InvocationOutputCollection] = Field(
        default=...,
        title="Output collections",
        description="Output dataset collections of the workflow invocation.",
    )
    output_values: Dict[str, Any] = Field(
        default=..., title="Output values", description="Output values of the workflow invocation."
    )
    messages: List[InvocationMessageResponseUnion] = Field(
        default=...,
        title="Messages",
        description="A list of messages about why the invocation did not succeed.",
    )


class WorkflowInvocationResponse(RootModel):
    root: Annotated[
        Union[WorkflowInvocationElementView, WorkflowInvocationCollectionView], Field(union_mode="left_to_right")
    ]


class InvocationJobsSummaryBaseModel(Model):
    id: EncodedDatabaseIdField = InvocationIdField
    states: Dict[JobState, int] = Field(
        default=..., title="States", description="The states of all the jobs related to the Invocation."
    )
    populated_state: JobState = Field(
        default=...,
        title="Populated state",
        description="The absolute state of all the jobs related to the Invocation.",
    )


class InvocationJobsResponse(InvocationJobsSummaryBaseModel):
    model: INVOCATION_MODEL_CLASS


class InvocationStepJobsResponseStepModel(InvocationJobsSummaryBaseModel):
    model: INVOCATION_STEP_MODEL_CLASS


class InvocationStepJobsResponseJobModel(InvocationJobsSummaryBaseModel):
    model: JOB_MODEL_CLASS


class InvocationStepJobsResponseCollectionJobsModel(InvocationJobsSummaryBaseModel):
    model: IMPLICIT_COLLECTION_JOBS_MODEL_CLASS
