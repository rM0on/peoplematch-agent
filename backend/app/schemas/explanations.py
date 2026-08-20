from __future__ import annotations

from datetime import datetime
from enum import Enum
import re
from typing import Annotated, List, Literal, Optional, Union

from pydantic import (
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.schemas.shared import ContractModel
from app.schemas.shared import ProductStage, RemotePolicy, Seniority
from app.schemas.candidate import EvidenceType, RiskLevel, SkillCategory, VerificationStatus
from app.schemas.job import RequirementCategory


EVIDENCE_ID_PATTERN = (
    r"^(?:"
    r"job_requirement:[A-Za-z0-9_.-]{1,100}|"
    r"candidate:[1-9][0-9]*:(?:"
    r"skill:[a-f0-9]{32,64}|"
    r"project:[A-Za-z0-9_.-]{1,100}|"
    r"project_evidence:[A-Za-z0-9_.-]{1,100})|"
    r"(?:feature|ranking|retrieval|diagnostic):[1-9][0-9]*:[a-z][a-z0-9_.-]{0,79}|"
    r"comparison:[1-9][0-9]*:top1:[a-z][a-z0-9_.-]{0,79}"
    r")$"
)
JOB_REQUIREMENT_EVIDENCE_ID_PATTERN = r"^job_requirement:[A-Za-z0-9_.-]{1,100}$"
CANDIDATE_SKILL_EVIDENCE_ID_PATTERN = (
    r"^candidate:[1-9][0-9]*:skill:[a-f0-9]{32,64}$"
)
CANDIDATE_PROJECT_EVIDENCE_ID_PATTERN = (
    r"^candidate:[1-9][0-9]*:project:[A-Za-z0-9_.-]{1,100}$"
)
CANDIDATE_PROJECT_RECORD_EVIDENCE_ID_PATTERN = (
    r"^candidate:[1-9][0-9]*:project_evidence:[A-Za-z0-9_.-]{1,100}$"
)
EvidenceId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=3,
        max_length=180,
        pattern=EVIDENCE_ID_PATTERN,
    ),
]
JobRequirementEvidenceId = Annotated[
    str, StringConstraints(pattern=JOB_REQUIREMENT_EVIDENCE_ID_PATTERN)
]
CandidateSkillEvidenceId = Annotated[
    str, StringConstraints(pattern=CANDIDATE_SKILL_EVIDENCE_ID_PATTERN)
]
CandidateProjectEvidenceId = Annotated[
    str, StringConstraints(pattern=CANDIDATE_PROJECT_EVIDENCE_ID_PATTERN)
]
CandidateProjectRecordEvidenceId = Annotated[
    str, StringConstraints(pattern=CANDIDATE_PROJECT_RECORD_EVIDENCE_ID_PATTERN)
]
Fingerprint = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
BoundedIdentifier = Annotated[str, StringConstraints(min_length=1, max_length=160)]
ProviderSafeIdentifier = Annotated[
    StrictStr,
    StringConstraints(
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$",
    ),
]
BoundedText = Annotated[str, StringConstraints(min_length=1, max_length=400)]


class Phase9ContractModel(ContractModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class ExplanationRunStatus(str, Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class RequirementPriority(str, Enum):
    MUST_HAVE = "must_have"
    NICE_TO_HAVE = "nice_to_have"


class RequirementStatus(str, Enum):
    MATCHED = "matched"
    PARTIAL = "partial"
    MISSING = "missing"
    NOT_ASSESSED = "not_assessed"


class RequirementEvidenceStatus(str, Enum):
    AVAILABLE_EVIDENCE = "available_evidence"
    CLAIM_ONLY = "claim_only"
    ABSENT = "absent"
    NOT_ASSESSED = "not_assessed"


class EvidenceFactKind(str, Enum):
    RANKING = "ranking"
    RETRIEVAL = "retrieval"
    FEATURE = "feature"
    DIAGNOSTIC = "diagnostic"
    COMPARISON = "comparison"


class RetrievalFactName(str, Enum):
    RETRIEVAL_RANK = "retrieval_rank"
    MATCHED_CHANNELS = "matched_channels"
    DENSE_RANK = "dense_rank"
    DENSE_SCORE = "dense_score"
    SPARSE_RANK = "sparse_rank"
    SPARSE_SCORE = "sparse_score"
    FUSION_SCORE = "fusion_score"


class FeatureFactName(str, Enum):
    SEMANTIC_SCORE = "semantic_score"
    SPARSE_SCORE = "sparse_score"
    SKILL_FIT_SCORE = "skill_fit_score"
    PROJECT_EVIDENCE_SCORE = "project_evidence_score"
    ROLE_DIRECTION_SCORE = "role_direction_score"
    AI_TOOL_SCORE = "ai_tool_score"
    LOCATION_SCORE = "location_score"
    SENIORITY_SCORE = "seniority_score"
    MISSING_PENALTY = "missing_penalty"
    OVERCLAIM_PENALTY = "overclaim_penalty"


class RankingFactName(str, Enum):
    RESULT_RANK = "result_rank"
    LTR_RANK = "ltr_rank"
    LTR_SCORE_RAW = "ltr_score_raw"
    CROSS_ENCODER_RANK = "cross_encoder_rank"
    CROSS_ENCODER_SCORE_RAW = "cross_encoder_score_raw"


class DiagnosticFactName(str, Enum):
    MATCHED_MUST_HAVE_REQUIREMENT_IDS = "matched_must_have_requirement_ids"
    WEAK_MATCHED_MUST_HAVE_REQUIREMENT_IDS = "weak_matched_must_have_requirement_ids"
    MISSING_MUST_HAVE_REQUIREMENT_IDS = "missing_must_have_requirement_ids"
    MATCHED_NICE_TO_HAVE_REQUIREMENT_IDS = "matched_nice_to_have_requirement_ids"
    EVIDENCE_SUPPORTED_REQUIREMENT_IDS = "evidence_supported_requirement_ids"
    MATCHED_CAPABILITIES = "matched_capabilities"
    MATCHED_EVIDENCE_SKILLS = "matched_evidence_skills"
    MATCHED_AI_TOOLS = "matched_ai_tools"
    LOCATION_RELATION = "location_relation"
    SENIORITY_RELATION = "seniority_relation"
    OVERCLAIM_LEVEL = "overclaim_level"
    OVERCLAIM_REASON_COUNT = "overclaim_reason_count"


class ComparisonFactName(str, Enum):
    RESULT_RANK = "result_rank"
    LTR_RANK = "ltr_rank"
    LTR_SCORE_RAW = "ltr_score_raw"
    CROSS_ENCODER_RANK = "cross_encoder_rank"
    CROSS_ENCODER_SCORE_RAW = "cross_encoder_score_raw"
    SKILL_FIT_SCORE = "skill_fit_score"
    PROJECT_EVIDENCE_SCORE = "project_evidence_score"
    ROLE_DIRECTION_SCORE = "role_direction_score"
    AI_TOOL_SCORE = "ai_tool_score"
    LOCATION_SCORE = "location_score"
    SENIORITY_SCORE = "seniority_score"
    MISSING_PENALTY = "missing_penalty"
    OVERCLAIM_PENALTY = "overclaim_penalty"


EvidenceValueText = Annotated[
    StrictStr, StringConstraints(min_length=1, max_length=500)
]
EvidenceValueList = Annotated[
    List[Annotated[StrictStr, StringConstraints(min_length=1, max_length=120)]],
    Field(max_length=100),
]
EvidenceValue = Union[
    StrictBool,
    StrictInt,
    Annotated[StrictFloat, Field(allow_inf_nan=False)],
    EvidenceValueText,
    EvidenceValueList,
    None,
]

StrictPositiveRank = Annotated[StrictInt, Field(ge=1, le=50)]
StrictTop1Rank = Annotated[StrictInt, Field(ge=1, le=1)]
StrictScore = Annotated[StrictFloat, Field(allow_inf_nan=False)]
MatchedChannel = Literal["dense", "sparse"]
MatchRelation = Literal["exact_match", "mismatch", "unavailable"]
RiskLevelValue = Literal["low", "medium", "high"]
SafeNormalizedLabel = Annotated[
    StrictStr,
    StringConstraints(
        pattern=(
            r"^[A-Za-z0-9][A-Za-z0-9_.:/+-]*"
            r"(?: [A-Za-z0-9][A-Za-z0-9_.:/+-]*){0,11}$"
        ),
        max_length=120,
    ),
]
RequirementIdList = Annotated[List[JobRequirementEvidenceId], Field(max_length=100)]
NormalizedLabelList = Annotated[List[SafeNormalizedLabel], Field(max_length=100)]
MatchedChannelList = Annotated[List[MatchedChannel], Field(max_length=10)]


class ProviderRequirementEvidence(Phase9ContractModel):
    evidence_id: JobRequirementEvidenceId
    requirement_id: ProviderSafeIdentifier
    priority: RequirementPriority
    category: RequirementCategory


class HistoricalRequirementEvidence(ProviderRequirementEvidence):
    text: Annotated[str, StringConstraints(min_length=1, max_length=400)]
    evidence_expectation: Annotated[str, StringConstraints(min_length=1, max_length=400)]


class ProviderJobLocation(Phase9ContractModel):
    remote_policy: RemotePolicy
    relocation_supported: StrictBool


class HistoricalJobLocation(ProviderJobLocation):
    cities: List[Annotated[str, StringConstraints(min_length=1, max_length=120)]] = Field(
        max_length=4
    )


class ProviderJobEvidence(Phase9ContractModel):
    requirements: List[ProviderRequirementEvidence] = Field(
        min_length=1, max_length=100
    )
    location: ProviderJobLocation
    seniority_requirement: List[Seniority] = Field(min_length=1, max_length=8)
    product_stage: ProductStage


class HistoricalJobEvidence(ProviderJobEvidence):
    requirements: List[HistoricalRequirementEvidence] = Field(min_length=1, max_length=100)
    location: HistoricalJobLocation
    job_id: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    role_title: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    role_direction: List[
        Annotated[str, StringConstraints(min_length=1, max_length=120)]
    ] = Field(max_length=20)


class CandidateSkillEvidence(Phase9ContractModel):
    evidence_id: EvidenceId
    name: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    category: SkillCategory


class CandidateProjectEvidence(Phase9ContractModel):
    evidence_id: EvidenceId
    project_id: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    technologies: List[
        Annotated[str, StringConstraints(min_length=1, max_length=120)]
    ] = Field(max_length=50)
    skills_demonstrated: List[
        Annotated[str, StringConstraints(min_length=1, max_length=120)]
    ] = Field(max_length=50)


class CandidateEvidenceRecord(Phase9ContractModel):
    evidence_id: EvidenceId
    source_evidence_id: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    project_id: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    supports_skills: List[
        Annotated[str, StringConstraints(min_length=1, max_length=120)]
    ] = Field(max_length=50)
    verification_status: VerificationStatus
    evidence_type: EvidenceType


class CandidateLocationEvidence(Phase9ContractModel):
    cities: List[Annotated[str, StringConstraints(min_length=1, max_length=120)]] = Field(
        max_length=4
    )
    remote_policy: RemotePolicy
    relocation_open: StrictBool


class CandidateOverclaimEvidence(Phase9ContractModel):
    level: Optional[RiskLevel] = None
    reason_count: Annotated[StrictInt, Field(ge=0, le=100)]


class ProviderCandidateSkillEvidence(Phase9ContractModel):
    evidence_id: EvidenceId
    category: SkillCategory


class ProviderCandidateProjectEvidence(Phase9ContractModel):
    evidence_id: EvidenceId
    project_id: ProviderSafeIdentifier


class ProviderCandidateEvidenceRecord(Phase9ContractModel):
    evidence_id: EvidenceId
    source_evidence_id: ProviderSafeIdentifier
    project_id: ProviderSafeIdentifier
    verification_status: VerificationStatus
    evidence_type: EvidenceType


class ProviderCandidateLocationEvidence(Phase9ContractModel):
    remote_policy: RemotePolicy
    relocation_open: StrictBool


class ProviderCandidateOverclaimEvidence(Phase9ContractModel):
    level: Optional[RiskLevel] = None
    reason_count: Annotated[StrictInt, Field(ge=0, le=100)]


class EvidenceFact(Phase9ContractModel):
    evidence_id: EvidenceId
    kind: EvidenceFactKind
    candidate_id: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    name: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_.-]{0,79}$")]
    value: EvidenceValue
    comparison_candidate_id: Optional[
        Annotated[str, StringConstraints(min_length=1, max_length=80)]
    ] = None

    @model_validator(mode="after")
    def namespace_kind_and_name_are_closed(self) -> "EvidenceFact":
        namespace = self.evidence_id.split(":", 1)[0]
        expected_namespace = self.kind.value
        if namespace != expected_namespace:
            raise ValueError("evidence namespace must match fact kind")
        allowed_names = {
            EvidenceFactKind.RETRIEVAL: RetrievalFactName,
            EvidenceFactKind.FEATURE: FeatureFactName,
            EvidenceFactKind.RANKING: RankingFactName,
            EvidenceFactKind.DIAGNOSTIC: DiagnosticFactName,
            EvidenceFactKind.COMPARISON: ComparisonFactName,
        }
        if self.name not in {item.value for item in allowed_names[self.kind]}:
            raise ValueError("evidence fact name is not in the frozen allowlist")
        if self.evidence_id.rsplit(":", 1)[-1] != self.name:
            raise ValueError("evidence namespace name must match fact name")
        if self.kind == EvidenceFactKind.COMPARISON:
            if self.comparison_candidate_id is None:
                raise ValueError("comparison fact requires top-1 Candidate identity")
        elif self.comparison_candidate_id is not None:
            raise ValueError("only comparison facts may identify another Candidate")
        return self


class ProviderRankEvidence(Phase9ContractModel):
    evidence_id: EvidenceId
    value: StrictPositiveRank


class ProviderScoreEvidence(Phase9ContractModel):
    evidence_id: EvidenceId
    value: Optional[StrictScore]


class ProviderRequiredScoreEvidence(Phase9ContractModel):
    evidence_id: EvidenceId
    value: StrictScore


class ProviderChannelEvidence(Phase9ContractModel):
    evidence_id: EvidenceId
    value: MatchedChannelList


class ProviderRequirementIdsEvidence(Phase9ContractModel):
    evidence_id: EvidenceId
    value: RequirementIdList


class ProviderLabelsEvidence(Phase9ContractModel):
    evidence_id: EvidenceId
    value: NormalizedLabelList


class ProviderRelationEvidence(Phase9ContractModel):
    evidence_id: EvidenceId
    value: MatchRelation


class ProviderRiskLevelEvidence(Phase9ContractModel):
    evidence_id: EvidenceId
    value: RiskLevelValue


class ProviderCountEvidence(Phase9ContractModel):
    evidence_id: EvidenceId
    value: Annotated[StrictInt, Field(ge=0, le=100)]


class ProviderRetrievalEvidence(Phase9ContractModel):
    retrieval_rank: ProviderRankEvidence
    matched_channels: ProviderChannelEvidence
    dense_rank: Optional[ProviderRankEvidence]
    dense_score: ProviderScoreEvidence
    sparse_rank: Optional[ProviderRankEvidence]
    sparse_score: ProviderScoreEvidence
    fusion_score: ProviderRequiredScoreEvidence


class ProviderFeatureEvidence(Phase9ContractModel):
    semantic_score: ProviderScoreEvidence
    sparse_score: ProviderScoreEvidence
    skill_fit_score: ProviderScoreEvidence
    project_evidence_score: ProviderScoreEvidence
    role_direction_score: ProviderScoreEvidence
    ai_tool_score: ProviderScoreEvidence
    location_score: ProviderScoreEvidence
    seniority_score: ProviderScoreEvidence
    missing_penalty: ProviderScoreEvidence
    overclaim_penalty: ProviderScoreEvidence


class ProviderRankingEvidence(Phase9ContractModel):
    result_rank: ProviderRankEvidence
    ltr_rank: ProviderRankEvidence
    ltr_score_raw: ProviderRequiredScoreEvidence
    cross_encoder_rank: Optional[ProviderRankEvidence]
    cross_encoder_score_raw: Optional[ProviderRequiredScoreEvidence]


class ProviderDiagnosticEvidence(Phase9ContractModel):
    matched_must_have_requirement_ids: Optional[ProviderRequirementIdsEvidence] = None
    weak_matched_must_have_requirement_ids: Optional[ProviderRequirementIdsEvidence] = None
    missing_must_have_requirement_ids: Optional[ProviderRequirementIdsEvidence] = None
    matched_nice_to_have_requirement_ids: Optional[ProviderRequirementIdsEvidence] = None
    evidence_supported_requirement_ids: Optional[ProviderRequirementIdsEvidence] = None
    location_relation: Optional[ProviderRelationEvidence] = None
    seniority_relation: Optional[ProviderRelationEvidence] = None
    overclaim_level: Optional[ProviderRiskLevelEvidence] = None
    overclaim_reason_count: Optional[ProviderCountEvidence] = None


class ProviderTop1Comparison(Phase9ContractModel):
    top1_candidate_id: ProviderSafeIdentifier
    top1_rank: StrictTop1Rank
    result_rank: Optional[ProviderRankEvidence] = None
    ltr_rank: Optional[ProviderRankEvidence] = None
    ltr_score_raw: Optional[ProviderRequiredScoreEvidence] = None
    cross_encoder_rank: Optional[ProviderRankEvidence] = None
    cross_encoder_score_raw: Optional[ProviderRequiredScoreEvidence] = None
    skill_fit_score: Optional[ProviderScoreEvidence] = None
    project_evidence_score: Optional[ProviderScoreEvidence] = None
    role_direction_score: Optional[ProviderScoreEvidence] = None
    ai_tool_score: Optional[ProviderScoreEvidence] = None
    location_score: Optional[ProviderScoreEvidence] = None
    seniority_score: Optional[ProviderScoreEvidence] = None
    missing_penalty: Optional[ProviderScoreEvidence] = None
    overclaim_penalty: Optional[ProviderScoreEvidence] = None


class HistoricalCandidateEvidence(Phase9ContractModel):
    candidate_id: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    result_rank: StrictPositiveRank
    target_roles: List[
        Annotated[str, StringConstraints(min_length=1, max_length=160)]
    ] = Field(max_length=30)
    skills: List[CandidateSkillEvidence] = Field(max_length=200)
    projects: List[CandidateProjectEvidence] = Field(max_length=100)
    project_evidence: List[CandidateEvidenceRecord] = Field(max_length=200)
    ai_tools: List[
        Annotated[str, StringConstraints(min_length=1, max_length=120)]
    ] = Field(max_length=100)
    preferred_locations: CandidateLocationEvidence
    seniority: Seniority
    team_stage_preference: List[
        Annotated[str, StringConstraints(min_length=1, max_length=64)]
    ] = Field(max_length=20)
    overclaim_risk: CandidateOverclaimEvidence
    facts: List[EvidenceFact] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def evidence_belongs_to_candidate_and_rank(self) -> "HistoricalCandidateEvidence":
        _validate_candidate_ownership(self, self.facts)
        return self


class ProviderCandidateEvidence(Phase9ContractModel):
    candidate_id: ProviderSafeIdentifier
    result_rank: StrictPositiveRank
    skills: List[ProviderCandidateSkillEvidence] = Field(max_length=200)
    projects: List[ProviderCandidateProjectEvidence] = Field(max_length=100)
    project_evidence: List[ProviderCandidateEvidenceRecord] = Field(max_length=200)
    preferred_locations: ProviderCandidateLocationEvidence
    seniority: Seniority
    overclaim_risk: ProviderCandidateOverclaimEvidence
    retrieval: ProviderRetrievalEvidence
    features: ProviderFeatureEvidence
    ranking: ProviderRankingEvidence
    diagnostics: ProviderDiagnosticEvidence
    top1_comparison: Optional[ProviderTop1Comparison]

    @model_validator(mode="after")
    def evidence_belongs_to_candidate_and_rank(self) -> "ProviderCandidateEvidence":
        for namespace, group in (
            ("retrieval", self.retrieval),
            ("feature", self.features),
            ("ranking", self.ranking),
            ("diagnostic", self.diagnostics),
        ):
            for name, item in group.__dict__.items():
                if item is not None and item.evidence_id != (
                    f"{namespace}:{self.result_rank}:{name}"
                ):
                    raise ValueError(
                        "Provider evidence ID must match its aggregate property"
                    )
        if self.top1_comparison is not None:
            for name, item in self.top1_comparison.__dict__.items():
                if name in {"top1_candidate_id", "top1_rank"} or item is None:
                    continue
                if item.evidence_id != f"comparison:{self.result_rank}:top1:{name}":
                    raise ValueError(
                        "Provider comparison ID must match its aggregate property"
                    )
        for item in _provider_candidate_evidence_items(self):
            if _fact_rank(item.evidence_id) != self.result_rank:
                raise ValueError("Provider evidence rank owner does not match parent")
        project_ids = {item.project_id for item in self.projects}
        if any(item.project_id not in project_ids for item in self.project_evidence):
            raise ValueError("Provider project evidence project owner does not match parent")
        if self.ranking.result_rank.value != self.result_rank:
            raise ValueError("Provider result_rank evidence must match Candidate rank")
        if (self.ranking.cross_encoder_rank is None) != (
            self.ranking.cross_encoder_score_raw is None
        ):
            raise ValueError("Provider Cross-Encoder rank and score must be absent or complete")
        if self.result_rank == 1 and self.top1_comparison is not None:
            raise ValueError("rank-1 Candidate cannot contain a top-1 comparison")
        if self.result_rank > 1 and self.top1_comparison is None:
            raise ValueError("non-top-one Candidate requires top-1 comparison evidence")
        return self


class MatchRunEvidenceSource(Phase9ContractModel):
    match_run_id: Annotated[str, StringConstraints(min_length=1, max_length=36)]
    ranking_variant: Literal["ltr", "cross_encoder_experiment"]
    workflow_version: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    workflow_fingerprint: Fingerprint
    ranking_input_fingerprint: Fingerprint
    result_fingerprint: Fingerprint


class CrossEncoderRuntimeProvenance(Phase9ContractModel):
    reranker_version: BoundedIdentifier
    model_id: BoundedIdentifier
    model_revision: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    snapshot_fingerprint: Fingerprint
    text_schema_version: BoundedIdentifier
    text_contract_fingerprint: Fingerprint
    pair_order: BoundedIdentifier
    score_type: BoundedIdentifier
    score_direction: BoundedIdentifier
    calibration: bool


class RuntimeProvenance(Phase9ContractModel):
    retrieval_document_version: BoundedIdentifier
    retrieval_configuration_fingerprint: Fingerprint
    feature_version: BoundedIdentifier
    feature_fingerprint: Fingerprint
    ranker_version: BoundedIdentifier
    ranker_model_sha256: Fingerprint
    cross_encoder: Optional[CrossEncoderRuntimeProvenance]


class WorkflowTraceItem(Phase9ContractModel):
    sequence: int = Field(ge=1, le=100)
    step_name: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    status: Literal["COMPLETED"]


def _fact_rank(evidence_id: str) -> int:
    return int(evidence_id.split(":", 2)[1])


def _validate_fact_value(kind: EvidenceFactKind, name: str | Enum, value: object) -> None:
    fact_name = name.value if isinstance(name, Enum) else name
    rank_names = {
        "retrieval_rank", "dense_rank", "sparse_rank", "result_rank",
        "ltr_rank", "cross_encoder_rank",
    }
    score_names = {
        "dense_score", "sparse_score", "fusion_score", "semantic_score",
        "skill_fit_score", "project_evidence_score", "role_direction_score",
        "ai_tool_score", "location_score", "seniority_score", "missing_penalty",
        "overclaim_penalty", "ltr_score_raw", "cross_encoder_score_raw",
    }
    requirement_list_names = {
        "matched_must_have_requirement_ids",
        "weak_matched_must_have_requirement_ids", "missing_must_have_requirement_ids",
        "matched_nice_to_have_requirement_ids", "evidence_supported_requirement_ids",
    }
    label_list_names = {"matched_capabilities", "matched_evidence_skills", "matched_ai_tools"}
    relation_names = {"location_relation", "seniority_relation"}
    if fact_name in rank_names:
        if type(value) is not int or value < 1:
            raise ValueError("rank fact values must be strict positive integers")
    elif fact_name in score_names:
        nullable_scores = {
            "dense_score", "sparse_score", "semantic_score", "skill_fit_score",
            "project_evidence_score", "role_direction_score", "ai_tool_score",
            "location_score", "seniority_score", "missing_penalty", "overclaim_penalty",
        }
        if value is None and fact_name in nullable_scores and kind in {
            EvidenceFactKind.RETRIEVAL, EvidenceFactKind.FEATURE
        }:
            return
        if type(value) is not float:
            raise ValueError("score fact values must be strict finite floats")
    elif fact_name == "matched_channels":
        if not isinstance(value, list) or any(item not in {"dense", "sparse"} for item in value):
            raise ValueError("matched_channels must use the closed channel enum")
    elif fact_name in requirement_list_names:
        if not isinstance(value, list) or any(
            not isinstance(item, str) or re.fullmatch(JOB_REQUIREMENT_EVIDENCE_ID_PATTERN, item) is None
            for item in value
        ):
            raise ValueError("requirement diagnostics must contain Job requirement Evidence IDs")
    elif fact_name in label_list_names:
        if not isinstance(value, list) or any(
            not isinstance(item, str)
            or re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9_.:/+-]*(?: [A-Za-z0-9][A-Za-z0-9_.:/+-]*){0,11}",
                item,
            ) is None
            or len(item) > 120
            for item in value
        ):
            raise ValueError("label diagnostics must contain normalized labels")
    elif fact_name in relation_names:
        if value not in set(MatchRelation.__args__):
            raise ValueError("diagnostic relation values must use the closed enum")
    elif fact_name == "overclaim_level":
        if value not in set(RiskLevelValue.__args__):
            raise ValueError("overclaim level must use the closed enum")
    elif fact_name == "overclaim_reason_count":
        if type(value) is not int or value < 0:
            raise ValueError("diagnostic count values must be strict integers")
    else:
        raise ValueError("unsupported evidence fact name")


def _validate_candidate_ownership(candidate, facts: list) -> None:
    rank = candidate.result_rank
    prefixes = (
        (candidate.skills, f"candidate:{rank}:skill:"),
        (candidate.projects, f"candidate:{rank}:project:"),
        (candidate.project_evidence, f"candidate:{rank}:project_evidence:"),
    )
    for items, prefix in prefixes:
        for item in items:
            if not item.evidence_id.startswith(prefix):
                raise ValueError("Candidate evidence rank owner does not match parent")
    project_ids = {item.project_id for item in candidate.projects}
    if any(item.project_id not in project_ids for item in candidate.project_evidence):
        raise ValueError("Candidate project evidence project owner does not match parent")
    for fact in facts:
        if fact.candidate_id != candidate.candidate_id:
            raise ValueError("EvidenceFact Candidate owner does not match parent")
        if _fact_rank(fact.evidence_id) != rank:
            raise ValueError("EvidenceFact rank owner does not match parent")
        fact_name = fact.name.value if isinstance(fact.name, Enum) else fact.name
        if fact.evidence_id.rsplit(":", 1)[-1] != fact_name:
            raise ValueError("evidence namespace name must match fact name")
        _validate_fact_value(fact.kind, fact.name, fact.value)


def _candidate_identity_is_canonical(candidates: list) -> None:
    candidate_ids = [candidate.candidate_id for candidate in candidates]
    ranks = [candidate.result_rank for candidate in candidates]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("candidate_id values must be unique")
    if len(ranks) != len(set(ranks)):
        raise ValueError("result_rank values must be unique")
    if ranks != list(range(1, len(ranks) + 1)):
        raise ValueError("Candidates must use contiguous ascending result_rank order")


def _candidate_identity_from_input(value) -> tuple[list[str], list[int]]:
    candidates = value.get("candidates", []) if isinstance(value, dict) else []
    candidate_ids = [
        item.get("candidate_id") for item in candidates if isinstance(item, dict)
    ]
    ranks = [item.get("result_rank") for item in candidates if isinstance(item, dict)]
    return candidate_ids, ranks


def _validate_candidate_identity_input(value) -> None:
    candidate_ids, ranks = _candidate_identity_from_input(value)
    if any(not isinstance(candidate_id, str) for candidate_id in candidate_ids):
        raise ValueError("candidate_id values must be strings")
    if any(type(rank) is not int for rank in ranks):
        raise ValueError("result_rank values must be strict integers")
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("candidate_id values must be unique")
    if len(ranks) != len(set(ranks)):
        raise ValueError("result_rank values must be unique")
    if ranks and ranks != list(range(1, len(ranks) + 1)):
        raise ValueError("Candidates must use contiguous ascending result_rank order")


def _candidate_facts(candidate) -> list:
    if isinstance(candidate, HistoricalCandidateEvidence):
        return list(candidate.facts)
    return _provider_candidate_evidence_items(candidate)


def _provider_candidate_evidence_items(candidate: ProviderCandidateEvidence) -> list:
    items = []
    for group in (candidate.retrieval, candidate.features, candidate.ranking, candidate.diagnostics):
        items.extend(
            value
            for value in group.__dict__.values()
            if value is not None
        )
    if candidate.top1_comparison is not None:
        items.extend(
            value
            for name, value in candidate.top1_comparison.__dict__.items()
            if name not in {"top1_candidate_id", "top1_rank"} and value is not None
        )
    return items


def _evidence_ids(job: ProviderJobEvidence, candidates: list):
    for requirement in job.requirements:
        yield requirement.evidence_id
    for candidate in candidates:
        for item in candidate.skills:
            yield item.evidence_id
        for item in candidate.projects:
            yield item.evidence_id
        for item in candidate.project_evidence:
            yield item.evidence_id
        for item in _candidate_facts(candidate):
            yield item.evidence_id


def _validate_rewrite_support_refs(operation, result_rank: int) -> None:
    operation_name = operation.operation
    allowed_candidate_kinds = {
        "surface_existing_skill": {"skill", "project", "project_evidence"},
        "link_skill_to_project": {"skill", "project", "project_evidence"},
        "clarify_evidence_status": {"skill", "project", "project_evidence"},
        "reorder_existing_claim": {"skill", "project", "project_evidence"},
    }
    for ref in operation.evidence_refs:
        if ref.startswith("candidate:"):
            parts = ref.split(":", 3)
            if len(parts) != 4 or int(parts[1]) != result_rank:
                raise ValueError("Rewrite evidence Candidate rank must match output rank")
            if operation_name not in allowed_candidate_kinds or parts[2] not in allowed_candidate_kinds[operation_name]:
                raise ValueError("Rewrite evidence namespace is incompatible with operation")
        elif ref.startswith("job_requirement:"):
            if operation_name not in {"clarify_evidence_status", "state_gap_explicitly"}:
                raise ValueError("Job requirement evidence is incompatible with operation")
        elif ref.startswith("diagnostic:"):
            diagnostic_name = ref.rsplit(":", 1)[-1]
            if (
                operation_name != "state_gap_explicitly"
                or _fact_rank(ref) != result_rank
                or diagnostic_name not in {
                    "weak_matched_must_have_requirement_ids",
                    "missing_must_have_requirement_ids",
                }
            ):
                raise ValueError("Diagnostic rewrite evidence is incompatible with operation")
        else:
            raise ValueError("Rewrite evidence namespace is not allowed")


class InternalEvidenceBundleV1(Phase9ContractModel):
    contract_version: Literal["evidence_bundle_v1"]
    source: MatchRunEvidenceSource
    job: HistoricalJobEvidence
    runtime_provenance: RuntimeProvenance
    workflow_trace: List[WorkflowTraceItem] = Field(min_length=1, max_length=20)
    candidates: List[HistoricalCandidateEvidence] = Field(min_length=1, max_length=10)

    @model_validator(mode="before")
    @classmethod
    def candidate_identity_is_unique_and_ordered(cls, value):
        _validate_candidate_identity_input(value)
        return value

    @model_validator(mode="after")
    def evidence_contract_is_consistent(self) -> "InternalEvidenceBundleV1":
        _candidate_identity_is_canonical(self.candidates)
        identifiers = list(_evidence_ids(self.job, self.candidates))
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("evidence IDs must be unique inside a contract")
        is_ce = self.source.ranking_variant == "cross_encoder_experiment"
        if is_ce != (self.runtime_provenance.cross_encoder is not None):
            raise ValueError("Cross-Encoder provenance must match ranking variant")
        for candidate in self.candidates:
            ranking_names = {
                fact.name.value if isinstance(fact.name, Enum) else fact.name
                for fact in candidate.facts
                if fact.kind == EvidenceFactKind.RANKING
            }
            ce_names = {
                RankingFactName.CROSS_ENCODER_RANK.value,
                RankingFactName.CROSS_ENCODER_SCORE_RAW.value,
            }
            if is_ce and not ce_names <= ranking_names:
                raise ValueError("Cross-Encoder Candidate ranking facts are required")
            if not is_ce and ce_names & ranking_names:
                raise ValueError("LTR evidence cannot contain Cross-Encoder ranking facts")
            for fact in candidate.facts:
                if (
                    fact.kind == EvidenceFactKind.RANKING
                    and fact.name == RankingFactName.RESULT_RANK.value
                    and fact.value != candidate.result_rank
                ):
                    raise ValueError("result_rank fact must match Candidate rank")
                if fact.kind == EvidenceFactKind.COMPARISON:
                    if candidate.result_rank == 1:
                        raise ValueError("rank-1 Candidate cannot contain a top-1 comparison")
                    if fact.comparison_candidate_id != self.candidates[0].candidate_id:
                        raise ValueError("comparison fact must reference the rank-1 Candidate")
        return self


class ProviderEvidenceV1(Phase9ContractModel):
    contract_version: Literal["provider_evidence_v1"]
    job: ProviderJobEvidence
    candidates: List[ProviderCandidateEvidence] = Field(min_length=1, max_length=10)

    @model_validator(mode="before")
    @classmethod
    def candidate_identity_is_unique_and_ordered(cls, value):
        _validate_candidate_identity_input(value)
        return value

    @model_validator(mode="after")
    def evidence_ids_are_unique(self) -> "ProviderEvidenceV1":
        _candidate_identity_is_canonical(self.candidates)
        identifiers = list(_evidence_ids(self.job, self.candidates))
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("evidence IDs must be unique inside a contract")
        for candidate in self.candidates:
            if candidate.top1_comparison is not None:
                if candidate.top1_comparison.top1_candidate_id != self.candidates[0].candidate_id:
                    raise ValueError("provider comparison must reference the rank-1 Candidate")
        return self


EvidenceRefs = Annotated[List[EvidenceId], Field(min_length=1, max_length=6)]


class GroundedSummary(Phase9ContractModel):
    text: BoundedText
    evidence_refs: EvidenceRefs


class MatchReasonCategory(str, Enum):
    SKILL_ALIGNMENT = "skill_alignment"
    PROJECT_EVIDENCE = "project_evidence"
    ROLE_DIRECTION = "role_direction"
    AI_TOOLING = "ai_tooling"
    LOCATION = "location"
    SENIORITY = "seniority"
    RANKING_CONTEXT = "ranking_context"


class MatchReason(Phase9ContractModel):
    category: MatchReasonCategory
    text: BoundedText
    evidence_refs: EvidenceRefs


class RiskCategory(str, Enum):
    MISSING_REQUIREMENT = "missing_requirement"
    WEAK_EVIDENCE = "weak_evidence"
    ROLE_DIRECTION_MISMATCH = "role_direction_mismatch"
    LOCATION_MISMATCH = "location_mismatch"
    SENIORITY_MISMATCH = "seniority_mismatch"
    OVERCLAIM_SIGNAL = "overclaim_signal"
    RANKING_COMPARISON = "ranking_comparison"


class RiskPoint(Phase9ContractModel):
    category: RiskCategory
    text: BoundedText
    evidence_refs: EvidenceRefs


class MissingSkill(Phase9ContractModel):
    requirement_id: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    requirement_text: Annotated[str, StringConstraints(min_length=5, max_length=240)]
    priority: RequirementPriority
    status: Literal[RequirementStatus.PARTIAL, RequirementStatus.MISSING]
    evidence_status: RequirementEvidenceStatus
    evidence_refs: EvidenceRefs


class InterviewQuestion(Phase9ContractModel):
    question: Annotated[str, StringConstraints(min_length=5, max_length=240)]
    rationale: Annotated[str, StringConstraints(min_length=5, max_length=240)]
    evidence_refs: EvidenceRefs


class WhyNotTop1(Phase9ContractModel):
    category: Literal[RiskCategory.RANKING_COMPARISON]
    text: BoundedText
    evidence_refs: EvidenceRefs


class SurfaceExistingSkill(Phase9ContractModel):
    operation: Literal["surface_existing_skill"]
    skill_evidence_id: CandidateSkillEvidenceId
    evidence_refs: EvidenceRefs


class LinkSkillToProject(Phase9ContractModel):
    operation: Literal["link_skill_to_project"]
    skill_evidence_id: CandidateSkillEvidenceId
    project_evidence_id: Union[
        CandidateProjectEvidenceId, CandidateProjectRecordEvidenceId
    ]
    evidence_refs: EvidenceRefs


class ClarifyEvidenceStatus(Phase9ContractModel):
    operation: Literal["clarify_evidence_status"]
    evidence_record_id: CandidateProjectRecordEvidenceId
    evidence_refs: EvidenceRefs


class ReorderExistingClaim(Phase9ContractModel):
    operation: Literal["reorder_existing_claim"]
    claim_evidence_id: Union[
        CandidateSkillEvidenceId,
        CandidateProjectEvidenceId,
        CandidateProjectRecordEvidenceId,
    ]
    evidence_refs: EvidenceRefs


class StateGapExplicitly(Phase9ContractModel):
    operation: Literal["state_gap_explicitly"]
    requirement_evidence_id: JobRequirementEvidenceId
    evidence_refs: EvidenceRefs


RewriteOperation = Annotated[
    Union[
        SurfaceExistingSkill,
        LinkSkillToProject,
        ClarifyEvidenceStatus,
        ReorderExistingClaim,
        StateGapExplicitly,
    ],
    Field(discriminator="operation"),
]


class ProfileRewriteSuggestion(Phase9ContractModel):
    operations: List[RewriteOperation] = Field(min_length=1, max_length=3)


class CandidateExplanationOutput(Phase9ContractModel):
    output_schema_version: Literal["explanation_output_v1"]
    candidate_id: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    result_rank: StrictPositiveRank
    summary: GroundedSummary
    match_reasons: List[MatchReason] = Field(min_length=2, max_length=4)
    risk_points: List[RiskPoint] = Field(max_length=4)
    missing_skills: List[MissingSkill] = Field(max_length=50)
    interview_questions: List[InterviewQuestion] = Field(max_length=3)
    why_not_top1: Optional[WhyNotTop1]
    profile_rewrite_suggestion: Optional[ProfileRewriteSuggestion]

    @model_validator(mode="after")
    def top_one_semantics_are_structural(self) -> "CandidateExplanationOutput":
        if self.result_rank == 1 and self.why_not_top1 is not None:
            raise ValueError("rank one must not have why_not_top1")
        if self.result_rank > 1 and self.why_not_top1 is None:
            raise ValueError("non-top-one output requires why_not_top1")
        if self.profile_rewrite_suggestion is not None:
            for operation in self.profile_rewrite_suggestion.operations:
                _validate_rewrite_support_refs(operation, self.result_rank)
                for name, value in operation.model_dump(mode="json").items():
                    if not name.endswith("_evidence_id") or not value.startswith(
                        "candidate:"
                    ):
                        continue
                    if _fact_rank(value) != self.result_rank:
                        raise ValueError(
                            "Rewrite evidence Candidate rank must match output rank"
                        )
        return self


class ExplanationOutputV1(Phase9ContractModel):
    contract_version: Literal["explanation_output_v1"]
    candidates: List[CandidateExplanationOutput] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def candidate_order_is_rank_order(self) -> "ExplanationOutputV1":
        ranks = [item.result_rank for item in self.candidates]
        if ranks != sorted(ranks) or len(ranks) != len(set(ranks)):
            raise ValueError("Candidate outputs must have unique ascending ranks")
        return self


class ExplanationRunRecord(Phase9ContractModel):
    explanation_run_id: Annotated[str, StringConstraints(min_length=1, max_length=36)]
    match_run_id: Annotated[str, StringConstraints(min_length=1, max_length=36)]
    request_id: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    status: ExplanationRunStatus
    requested_top_k: int = Field(ge=1, le=10)
    effective_top_k: Optional[int] = Field(default=None, ge=1, le=10)
    explanation_count: int = Field(default=0, ge=0, le=10)
    evidence_bundle_version: Optional[Literal["evidence_bundle_v1"]] = None
    evidence_bundle_fingerprint: Optional[Fingerprint] = None
    evidence_bundle_json: Optional[InternalEvidenceBundleV1] = None
    provider_evidence_version: Optional[Literal["provider_evidence_v1"]] = None
    provider_evidence_fingerprint: Optional[Fingerprint] = None
    provider_evidence_json: Optional[ProviderEvidenceV1] = None
    output_schema_version: Optional[Literal["explanation_output_v1"]] = None
    provider_kind: Optional[Annotated[str, StringConstraints(min_length=1, max_length=40)]] = None
    provider_name: Optional[Annotated[str, StringConstraints(min_length=1, max_length=80)]] = None
    configured_model: Optional[
        Annotated[str, StringConstraints(min_length=1, max_length=160)]
    ] = None
    observed_model: Optional[
        Annotated[str, StringConstraints(min_length=1, max_length=160)]
    ] = None
    provider_configuration_fingerprint: Optional[Fingerprint] = None
    prompt_version: Optional[Annotated[str, StringConstraints(min_length=1, max_length=64)]] = None
    prompt_fingerprint: Optional[Fingerprint] = None
    attempt_count: int = Field(default=0, ge=0, le=2)
    repaired: bool = False
    result_fingerprint: Optional[Fingerprint] = None
    error_code: Optional[
        Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,79}$")]
    ] = None
    error_detail_safe: Optional[
        Annotated[str, StringConstraints(min_length=1, max_length=500, pattern=r"^[^\r\n]+$")]
    ] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @field_validator("error_detail_safe")
    @classmethod
    def error_detail_excludes_debug_and_secret_material(
        cls, value: Optional[str]
    ) -> Optional[str]:
        if value is None:
            return value
        lowered = value.casefold()
        forbidden = (
            "traceback",
            "postgresql://",
            "authorization:",
            "bearer ",
            "api_key",
            "password",
        )
        has_windows_path = (
            len(value) >= 4
            and value[0].isalpha()
            and value[1] == ":"
            and value[2] == "\\"
        )
        if any(token in lowered for token in forbidden) or has_windows_path:
            raise ValueError("safe error detail contains forbidden debug or secret material")
        return value

    @model_validator(mode="after")
    def lifecycle_is_truthful(self) -> "ExplanationRunRecord":
        if self.effective_top_k is not None and self.effective_top_k > self.requested_top_k:
            raise ValueError("effective_top_k cannot exceed requested_top_k")
        if self.repaired and self.attempt_count < 2:
            raise ValueError("repaired requires at least two attempts")

        evidence = (
            self.evidence_bundle_version,
            self.evidence_bundle_fingerprint,
            self.evidence_bundle_json,
        )
        provider_evidence = (
            self.provider_evidence_version,
            self.provider_evidence_fingerprint,
            self.provider_evidence_json,
        )
        prompt = (self.prompt_version, self.prompt_fingerprint)
        for values, label in (
            (evidence, "evidence bundle"),
            (provider_evidence, "provider evidence"),
            (prompt, "prompt provenance"),
        ):
            if any(value is not None for value in values) and not all(
                value is not None for value in values
            ):
                raise ValueError(f"{label} must be absent or complete")

        if self.status == ExplanationRunStatus.RUNNING:
            if self.completed_at or self.error_code or self.error_detail_safe:
                raise ValueError("running explanation run cannot be terminal")
            if self.explanation_count or self.result_fingerprint:
                raise ValueError("running explanation run cannot have results")
            return self

        if self.completed_at is None:
            raise ValueError("terminal explanation run requires completed_at")
        if self.status == ExplanationRunStatus.FAILED:
            if not self.error_code or not self.error_detail_safe:
                raise ValueError("failed explanation run requires a safe error")
            if self.explanation_count or self.result_fingerprint:
                raise ValueError("failed explanation run cannot have completed results")
            return self

        required = (
            self.effective_top_k,
            *evidence,
            *provider_evidence,
            self.output_schema_version,
            self.provider_kind,
            self.provider_name,
            self.configured_model,
            self.provider_configuration_fingerprint,
            *prompt,
            self.result_fingerprint,
        )
        if any(value is None for value in required):
            raise ValueError("completed explanation run requires complete historical contract")
        if self.attempt_count < 1:
            raise ValueError("completed explanation run requires at least one attempt")
        if self.explanation_count != self.effective_top_k or self.explanation_count < 1:
            raise ValueError("completed explanation run count must equal effective_top_k")
        if self.error_code or self.error_detail_safe:
            raise ValueError("completed explanation run cannot have an error")
        return self


__all__ = [
    "CandidateExplanationOutput",
    "EVIDENCE_ID_PATTERN",
    "EvidenceId",
    "ExplanationOutputV1",
    "ExplanationRunRecord",
    "ExplanationRunStatus",
    "InternalEvidenceBundleV1",
    "ProviderEvidenceV1",
]
