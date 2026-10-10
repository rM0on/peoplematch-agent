"""Typed, presentation-only recruiter propositions (Phase 1 contract)."""

from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from app.schemas.shared import ContractModel


PropositionKindV1 = Literal[
    "project_observation", "listed_skill_observation", "technical_alignment",
    "interview_target", "material_unknown", "human_review_recommendation",
]
NarrativeFieldV1 = Literal[
    "decision_summary", "why_consider", "technical_signal", "interview_focus", "uncertainty",
]
SubjectV1 = Literal[
    "project_material", "candidate_material", "interview_process", "selected_material", "human_review",
]
PredicateV1 = Literal[
    "lists_project_technologies", "lists_skill", "overlaps_job_requirement",
    "verify_project_scope", "verify_open_requirement", "project_scope_not_established",
    "requirement_evidence_not_established", "prioritize_technical_review",
    "consider_targeted_screen",
]
ModalityV1 = Literal["fact", "alignment", "hypothesis", "unknown", "recommendation"]
PolarityV1 = Literal["affirmative", "undetermined"]

# This policy constrains semantic propositions, not permissible Chinese phrases.
_POLICY: dict[str, tuple[str, frozenset[str], str, str, tuple[str, ...]]] = {
    "project_observation": (
        "project_material", frozenset({"lists_project_technologies"}), "fact", "affirmative",
        ("technical_signal",),
    ),
    "listed_skill_observation": (
        "candidate_material", frozenset({"lists_skill"}), "fact", "affirmative",
        ("technical_signal",),
    ),
    "technical_alignment": (
        "candidate_material", frozenset({"overlaps_job_requirement"}), "alignment", "affirmative",
        ("why_consider", "technical_signal"),
    ),
    "interview_target": (
        "interview_process", frozenset({"verify_project_scope", "verify_open_requirement"}),
        "hypothesis", "undetermined", ("interview_focus",),
    ),
    "material_unknown": (
        "selected_material", frozenset({"project_scope_not_established", "requirement_evidence_not_established"}),
        "unknown", "undetermined", ("uncertainty",),
    ),
    "human_review_recommendation": (
        "human_review", frozenset({"prioritize_technical_review", "consider_targeted_screen"}), "recommendation",
        "undetermined", ("decision_summary", "why_consider"),
    ),
}


def proposition_semantics_v1(kind: PropositionKindV1, predicate: PredicateV1) -> tuple[str, str, str, tuple[str, ...]]:
    subject, predicates, modality, polarity, fields = _POLICY[kind]
    if predicate not in predicates:
        raise ValueError("proposition_semantic_upgrade_or_role_mismatch")
    return subject, modality, polarity, fields


class RecruiterPropositionV1(ContractModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    proposition_id: str = Field(min_length=8)
    candidate_id: str = Field(min_length=1)
    result_rank: int = Field(ge=1)
    kind: PropositionKindV1
    subject: SubjectV1
    predicate: PredicateV1
    modality: ModalityV1
    polarity: PolarityV1
    topic_terms: tuple[str, ...] = Field(min_length=1)
    job_requirement_terms: tuple[str, ...] = ()
    source_fact_ids: tuple[str, ...] = Field(min_length=1)
    source_claim_ids: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = Field(min_length=1)
    job_requirement_refs: tuple[str, ...] = ()
    allowed_fields: tuple[NarrativeFieldV1, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def semantic_policy_is_consistent(self) -> RecruiterPropositionV1:
        subject, predicates, modality, polarity, fields = _POLICY[self.kind]
        if (self.subject != subject or self.predicate not in predicates
                or self.modality != modality or self.polarity != polarity
                or self.allowed_fields != fields):
            raise ValueError("proposition_semantic_upgrade_or_role_mismatch")
        requires_job = self.kind in {"technical_alignment", "human_review_recommendation"}
        requires_job |= self.predicate in {"verify_open_requirement", "requirement_evidence_not_established"}
        if requires_job and (not self.job_requirement_refs or not self.job_requirement_terms):
            raise ValueError("proposition_job_requirement_source_missing")
        # A canonical proposition may be supported directly by an exact V2
        # requirement relation even when V3/V4 do not know the technology.
        # The builder/rebuild check, not this shape validator, proves lineage.
        return self


class RecruiterPropositionSetV1(ContractModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal["recruiter_proposition_v1"]
    candidate_id: str = Field(min_length=1)
    result_rank: int = Field(ge=1)
    propositions: tuple[RecruiterPropositionV1, ...]


__all__ = ["RecruiterPropositionV1", "RecruiterPropositionSetV1", "proposition_semantics_v1"]
