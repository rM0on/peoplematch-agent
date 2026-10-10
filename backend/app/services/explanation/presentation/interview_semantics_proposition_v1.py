"""Source-backed question content selection; no facts or final prose are generated."""

from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from app.schemas.shared import ContractModel
from app.services.explanation.presentation.adapter import NarrativeProjection
from app.services.explanation.presentation.contracts_proposition_v1 import RecruiterPropositionSetV1
from app.services.explanation.presentation.propositions_v1 import validate_interview_recruiter_propositions_v1


QuestionKindV1 = Literal["participation_existence", "requirement_verification"]
FollowUpGateV1 = Literal["personal_participation_confirmation_required",
                         "requirement_practice_confirmation_required"]
ReviewActionV1 = Literal["priority_human_review", "conditional_targeted_screen"]


class InterviewQuestionIntentV1(ContractModel):
    """One question target and explicit prerequisites, not a second Proposition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str = Field(min_length=1)
    result_rank: int = Field(ge=1)
    question_kind: QuestionKindV1
    target_requirement_ref: str = Field(min_length=1)
    target_topic: str = Field(min_length=1)
    supporting_proposition_ids: tuple[str, ...] = Field(min_length=1, max_length=1)
    direct_question_level: QuestionKindV1
    follow_up_gate: FollowUpGateV1
    decision_responsibility_gate: Literal["personal_participation_confirmation_required"]
    decision_rationale_gate: Literal["personal_decision_confirmation_required"]
    review_action: ReviewActionV1

    @model_validator(mode="after")
    def enforce_question_preconditions(self) -> InterviewQuestionIntentV1:
        if not self.target_requirement_ref.startswith("job_requirement:"):
            raise ValueError("interview_requirement_source_invalid")
        expected_gate: FollowUpGateV1 = (
            "personal_participation_confirmation_required"
            if self.question_kind == "participation_existence"
            else "requirement_practice_confirmation_required"
        )
        if self.direct_question_level != self.question_kind or self.follow_up_gate != expected_gate:
            raise ValueError("interview_question_prerequisite_mismatch")
        if (self.review_action == "conditional_targeted_screen"
                and self.question_kind != "requirement_verification"):
            raise ValueError("conditional_screen_cannot_assume_interview_depth")
        return self


def _role_overlap(role_title: str, requirement_terms: tuple[str, ...]) -> int:
    role_tokens = {token.casefold() for token in role_title.split()}
    return max((len(role_tokens & {token.casefold() for token in term.split()})
                for term in requirement_terms), default=0)


def build_interview_question_intent_v1(
    projection: NarrativeProjection, propositions: RecruiterPropositionSetV1,
    *, review_proposition_id: str,
) -> InterviewQuestionIntentV1:
    """Choose the first unresolved *job* question, never a decorative project term."""
    validate_interview_recruiter_propositions_v1(propositions, projection=projection)
    reviews = [item for item in propositions.propositions
               if item.kind == "human_review_recommendation"
               and item.proposition_id == review_proposition_id]
    if len(reviews) != 1:
        raise ValueError("interview_review_action_missing_or_ambiguous")
    priority = reviews[0].predicate == "prioritize_technical_review"
    if reviews[0].predicate not in {"prioritize_technical_review", "consider_targeted_screen"}:
        raise ValueError("interview_review_action_invalid")

    candidates = []
    for requirement_ref in sorted(projection.positive_refs):
        if not requirement_ref.startswith("job_requirement:"):
            continue
        requirement_terms = projection.facts.get(requirement_ref, ())
        if not requirement_terms or any(not term.strip() for term in requirement_terms):
            raise ValueError("interview_requirement_source_missing")
        for target in propositions.propositions:
            if target.kind != "interview_target":
                continue
            if priority:
                if target.predicate != "verify_project_scope":
                    continue
                supported = any(
                    alignment.kind == "technical_alignment"
                    and requirement_ref in alignment.job_requirement_refs
                    and set(alignment.topic_terms) & set(target.topic_terms)
                    and set(alignment.evidence_refs) & set(target.evidence_refs)
                    for alignment in propositions.propositions
                )
            else:
                supported = (target.predicate == "verify_open_requirement"
                             and requirement_ref in target.job_requirement_refs)
            if supported:
                candidates.append((requirement_ref, requirement_terms, target))
    if not candidates:
        raise ValueError("interview_question_source_missing")
    requirement_ref, terms, target = min(
        candidates,
        key=lambda entry: (
            -_role_overlap(projection.role_title, entry[1]),
            entry[0], entry[2].proposition_id,
        ),
    )
    kind: QuestionKindV1 = ("participation_existence" if priority else "requirement_verification")
    return InterviewQuestionIntentV1(
        candidate_id=propositions.candidate_id,
        result_rank=propositions.result_rank,
        question_kind=kind,
        target_requirement_ref=requirement_ref,
        target_topic=terms[0],
        supporting_proposition_ids=(target.proposition_id,),
        direct_question_level=kind,
        follow_up_gate=("personal_participation_confirmation_required" if priority
                        else "requirement_practice_confirmation_required"),
        decision_responsibility_gate="personal_participation_confirmation_required",
        decision_rationale_gate="personal_decision_confirmation_required",
        review_action=("priority_human_review" if priority else "conditional_targeted_screen"),
    )


__all__ = ["InterviewQuestionIntentV1", "build_interview_question_intent_v1"]
