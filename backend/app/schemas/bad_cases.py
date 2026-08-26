from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, List, Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StringConstraints,
    model_validator,
)

from app.services.bad_cases.taxonomy import (
    BAD_CASE_CONTRACT_VERSION,
    BAD_CASE_TAXONOMY_VERSION,
    category_family,
    root_cause_allowed,
    transition_reason_allowed,
)


SafeIdentifier = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=160,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    ),
]
SafeSummary = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1000),
]
StrictRevision = Annotated[StrictInt, Field(ge=0)]
DatabaseId = Annotated[StrictInt, Field(gt=0)]
ImmutableArtifactReference = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=10,
        max_length=160,
        pattern=r"^(match_run|explanation_run|commit|contract):[A-Za-z0-9][A-Za-z0-9._:-]*$",
    ),
]


class BadCaseCategory(str, Enum):
    WRONG_TOP1 = "wrong_top1"
    RANKING_INVERSION = "ranking_inversion"
    FALSE_POSITIVE = "false_positive"
    FALSE_NEGATIVE = "false_negative"
    CONSTRAINT_CONFLICT = "constraint_conflict"
    UNCERTAIN_ORDER = "uncertain_order"
    EXPECTED_CANDIDATE_NOT_RECALLED = "expected_candidate_not_recalled"
    IRRELEVANT_CANDIDATE_RECALLED = "irrelevant_candidate_recalled"
    FILTER_EXCLUSION_DISAGREEMENT = "filter_exclusion_disagreement"
    POOL_TRUNCATION_CONCERN = "pool_truncation_concern"
    MISSING_SUPPORT = "missing_support"
    INCORRECT_SUPPORT_STATUS = "incorrect_support_status"
    PROJECT_SKILL_LINK_DISAGREEMENT = "project_skill_link_disagreement"
    REQUIREMENT_COVERAGE_DISAGREEMENT = "requirement_coverage_disagreement"
    UNSUPPORTED_EXPLANATION = "unsupported_explanation"
    MISLEADING_EXPLANATION = "misleading_explanation"
    INCOMPLETE_EXPLANATION = "incomplete_explanation"
    INCORRECT_GAP_STATEMENT = "incorrect_gap_statement"
    INCORRECT_TOP1_COMPARISON = "incorrect_top1_comparison"
    CANDIDATE_SNAPSHOT_ISSUE = "candidate_snapshot_issue"
    JOB_SNAPSHOT_ISSUE = "job_snapshot_issue"
    REQUIREMENT_ISSUE = "requirement_issue"
    CONSTRAINT_ISSUE = "constraint_issue"
    HISTORY_INTEGRITY_FAILURE = "history_integrity_failure"
    OWNERSHIP_FAILURE = "ownership_failure"
    LIFECYCLE_FAILURE = "lifecycle_failure"
    PROVIDER_ATTEMPT_FAILURE = "provider_attempt_failure"


class BadCaseSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class BadCaseStatus(str, Enum):
    CREATED = "CREATED"
    REVIEWED = "REVIEWED"
    ROOT_CAUSE_IDENTIFIED = "ROOT_CAUSE_IDENTIFIED"
    ACTION_PLANNED = "ACTION_PLANNED"
    RESOLVED = "RESOLVED"
    VERIFIED = "VERIFIED"
    DISMISSED = "DISMISSED"
    DUPLICATE = "DUPLICATE"


class SymptomFamily(str, Enum):
    RANKING = "RANKING"
    RETRIEVAL = "RETRIEVAL"
    EVIDENCE = "EVIDENCE"
    EXPLANATION = "EXPLANATION"
    DATA_QUALITY = "DATA_QUALITY"
    INTEGRITY_OPERATIONS = "INTEGRITY_OPERATIONS"


class RootCauseType(str, Enum):
    RANKING = "ranking"
    RETRIEVAL = "retrieval"
    FEATURE = "feature"
    EVIDENCE = "evidence"
    EXPLANATION = "explanation"
    DATA_QUALITY = "data_quality"
    INTEGRITY = "integrity"


class RootCauseCode(str, Enum):
    RANKING_WRONG_TOP1 = "ranking_wrong_top1"
    RANKING_PAIRWISE_INVERSION = "ranking_pairwise_inversion"
    RANKING_FALSE_POSITIVE = "ranking_false_positive"
    RANKING_FALSE_NEGATIVE = "ranking_false_negative"
    RANKING_TIE_BREAK_ISSUE = "ranking_tie_break_issue"
    RANKING_CONSTRAINT_POLICY_ISSUE = "ranking_constraint_policy_issue"
    RETRIEVAL_RECALL_MISS = "retrieval_recall_miss"
    RETRIEVAL_FILTER_EXCLUSION = "retrieval_filter_exclusion"
    RETRIEVAL_DENSE_COVERAGE_GAP = "retrieval_dense_coverage_gap"
    RETRIEVAL_SPARSE_COVERAGE_GAP = "retrieval_sparse_coverage_gap"
    RETRIEVAL_FUSION_ISSUE = "retrieval_fusion_issue"
    RETRIEVAL_POOL_TRUNCATION = "retrieval_pool_truncation"
    RETRIEVAL_INDEX_INTEGRITY = "retrieval_index_integrity"
    FEATURE_SEMANTIC_SCORE_ISSUE = "feature_semantic_score_issue"
    FEATURE_SPARSE_SCORE_ISSUE = "feature_sparse_score_issue"
    FEATURE_SKILL_FIT_ISSUE = "feature_skill_fit_issue"
    FEATURE_PROJECT_EVIDENCE_ISSUE = "feature_project_evidence_issue"
    FEATURE_ROLE_DIRECTION_ISSUE = "feature_role_direction_issue"
    FEATURE_LOCATION_ISSUE = "feature_location_issue"
    FEATURE_SENIORITY_ISSUE = "feature_seniority_issue"
    FEATURE_MISSING_PENALTY_ISSUE = "feature_missing_penalty_issue"
    FEATURE_OVERCLAIM_PENALTY_ISSUE = "feature_overclaim_penalty_issue"
    FEATURE_AVAILABILITY_ISSUE = "feature_availability_issue"
    EVIDENCE_MISSING_PROJECT_SUPPORT = "evidence_missing_project_support"
    EVIDENCE_STATUS_INCORRECT = "evidence_status_incorrect"
    EVIDENCE_SKILL_PROJECT_LINK_INCORRECT = "evidence_skill_project_link_incorrect"
    EVIDENCE_REQUIREMENT_ALIGNMENT_INCORRECT = "evidence_requirement_alignment_incorrect"
    EVIDENCE_CLAIM_PROMOTED_WITHOUT_SUPPORT = "evidence_claim_promoted_without_support"
    EVIDENCE_OWNER_MISMATCH = "evidence_owner_mismatch"
    EXPLANATION_UNSUPPORTED_CLAIM = "explanation_unsupported_claim"
    EXPLANATION_MISLEADING_TEMPLATE = "explanation_misleading_template"
    EXPLANATION_INCOMPLETE_SELECTION = "explanation_incomplete_selection"
    EXPLANATION_INCORRECT_GAP = "explanation_incorrect_gap"
    EXPLANATION_COMPARISON_MISMATCH = "explanation_comparison_mismatch"
    EXPLANATION_REFERENCE_OWNERSHIP = "explanation_reference_ownership"
    EXPLANATION_CLARITY_ISSUE = "explanation_clarity_issue"
    DATA_CANDIDATE_SKILL_MISSING = "data_candidate_skill_missing"
    DATA_CANDIDATE_SKILL_INCORRECT = "data_candidate_skill_incorrect"
    DATA_PROJECT_EVIDENCE_MISSING = "data_project_evidence_missing"
    DATA_CANDIDATE_SENIORITY_INCORRECT = "data_candidate_seniority_incorrect"
    DATA_CANDIDATE_LOCATION_INCORRECT = "data_candidate_location_incorrect"
    DATA_JOB_REQUIREMENT_UNCLEAR = "data_job_requirement_unclear"
    DATA_JOB_REQUIREMENT_MISSING = "data_job_requirement_missing"
    DATA_JOB_REQUIREMENT_PRIORITY_INCORRECT = "data_job_requirement_priority_incorrect"
    DATA_JOB_LEVEL_INCORRECT = "data_job_level_incorrect"
    DATA_JOB_EXPECTATION_MISSING = "data_job_expectation_missing"
    INTEGRITY_SNAPSHOT_FINGERPRINT = "integrity_snapshot_fingerprint"
    INTEGRITY_RESULT_FINGERPRINT = "integrity_result_fingerprint"
    INTEGRITY_CROSS_OWNER_REFERENCE = "integrity_cross_owner_reference"
    INTEGRITY_TERMINAL_OVERWRITE = "integrity_terminal_overwrite"
    INTEGRITY_ATTEMPT_AUDIT = "integrity_attempt_audit"


class AnalysisAssessment(str, Enum):
    SUSPECTED = "suspected"
    SUPPORTED = "supported"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class ResolutionActionType(str, Enum):
    DATA_CORRECTION_PROPOSAL = "data_correction_proposal"
    RETRIEVAL_CHANGE_HYPOTHESIS = "retrieval_change_hypothesis"
    FILTER_POLICY_HYPOTHESIS = "filter_policy_hypothesis"
    FUSION_POLICY_HYPOTHESIS = "fusion_policy_hypothesis"
    POOL_POLICY_HYPOTHESIS = "pool_policy_hypothesis"
    FEATURE_RULE_HYPOTHESIS = "feature_rule_hypothesis"
    FEATURE_CONTRACT_HYPOTHESIS = "feature_contract_hypothesis"
    RANKING_CHANGE_HYPOTHESIS = "ranking_change_hypothesis"
    RANKING_CONTRACT_HYPOTHESIS = "ranking_contract_hypothesis"
    CONSTRAINT_POLICY_HYPOTHESIS = "constraint_policy_hypothesis"
    DATA_INTEGRITY_ACTION = "data_integrity_action"
    EVIDENCE_RULE_HYPOTHESIS = "evidence_rule_hypothesis"
    EVIDENCE_INTEGRITY_ACTION = "evidence_integrity_action"
    PLANNING_POLICY_HYPOTHESIS = "planning_policy_hypothesis"
    TEMPLATE_CHANGE_HYPOTHESIS = "template_change_hypothesis"
    GROUNDING_INTEGRITY_ACTION = "grounding_integrity_action"
    INTEGRITY_REPAIR_ACTION = "integrity_repair_action"
    DOCUMENTATION_ACTION = "documentation_action"
    NO_CHANGE = "no_change"


class ResolutionActionStatus(str, Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"


class TransitionReason(str, Enum):
    REVIEW_COMPLETED = "review_completed"
    ROOT_CAUSE_SUPPORTED = "root_cause_supported"
    ACTION_CREATED = "action_created"
    ACTIONS_COMPLETED = "actions_completed"
    VERIFICATION_LINKED = "verification_linked"
    CASE_DISMISSED = "case_dismissed"
    DUPLICATE_LINKED = "duplicate_linked"
    CASE_REOPENED = "case_reopened"


class BadCaseSourceType(str, Enum):
    FEEDBACK = "feedback"
    SYSTEM_SIGNAL = "system_signal"


class BadCaseCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feedback_id: Optional[SafeIdentifier] = None
    system_signal_id: Optional[SafeIdentifier] = None
    symptom_code: BadCaseCategory
    severity: BadCaseSeverity

    @model_validator(mode="after")
    def exactly_one_source(self) -> "BadCaseCreateRequest":
        if (self.feedback_id is None) == (self.system_signal_id is None):
            raise ValueError("Exactly one BadCase source is required")
        if (
            self.system_signal_id is not None
            and self.symptom_code
            not in {
                BadCaseCategory.HISTORY_INTEGRITY_FAILURE,
                BadCaseCategory.OWNERSHIP_FAILURE,
                BadCaseCategory.LIFECYCLE_FAILURE,
                BadCaseCategory.PROVIDER_ATTEMPT_FAILURE,
            }
        ):
            raise ValueError(
                "System signals can create only deterministic integrity cases"
            )
        return self


class BadCaseAnalysisCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessment: AnalysisAssessment
    root_cause_type: RootCauseType
    root_cause_code: RootCauseCode
    description: SafeSummary
    supporting_evidence_link_id: Optional[DatabaseId] = None

    @model_validator(mode="after")
    def code_matches_type(self) -> "BadCaseAnalysisCreate":
        if not root_cause_allowed(self.root_cause_type.value, self.root_cause_code.value):
            raise ValueError("Root-cause code does not belong to the selected type")
        if (
            self.assessment in {AnalysisAssessment.SUPPORTED, AnalysisAssessment.CONFIRMED}
            and self.supporting_evidence_link_id is None
        ):
            raise ValueError("Supported analysis requires a scoped historical evidence link")
        return self


class ResolutionActionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_type: ResolutionActionType
    description: SafeSummary
    status: ResolutionActionStatus = ResolutionActionStatus.PLANNED
    supersedes_action_id: Optional[DatabaseId] = None
    safe_change_reference: Optional[SafeIdentifier] = None


class BadCaseUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_status: BadCaseStatus
    expected_revision: StrictRevision
    status: Optional[BadCaseStatus] = None
    transition_reason: Optional[TransitionReason] = None
    analysis: Optional[BadCaseAnalysisCreate] = None
    resolution: Optional[ResolutionActionCreate] = None
    verification_reference: Optional[ImmutableArtifactReference] = None
    duplicate_of_bad_case_id: Optional[SafeIdentifier] = None

    @model_validator(mode="after")
    def update_is_bounded(self) -> "BadCaseUpdateRequest":
        if self.status is None and self.analysis is None and self.resolution is None:
            raise ValueError("At least one review operation is required")
        if self.status is not None:
            if self.status == self.expected_status:
                raise ValueError("Lifecycle transition must change status")
            if self.transition_reason is None:
                raise ValueError("A status transition requires a reason")
            if not transition_reason_allowed(
                self.expected_status.value,
                self.status.value,
                self.transition_reason.value,
            ):
                raise ValueError("Transition reason does not match lifecycle transition")
        elif self.transition_reason is not None:
            raise ValueError("Transition reason requires a status transition")
        if self.status == BadCaseStatus.VERIFIED and self.verification_reference is None:
            raise ValueError("Verification requires an immutable reference")
        if self.status != BadCaseStatus.VERIFIED and self.verification_reference is not None:
            raise ValueError("Verification reference is only valid when verifying")
        if self.status == BadCaseStatus.DUPLICATE and self.duplicate_of_bad_case_id is None:
            raise ValueError("Duplicate disposition requires a canonical case")
        if self.status != BadCaseStatus.DUPLICATE and self.duplicate_of_bad_case_id is not None:
            raise ValueError("Duplicate reference is only valid for duplicate disposition")
        return self


class BadCaseSourceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: BadCaseSourceType
    feedback_id: Optional[SafeIdentifier] = None
    system_signal_id: Optional[SafeIdentifier] = None
    created_at: datetime

    @model_validator(mode="after")
    def source_identity_matches_type(self) -> "BadCaseSourceResponse":
        if self.source_type == BadCaseSourceType.FEEDBACK:
            if self.feedback_id is None or self.system_signal_id is not None:
                raise ValueError("Feedback source requires exactly one feedback ID")
        elif self.system_signal_id is None or self.feedback_id is not None:
            raise ValueError("System source requires exactly one signal ID")
        return self


class BadCaseAnalysisResponse(BadCaseAnalysisCreate):
    analysis_id: DatabaseId
    revision_number: Annotated[StrictInt, Field(gt=0)]
    created_at: datetime


class ResolutionActionResponse(ResolutionActionCreate):
    action_id: DatabaseId
    created_at: datetime
    completed_at: Optional[datetime] = None


class BadCaseTransitionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transition_id: DatabaseId
    from_status: BadCaseStatus
    to_status: BadCaseStatus
    reason: TransitionReason
    origin: Literal["manual_review", "system_rule"]
    previous_revision: StrictRevision
    new_revision: StrictRevision
    created_at: datetime


class BadCaseSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bad_case_id: SafeIdentifier
    case_contract_version: Literal[BAD_CASE_CONTRACT_VERSION]
    taxonomy_version: Literal[BAD_CASE_TAXONOMY_VERSION]
    primary_match_run_id: SafeIdentifier
    primary_match_result_id: Optional[DatabaseId] = None
    historical_job_id: SafeIdentifier
    historical_candidate_id: Optional[SafeIdentifier] = None
    result_rank: Optional[Annotated[StrictInt, Field(gt=0)]] = None
    primary_explanation_run_id: Optional[SafeIdentifier] = None
    primary_match_explanation_id: Optional[DatabaseId] = None
    symptom_code: BadCaseCategory
    symptom_family: SymptomFamily
    severity: BadCaseSeverity
    status: BadCaseStatus
    revision: StrictRevision
    duplicate_of_bad_case_id: Optional[SafeIdentifier] = None
    related_case_id: Optional[SafeIdentifier] = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def symptom_matches_family(self) -> "BadCaseSummaryResponse":
        if category_family(self.symptom_code.value) != self.symptom_family.value:
            raise ValueError("Symptom code does not belong to the selected family")
        if self.duplicate_of_bad_case_id == self.bad_case_id:
            raise ValueError("BadCase cannot duplicate itself")
        if self.related_case_id == self.bad_case_id:
            raise ValueError("BadCase cannot relate to itself")
        return self


class BadCaseDetailResponse(BadCaseSummaryResponse):
    sources: List[BadCaseSourceResponse] = Field(default_factory=list, max_length=20)
    analysis: Optional[BadCaseAnalysisResponse] = None
    resolution: Optional[ResolutionActionResponse] = None
    analyses: List[BadCaseAnalysisResponse] = Field(default_factory=list, max_length=100)
    resolution_actions: List[ResolutionActionResponse] = Field(
        default_factory=list, max_length=100
    )
    transitions: List[BadCaseTransitionResponse] = Field(
        default_factory=list, max_length=100
    )


__all__ = [
    "AnalysisAssessment",
    "BadCaseAnalysisCreate",
    "BadCaseAnalysisResponse",
    "BadCaseCategory",
    "BadCaseCreateRequest",
    "BadCaseDetailResponse",
    "BadCaseSeverity",
    "BadCaseSourceType",
    "BadCaseStatus",
    "BadCaseSummaryResponse",
    "BadCaseTransitionResponse",
    "BadCaseUpdateRequest",
    "ResolutionActionCreate",
    "ResolutionActionResponse",
    "ResolutionActionStatus",
    "ResolutionActionType",
    "RootCauseCode",
    "RootCauseType",
    "SymptomFamily",
    "TransitionReason",
]
