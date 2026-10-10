"""Deterministic hiring context from canonical V4 claims and V4.1 frame."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.explanation.presentation.claims_v4 import RecruiterClaimGraphV4
from app.services.explanation.presentation.decision_frame_v4_1 import (
    HiringDecisionFrameV1, guard_decision_frame_v4_1,
)


@dataclass(frozen=True)
class HiringContextItemV5:
    claim_refs: tuple[str, ...]
    concepts: tuple[str, ...]
    job_relation: str


@dataclass(frozen=True)
class HiringContextGraphV5:
    candidate_id: str
    result_rank: int
    candidate_signal: tuple[HiringContextItemV5, ...]
    why_this_matters: tuple[HiringContextItemV5, ...]
    interview_focus: tuple[HiringContextItemV5, ...]
    uncertainty_boundary: tuple[HiringContextItemV5, ...]


def build_hiring_context_v5(
    graph: RecruiterClaimGraphV4, frame: HiringDecisionFrameV1,
) -> HiringContextGraphV5:
    """Organize allowed relationships, without authoring new facts or candidate claims."""
    guard_decision_frame_v4_1(frame, graph=graph)
    lookup = {claim.claim_id: claim for claim in graph.claims}

    def items(entries, relation: str) -> tuple[HiringContextItemV5, ...]:
        return tuple(HiringContextItemV5(
            claim_refs=entry.claim_refs,
            concepts=entry.concepts,
            job_relation=relation,
        ) for entry in entries)

    aligned = {parent for review in graph.claims if review.claim_type == "review_recommendation"
               for parent in review.source_claim_ids if parent in lookup
               and lookup[parent].claim_type == "technical_alignment"}
    why_entries = tuple(entry for entry in frame.current_signal
                        if any(ref in aligned for ref in entry.claim_refs))
    if not why_entries or not frame.current_signal or not frame.what_to_verify:
        raise ValueError("insufficient_hiring_context_claims")
    uncertainty_entries = frame.risk_boundary or tuple(
        entry for entry in frame.what_to_verify
        if any(lookup[ref].claim_type == "project_depth_validation" for ref in entry.claim_refs))
    if not uncertainty_entries:
        raise ValueError("missing_uncertainty_boundary")
    return HiringContextGraphV5(
        candidate_id=graph.candidate_id,
        result_rank=graph.result_rank,
        candidate_signal=items(frame.current_signal, "observed_technical_direction"),
        why_this_matters=items(why_entries, "job_relevant_observation"),
        interview_focus=items(frame.what_to_verify, "next_interview_question"),
        uncertainty_boundary=items(uncertainty_entries, "information_not_yet_confirmed"),
    )


def guard_hiring_context_v5(
    context: HiringContextGraphV5, *, graph: RecruiterClaimGraphV4,
    frame: HiringDecisionFrameV1,
) -> None:
    if context != build_hiring_context_v5(graph, frame):
        raise ValueError("hiring_context_not_canonical_for_candidate")


__all__ = ["HiringContextItemV5", "HiringContextGraphV5",
           "build_hiring_context_v5", "guard_hiring_context_v5"]
