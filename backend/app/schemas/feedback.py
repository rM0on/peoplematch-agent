from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Literal, Optional, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StringConstraints,
    model_validator,
)

from app.schemas.explanations import EvidenceId
from app.services.feedback.contracts import FEEDBACK_CONTRACT_VERSION


SafeIdentifier = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=160,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    ),
]
SafeComment = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]
ExpectedCandidateReference = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=20,
        max_length=160,
        pattern=r"^expected_candidate:[A-Za-z0-9][A-Za-z0-9._:-]*$",
    ),
]
DatabaseId = Annotated[StrictInt, Field(gt=0)]


class FeedbackType(str, Enum):
    RANKING = "ranking"
    EXPLANATION = "explanation"
    PROFILE_DATA = "profile_data"


class RankingTargetType(str, Enum):
    OVERALL_RANKING = "overall_ranking"
    TOP1 = "top1"
    CANDIDATE_RESULT = "candidate_result"
    PAIRWISE = "pairwise"
    EXPECTED_CANDIDATE = "expected_candidate"


class RankingVerdict(str, Enum):
    CORRECT = "correct"
    WRONG = "wrong"
    UNCERTAIN = "uncertain"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class RankingReasonCode(str, Enum):
    WRONG_TOP1 = "wrong_top1"
    RANKING_INVERSION = "ranking_inversion"
    FALSE_POSITIVE = "false_positive"
    FALSE_NEGATIVE = "false_negative"
    CONSTRAINT_CONFLICT = "constraint_conflict"
    EVIDENCE_COVERAGE_DISAGREEMENT = "evidence_coverage_disagreement"


class ExplanationTargetType(str, Enum):
    SUMMARY = "summary"
    MATCH_REASON = "match_reason"
    RISK = "risk"
    MISSING_REQUIREMENT = "missing_requirement"
    INTERVIEW_QUESTION = "interview_question"
    TOP1_COMPARISON = "top1_comparison"
    REWRITE_OPERATION = "rewrite_operation"


class ExplanationVerdict(str, Enum):
    GROUNDED = "grounded"
    UNSUPPORTED = "unsupported"
    MISLEADING = "misleading"
    INCOMPLETE = "incomplete"


class ProfileTargetType(str, Enum):
    CANDIDATE_PROFILE = "candidate_profile"
    JOB_PROFILE = "job_profile"


class ProfileDataIssue(str, Enum):
    MISSING_SKILL = "missing_skill"
    INCORRECT_SKILL = "incorrect_skill"
    MISSING_PROJECT_EVIDENCE = "missing_project_evidence"
    INCORRECT_PROJECT_EVIDENCE_STATUS = "incorrect_project_evidence_status"
    INCORRECT_SENIORITY = "incorrect_seniority"
    INCORRECT_LOCATION = "incorrect_location"
    INCORRECT_ROLE_DIRECTION = "incorrect_role_direction"
    UNCLEAR_REQUIREMENT = "unclear_requirement"
    MISSING_REQUIREMENT = "missing_requirement"
    INCORRECT_REQUIREMENT_PRIORITY = "incorrect_requirement_priority"
    INCORRECT_SENIORITY_REQUIREMENT = "incorrect_seniority_requirement"
    INCORRECT_LOCATION_CONSTRAINT = "incorrect_location_constraint"
    MISSING_EXPECTATION = "missing_expectation"


class ProfileFieldLocator(str, Enum):
    CANDIDATE_SKILLS = "candidate.skills"
    CANDIDATE_PROJECT_EVIDENCE = "candidate.project_evidence"
    CANDIDATE_SENIORITY = "candidate.seniority"
    CANDIDATE_LOCATION = "candidate.location"
    CANDIDATE_ROLE_DIRECTION = "candidate.role_direction"
    JOB_REQUIREMENTS = "job.requirements"
    JOB_REQUIREMENT_PRIORITY = "job.requirement_priority"
    JOB_SENIORITY = "job.seniority"
    JOB_LOCATION = "job.location"
    JOB_EXPECTATIONS = "job.expectations"


class _FeedbackCreateBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    match_run_id: SafeIdentifier
    comment: Optional[SafeComment] = None
    supersedes_feedback_id: Optional[SafeIdentifier] = None


class RankingFeedbackCreate(_FeedbackCreateBase):
    feedback_type: Literal["ranking"]
    target_type: RankingTargetType
    subject_match_result_id: Optional[DatabaseId] = None
    comparison_match_result_id: Optional[DatabaseId] = None
    expected_candidate_reference: Optional[ExpectedCandidateReference] = None
    value: RankingVerdict
    reason_code: Optional[RankingReasonCode] = None

    @model_validator(mode="after")
    def selectors_match_target(self) -> "RankingFeedbackCreate":
        allowed_reasons = {
            RankingTargetType.OVERALL_RANKING: {
                RankingReasonCode.CONSTRAINT_CONFLICT,
                RankingReasonCode.EVIDENCE_COVERAGE_DISAGREEMENT,
            },
            RankingTargetType.TOP1: {RankingReasonCode.WRONG_TOP1},
            RankingTargetType.CANDIDATE_RESULT: {
                RankingReasonCode.FALSE_POSITIVE,
                RankingReasonCode.CONSTRAINT_CONFLICT,
                RankingReasonCode.EVIDENCE_COVERAGE_DISAGREEMENT,
            },
            RankingTargetType.PAIRWISE: {
                RankingReasonCode.RANKING_INVERSION,
                RankingReasonCode.CONSTRAINT_CONFLICT,
                RankingReasonCode.EVIDENCE_COVERAGE_DISAGREEMENT,
            },
        }
        allowed_reasons[RankingTargetType.EXPECTED_CANDIDATE] = {
            RankingReasonCode.FALSE_NEGATIVE
        }
        if self.value == RankingVerdict.WRONG:
            if self.reason_code is None:
                raise ValueError("Wrong ranking feedback requires a reason code")
            if self.reason_code not in allowed_reasons[self.target_type]:
                raise ValueError("Reason code does not apply to the ranking target")
        elif self.reason_code is not None:
            raise ValueError("Only wrong ranking feedback accepts a defect reason")
        if self.target_type == RankingTargetType.OVERALL_RANKING:
            if (
                self.subject_match_result_id is not None
                or self.comparison_match_result_id is not None
                or self.expected_candidate_reference is not None
            ):
                raise ValueError("overall ranking feedback cannot select results")
        elif self.target_type in {
            RankingTargetType.TOP1,
            RankingTargetType.CANDIDATE_RESULT,
        }:
            if (
                self.subject_match_result_id is None
                or self.comparison_match_result_id is not None
                or self.expected_candidate_reference is not None
            ):
                raise ValueError("target requires exactly one subject result")
        elif self.target_type == RankingTargetType.PAIRWISE:
            if (
                self.subject_match_result_id is None
                or self.comparison_match_result_id is None
                or self.subject_match_result_id == self.comparison_match_result_id
                or self.expected_candidate_reference is not None
            ):
                raise ValueError("pairwise feedback requires two distinct results")
        elif (
            self.subject_match_result_id is not None
            or self.comparison_match_result_id is not None
            or self.expected_candidate_reference is None
        ):
            raise ValueError(
                "expected Candidate feedback requires only a bounded reviewer reference"
            )
        return self


class ExplanationFeedbackCreate(_FeedbackCreateBase):
    feedback_type: Literal["explanation"]
    explanation_run_id: SafeIdentifier
    match_explanation_id: DatabaseId
    target_type: ExplanationTargetType
    value: ExplanationVerdict
    evidence_reference: Optional[EvidenceId] = None


_CANDIDATE_PROFILE_ISSUES = {
    ProfileDataIssue.MISSING_SKILL,
    ProfileDataIssue.INCORRECT_SKILL,
    ProfileDataIssue.MISSING_PROJECT_EVIDENCE,
    ProfileDataIssue.INCORRECT_PROJECT_EVIDENCE_STATUS,
    ProfileDataIssue.INCORRECT_SENIORITY,
    ProfileDataIssue.INCORRECT_LOCATION,
    ProfileDataIssue.INCORRECT_ROLE_DIRECTION,
}
_JOB_PROFILE_ISSUES = set(ProfileDataIssue) - _CANDIDATE_PROFILE_ISSUES
_CANDIDATE_LOCATORS = {
    item for item in ProfileFieldLocator if item.value.startswith("candidate.")
}
_JOB_LOCATORS = set(ProfileFieldLocator) - _CANDIDATE_LOCATORS
_PROFILE_ISSUE_LOCATORS = {
    ProfileDataIssue.MISSING_SKILL: ProfileFieldLocator.CANDIDATE_SKILLS,
    ProfileDataIssue.INCORRECT_SKILL: ProfileFieldLocator.CANDIDATE_SKILLS,
    ProfileDataIssue.MISSING_PROJECT_EVIDENCE: ProfileFieldLocator.CANDIDATE_PROJECT_EVIDENCE,
    ProfileDataIssue.INCORRECT_PROJECT_EVIDENCE_STATUS: ProfileFieldLocator.CANDIDATE_PROJECT_EVIDENCE,
    ProfileDataIssue.INCORRECT_SENIORITY: ProfileFieldLocator.CANDIDATE_SENIORITY,
    ProfileDataIssue.INCORRECT_LOCATION: ProfileFieldLocator.CANDIDATE_LOCATION,
    ProfileDataIssue.INCORRECT_ROLE_DIRECTION: ProfileFieldLocator.CANDIDATE_ROLE_DIRECTION,
    ProfileDataIssue.UNCLEAR_REQUIREMENT: ProfileFieldLocator.JOB_REQUIREMENTS,
    ProfileDataIssue.MISSING_REQUIREMENT: ProfileFieldLocator.JOB_REQUIREMENTS,
    ProfileDataIssue.INCORRECT_REQUIREMENT_PRIORITY: ProfileFieldLocator.JOB_REQUIREMENT_PRIORITY,
    ProfileDataIssue.INCORRECT_SENIORITY_REQUIREMENT: ProfileFieldLocator.JOB_SENIORITY,
    ProfileDataIssue.INCORRECT_LOCATION_CONSTRAINT: ProfileFieldLocator.JOB_LOCATION,
    ProfileDataIssue.MISSING_EXPECTATION: ProfileFieldLocator.JOB_EXPECTATIONS,
}


class ProfileDataFeedbackCreate(_FeedbackCreateBase):
    feedback_type: Literal["profile_data"]
    target_type: ProfileTargetType
    subject_match_result_id: Optional[DatabaseId] = None
    value: ProfileDataIssue
    field_locator: ProfileFieldLocator

    @model_validator(mode="after")
    def target_is_semantically_closed(self) -> "ProfileDataFeedbackCreate":
        if self.target_type == ProfileTargetType.CANDIDATE_PROFILE:
            if self.subject_match_result_id is None:
                raise ValueError("Candidate profile feedback requires one historical result")
            if self.value not in _CANDIDATE_PROFILE_ISSUES:
                raise ValueError("Issue does not apply to Candidate history")
            if self.field_locator not in _CANDIDATE_LOCATORS:
                raise ValueError("Field locator does not address Candidate history")
        else:
            if self.subject_match_result_id is not None:
                raise ValueError("Job profile feedback cannot select a Candidate result")
            if self.value not in _JOB_PROFILE_ISSUES:
                raise ValueError("Issue does not apply to Job history")
            if self.field_locator not in _JOB_LOCATORS:
                raise ValueError("Field locator does not address Job history")
        if _PROFILE_ISSUE_LOCATORS[self.value] != self.field_locator:
            raise ValueError("Field locator does not match the selected issue")
        return self


FeedbackCreateRequest = Annotated[
    Union[
        RankingFeedbackCreate,
        ExplanationFeedbackCreate,
        ProfileDataFeedbackCreate,
    ],
    Field(discriminator="feedback_type"),
]


class _FeedbackRecordFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feedback_id: SafeIdentifier
    contract_version: Literal[FEEDBACK_CONTRACT_VERSION] = FEEDBACK_CONTRACT_VERSION
    origin: Literal["human"] = "human"
    job_id: SafeIdentifier
    candidate_id: Optional[SafeIdentifier] = None
    result_rank: Optional[Annotated[StrictInt, Field(gt=0)]] = None
    comparison_candidate_id: Optional[SafeIdentifier] = None
    comparison_result_rank: Optional[Annotated[StrictInt, Field(gt=0)]] = None
    created_at: datetime


class RankingFeedbackRecord(RankingFeedbackCreate, _FeedbackRecordFields):
    pass


class ExplanationFeedbackRecord(ExplanationFeedbackCreate, _FeedbackRecordFields):
    pass


class ProfileDataFeedbackRecord(ProfileDataFeedbackCreate, _FeedbackRecordFields):
    pass


FeedbackRecordV1 = Annotated[
    Union[
        RankingFeedbackRecord,
        ExplanationFeedbackRecord,
        ProfileDataFeedbackRecord,
    ],
    Field(discriminator="feedback_type"),
]


__all__ = [
    "ExplanationFeedbackCreate",
    "ExplanationFeedbackRecord",
    "ExplanationTargetType",
    "ExplanationVerdict",
    "ExpectedCandidateReference",
    "FeedbackCreateRequest",
    "FeedbackRecordV1",
    "FeedbackType",
    "ProfileDataFeedbackCreate",
    "ProfileDataFeedbackRecord",
    "ProfileDataIssue",
    "ProfileFieldLocator",
    "ProfileTargetType",
    "RankingFeedbackCreate",
    "RankingFeedbackRecord",
    "RankingReasonCode",
    "RankingTargetType",
    "RankingVerdict",
]
