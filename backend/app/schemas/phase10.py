from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from app.schemas.bad_cases import (
    AnalysisAssessment,
    BadCaseAnalysisCreate,
    BadCaseCategory,
    BadCaseCreateRequest,
    BadCaseSeverity,
    BadCaseAnalysisResponse,
    BadCaseSourceResponse,
    BadCaseSummaryResponse,
    BadCaseStatus,
    BadCaseUpdateRequest,
    BadCaseTransitionResponse,
    ImmutableArtifactReference,
    ResolutionActionResponse,
    ResolutionActionCreate,
    ResolutionActionStatus,
    ResolutionActionType,
    RootCauseCode,
    RootCauseType,
    SafeIdentifier,
    SymptomFamily,
    TransitionReason,
)
from app.schemas.explanations import EvidenceId
from app.schemas.feedback import ProfileFieldLocator
from app.services.bad_cases.taxonomy import (
    action_allowed_for_root_cause,
    category_family,
    root_cause_allowed,
)


PHASE10_REVIEW_EXPORT_VERSION = "phase10_review_export_v1"

EvidenceKind = Literal[
    "job_requirement",
    "skill",
    "project",
    "project_evidence",
    "retrieval",
    "feature",
    "ranking",
    "diagnostic",
    "comparison",
    "field_locator",
]
EvidencePurpose = Literal[
    "supports_observation",
    "disputed_reference",
    "missing_expected_evidence",
    "supports_analysis",
    "supports_verification",
]
TruncatedCollection = Literal[
    "sources",
    "evidence_links",
    "analyses",
    "resolution_actions",
    "transitions",
]


class _BadCaseCreateCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symptom_code: BadCaseCategory
    severity: BadCaseSeverity

    def to_create_request(self) -> BadCaseCreateRequest:
        return BadCaseCreateRequest.model_validate(
            self.model_dump(
                mode="python", exclude={"source_type"}, exclude_none=True
            )
        )


class FeedbackBadCaseCreateCommand(_BadCaseCreateCommand):
    source_type: Literal["feedback"]
    feedback_id: SafeIdentifier

    @model_validator(mode="after")
    def source_is_valid(self) -> "FeedbackBadCaseCreateCommand":
        self.to_create_request()
        return self


class SystemSignalBadCaseCreateCommand(_BadCaseCreateCommand):
    source_type: Literal["system_signal"]
    system_signal_id: SafeIdentifier

    @model_validator(mode="after")
    def source_is_valid(self) -> "SystemSignalBadCaseCreateCommand":
        self.to_create_request()
        return self


BadCaseCreateCommand = Annotated[
    Union[FeedbackBadCaseCreateCommand, SystemSignalBadCaseCreateCommand],
    Field(discriminator="source_type"),
]


class FeedbackBadCaseSourceCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: Literal["feedback"]
    feedback_id: SafeIdentifier

    @property
    def system_signal_id(self) -> None:
        return None


class SystemSignalBadCaseSourceCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: Literal["system_signal"]
    system_signal_id: SafeIdentifier

    @property
    def feedback_id(self) -> None:
        return None


BadCaseLinkSourceRequest = Annotated[
    Union[FeedbackBadCaseSourceCommand, SystemSignalBadCaseSourceCommand],
    Field(discriminator="source_type"),
]


class _BadCaseReviewCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_status: BadCaseStatus
    expected_revision: Annotated[StrictInt, Field(ge=0)]

    def to_update_request(self) -> BadCaseUpdateRequest:
        return BadCaseUpdateRequest.model_validate(
            self.model_dump(mode="python", exclude={"command"}, exclude_none=True)
        )


class BadCaseTransitionCommand(_BadCaseReviewCommand):
    command: Literal["transition"]
    status: BadCaseStatus
    transition_reason: TransitionReason
    verification_reference: Optional[ImmutableArtifactReference] = None
    duplicate_of_bad_case_id: Optional[SafeIdentifier] = None

    @model_validator(mode="after")
    def transition_is_valid(self) -> "BadCaseTransitionCommand":
        self.to_update_request()
        return self


class BadCaseAnalysisCommand(_BadCaseReviewCommand):
    command: Literal["analysis"]
    analysis: BadCaseAnalysisCreate
    status: Optional[BadCaseStatus] = None
    transition_reason: Optional[TransitionReason] = None

    @model_validator(mode="after")
    def analysis_command_is_valid(self) -> "BadCaseAnalysisCommand":
        self.to_update_request()
        return self


class BadCaseResolutionCommand(_BadCaseReviewCommand):
    command: Literal["resolution"]
    resolution: ResolutionActionCreate
    status: Optional[BadCaseStatus] = None
    transition_reason: Optional[TransitionReason] = None

    @model_validator(mode="after")
    def resolution_command_is_valid(self) -> "BadCaseResolutionCommand":
        self.to_update_request()
        return self


BadCaseReviewCommand = Annotated[
    Union[
        BadCaseTransitionCommand,
        BadCaseAnalysisCommand,
        BadCaseResolutionCommand,
    ],
    Field(discriminator="command"),
]


class BadCaseEvidenceLinkResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_link_id: Annotated[StrictInt, Field(gt=0)]
    explanation_run_id: Optional[SafeIdentifier] = None
    evidence_reference: Optional[EvidenceId] = None
    field_locator: Optional[ProfileFieldLocator] = None
    purpose: EvidencePurpose
    evidence_kind: Optional[EvidenceKind] = None
    candidate_id: Optional[SafeIdentifier] = None
    result_rank: Optional[Annotated[StrictInt, Field(gt=0)]] = None


class BadCaseTransitionApiResponse(BadCaseTransitionResponse):
    verification_reference: Optional[ImmutableArtifactReference] = None


class BadCaseApiDetailResponse(BadCaseSummaryResponse):
    sources: list[BadCaseSourceResponse] = Field(default_factory=list, max_length=20)
    evidence_links: list[BadCaseEvidenceLinkResponse] = Field(
        default_factory=list, max_length=100
    )
    analyses: list[BadCaseAnalysisResponse] = Field(default_factory=list, max_length=100)
    resolution_actions: list[ResolutionActionResponse] = Field(
        default_factory=list, max_length=100
    )
    transitions: list[BadCaseTransitionApiResponse] = Field(
        default_factory=list, max_length=100
    )
    child_limit: Annotated[StrictInt, Field(ge=1, le=100)]
    truncated_collections: list[TruncatedCollection] = Field(
        default_factory=list, max_length=5
    )

    @model_validator(mode="after")
    def truncation_metadata_is_canonical(self) -> "BadCaseApiDetailResponse":
        values = list(self.truncated_collections)
        if values != sorted(set(values)):
            raise ValueError("Truncated collection names must be unique and sorted")
        return self


class ReviewRootCauseExport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessment: AnalysisAssessment
    root_cause_type: RootCauseType
    root_cause_code: RootCauseCode

    @model_validator(mode="after")
    def code_matches_type(self) -> "ReviewRootCauseExport":
        if not root_cause_allowed(
            self.root_cause_type.value, self.root_cause_code.value
        ):
            raise ValueError("Export root-cause code does not belong to its type")
        return self


class ReviewResolutionActionExport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_type: ResolutionActionType
    status: ResolutionActionStatus


class Phase10ReviewExportV1(BaseModel):
    """Privacy-safe review artifact for future Phase 11 consumption."""

    model_config = ConfigDict(extra="forbid")

    contract_version: Literal[PHASE10_REVIEW_EXPORT_VERSION] = (
        PHASE10_REVIEW_EXPORT_VERSION
    )
    bad_case_id: SafeIdentifier
    match_run_id: SafeIdentifier
    match_result_id: Optional[Annotated[StrictInt, Field(gt=0)]] = None
    symptom_code: BadCaseCategory
    symptom_family: SymptomFamily
    severity: BadCaseSeverity
    status: BadCaseStatus
    source_types: list[Literal["feedback", "system_signal"]] = Field(
        min_length=1, max_length=20
    )
    root_cause_assessments: list[ReviewRootCauseExport] = Field(max_length=100)
    evidence_kinds: list[EvidenceKind] = Field(max_length=100)
    resolution_actions: list[ReviewResolutionActionExport] = Field(max_length=100)
    verification_state: Literal["not_verified", "case_specific_verified"]
    verification_reference: Optional[ImmutableArtifactReference] = None

    @model_validator(mode="after")
    def collections_are_canonical(self) -> "Phase10ReviewExportV1":
        source_values = list(self.source_types)
        evidence_values = list(self.evidence_kinds)
        analyses = [
            (item.assessment.value, item.root_cause_type.value, item.root_cause_code.value)
            for item in self.root_cause_assessments
        ]
        actions = [
            (item.action_type.value, item.status.value)
            for item in self.resolution_actions
        ]
        if source_values != sorted(set(source_values)):
            raise ValueError("Export source types must be unique and sorted")
        if evidence_values != sorted(set(evidence_values)):
            raise ValueError("Export evidence kinds must be unique and sorted")
        if analyses != sorted(set(analyses)):
            raise ValueError("Export root-cause assessments must be unique and sorted")
        if actions != sorted(set(actions)):
            raise ValueError("Export resolution actions must be unique and sorted")
        if category_family(self.symptom_code.value) != self.symptom_family.value:
            raise ValueError("Export symptom code does not belong to its family")
        verified = self.status.value == "VERIFIED"
        if verified != (self.verification_state == "case_specific_verified"):
            raise ValueError("Export verification state conflicts with BadCase status")
        if verified != (self.verification_reference is not None):
            raise ValueError(
                "Export verification reference conflicts with BadCase status"
            )
        supporting_root_causes = {
            item.root_cause_code.value
            for item in self.root_cause_assessments
            if item.assessment.value in {"supported", "confirmed"}
        }
        if any(
            not any(
                action_allowed_for_root_cause(root_cause, action.action_type.value)
                for root_cause in supporting_root_causes
            )
            for action in self.resolution_actions
        ):
            raise ValueError(
                "Export resolution action is incompatible with supported root-cause history"
            )
        return self


__all__ = [
    "BadCaseApiDetailResponse",
    "BadCaseAnalysisCommand",
    "BadCaseCreateCommand",
    "BadCaseEvidenceLinkResponse",
    "BadCaseLinkSourceRequest",
    "BadCaseResolutionCommand",
    "BadCaseReviewCommand",
    "BadCaseTransitionCommand",
    "BadCaseTransitionApiResponse",
    "FeedbackBadCaseSourceCommand",
    "FeedbackBadCaseCreateCommand",
    "PHASE10_REVIEW_EXPORT_VERSION",
    "Phase10ReviewExportV1",
    "ReviewResolutionActionExport",
    "ReviewRootCauseExport",
    "SystemSignalBadCaseSourceCommand",
    "SystemSignalBadCaseCreateCommand",
]
