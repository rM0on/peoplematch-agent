"""Request-scoped transport handles for canonical V4 recruiter claims."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.explanation.presentation.claims_v4 import RecruiterClaimGraphV4
from app.services.explanation.presentation.decision_frame_v4_1 import (
    HiringDecisionFrameV1, guard_decision_frame_v4_1,
)
from app.services.explanation.presentation.hiring_context_v5 import (
    HiringContextGraphV5, guard_hiring_context_v5,
)


@dataclass(frozen=True)
class ClaimHandleEntryV5:
    handle: str
    claim_id: str
    candidate_id: str
    claim_type: str
    relation_type: str
    concepts: tuple[str, ...]
    allowed_frame_roles: tuple[str, ...]


@dataclass(frozen=True)
class ClaimHandleBindingV5:
    candidate_id: str
    result_rank: int
    entries: tuple[ClaimHandleEntryV5, ...]

    def handle_for(self, claim_id: str) -> str:
        for entry in self.entries:
            if entry.claim_id == claim_id:
                return entry.handle
        raise ValueError("claim_not_in_current_request")

    def allowed_handles(self, field: str) -> tuple[str, ...]:
        if field not in {"decision_summary", "why_consider", "technical_signal",
                         "interview_focus", "uncertainty"}:
            raise ValueError("unknown_narrative_field")
        return tuple(entry.handle for entry in self.entries if field in entry.allowed_frame_roles)

    def resolve(self, handles: list[str], *, field: str) -> list[str]:
        if not handles or len(handles) > 4 or len(handles) != len(set(handles)):
            raise ValueError("invalid_claim_handles")
        lookup = {entry.handle: entry for entry in self.entries}
        allowed = set(self.allowed_handles(field))
        resolved: list[str] = []
        for handle in handles:
            if handle not in lookup or handle not in allowed:
                raise ValueError("unknown_or_wrong_role_claim_handle")
            entry = lookup[handle]
            if entry.candidate_id != self.candidate_id:
                raise ValueError("claim_handle_owner_mismatch")
            resolved.append(entry.claim_id)
        return resolved


def build_claim_handle_binding_v5(
    graph: RecruiterClaimGraphV4, frame: HiringDecisionFrameV1,
    context: HiringContextGraphV5,
) -> ClaimHandleBindingV5:
    guard_decision_frame_v4_1(frame, graph=graph)
    guard_hiring_context_v5(context, graph=graph, frame=frame)
    if any(claim.candidate_id != graph.candidate_id for claim in graph.claims):
        raise ValueError("claim_graph_candidate_mismatch")
    signal_refs = {ref for item in frame.current_signal for ref in item.claim_refs}
    verify_refs = {ref for item in frame.what_to_verify for ref in item.claim_refs}
    risk_refs = {ref for item in frame.risk_boundary for ref in item.claim_refs}
    review_refs = {ref for item in frame.why_consider for ref in item.claim_refs}
    entries = []
    for index, claim in enumerate(sorted(graph.claims, key=lambda item: item.claim_id), 1):
        roles: list[str] = []
        if claim.claim_id in review_refs and claim.claim_type == "review_recommendation":
            roles.append("decision_summary")
        if claim.claim_id in signal_refs and claim.claim_type in {
            "technical_alignment", "skill_requirement_match",
        }:
            roles.extend(("why_consider", "technical_signal"))
        if claim.claim_id in verify_refs and claim.claim_type in {
            "interview_focus", "project_depth_validation",
        }:
            roles.extend(("interview_focus", "uncertainty"))
        if claim.claim_id in risk_refs and claim.claim_type == "interview_focus":
            if "uncertainty" not in roles:
                roles.append("uncertainty")
        if roles:
            entries.append(ClaimHandleEntryV5(
                handle=f"C{index:02d}", claim_id=claim.claim_id,
                candidate_id=claim.candidate_id, claim_type=claim.claim_type,
                relation_type=claim.relation_type, concepts=claim.concepts,
                allowed_frame_roles=tuple(roles),
            ))
    binding = ClaimHandleBindingV5(graph.candidate_id, graph.result_rank, tuple(entries))
    if any(not binding.allowed_handles(field) for field in (
        "decision_summary", "why_consider", "technical_signal", "interview_focus", "uncertainty"
    )):
        raise ValueError("insufficient_claim_handles")
    return binding


__all__ = ["ClaimHandleEntryV5", "ClaimHandleBindingV5", "build_claim_handle_binding_v5"]
