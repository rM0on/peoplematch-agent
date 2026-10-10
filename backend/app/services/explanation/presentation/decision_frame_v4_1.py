"""Deterministic hiring intent over V4 claims; never creates candidate facts."""

from __future__ import annotations

from dataclasses import dataclass
import re

from app.services.explanation.presentation.claims_v4 import (
    RecruiterClaimGraphV4, build_recruiter_claim_graph_v4,
)
from app.services.explanation.presentation.contracts_v4 import (
    RecruiterClaimV1, RecruiterNarrativeV4,
)


@dataclass(frozen=True)
class DecisionFrameEntryV1:
    claim_refs: tuple[str, ...]
    concepts: tuple[str, ...]


@dataclass(frozen=True)
class HiringDecisionFrameV1:
    candidate_id: str
    result_rank: int
    why_consider: tuple[DecisionFrameEntryV1, ...]
    what_to_verify: tuple[DecisionFrameEntryV1, ...]
    current_signal: tuple[DecisionFrameEntryV1, ...]
    risk_boundary: tuple[DecisionFrameEntryV1, ...]


_MAPPING = {
    ("technical_alignment", "observed_requirement_overlap", "technical_direction"):
        frozenset({"why_consider", "current_signal"}),
    ("project_depth_validation", "verify_observed_scope", "project_verification"):
        frozenset({"why_consider", "what_to_verify"}),
    ("skill_requirement_match", "listed_skill_overlap", "skill_observation"):
        frozenset({"current_signal"}),
    ("interview_focus", "verify_observed_scope", "project_verification"):
        frozenset({"what_to_verify"}),
    ("interview_focus", "open_requirement", "open_question"):
        frozenset({"what_to_verify", "risk_boundary"}),
    ("review_recommendation", "alignment_plus_interview_focus", "human_review"):
        frozenset({"why_consider"}),
}


def guard_claim_frame_mapping_v4_1(claim: RecruiterClaimV1, frame_type: str) -> None:
    if frame_type not in _MAPPING.get(
        (claim.claim_type, claim.relation_type, claim.allowed_expression_scope), ()
    ):
        raise ValueError("claim_to_decision_frame_mapping_invalid")


def _entry(*claims: RecruiterClaimV1) -> DecisionFrameEntryV1:
    return DecisionFrameEntryV1(
        tuple(claim.claim_id for claim in claims),
        tuple(sorted({concept for claim in claims for concept in claim.concepts})),
    )


def build_hiring_decision_frame_v4_1(graph: RecruiterClaimGraphV4) -> HiringDecisionFrameV1:
    if graph != build_recruiter_claim_graph_v4(graph.fact_graph):
        raise ValueError("noncanonical_claim_graph")
    claims = {claim.claim_id: claim for claim in graph.claims}
    reviews = [claim for claim in graph.claims if claim.claim_type == "review_recommendation"]
    alignments = [claim for claim in graph.claims if claim.claim_type == "technical_alignment"]
    skill_matches = [claim for claim in graph.claims if claim.claim_type == "skill_requirement_match"]
    depths = [claim for claim in graph.claims if claim.claim_type == "project_depth_validation"]
    focuses = [claim for claim in graph.claims if claim.claim_type == "interview_focus"]
    if not reviews or not alignments or not focuses:
        raise ValueError("insufficient_claims_for_decision_frame")
    for review in reviews:
        guard_claim_frame_mapping_v4_1(review, "why_consider")
        if not all(parent in claims for parent in review.source_claim_ids):
            raise ValueError("review_claim_parent_missing")
    for claim in alignments:
        guard_claim_frame_mapping_v4_1(claim, "current_signal")
    for claim in skill_matches:
        guard_claim_frame_mapping_v4_1(claim, "current_signal")
    for claim in focuses:
        guard_claim_frame_mapping_v4_1(claim, "what_to_verify")
    for claim in depths:
        guard_claim_frame_mapping_v4_1(claim, "what_to_verify")
    open_focuses = [claim for claim in focuses if claim.relation_type == "open_requirement"]
    for claim in open_focuses:
        guard_claim_frame_mapping_v4_1(claim, "risk_boundary")
    return HiringDecisionFrameV1(
        candidate_id=graph.candidate_id,
        result_rank=graph.result_rank,
        why_consider=tuple(_entry(review) for review in reviews),
        what_to_verify=tuple(_entry(claim) for claim in (*focuses, *depths)),
        current_signal=tuple(_entry(claim) for claim in (*alignments, *skill_matches)),
        risk_boundary=tuple(_entry(focus) for focus in open_focuses),
    )


def guard_decision_frame_v4_1(frame: HiringDecisionFrameV1, *, graph: RecruiterClaimGraphV4) -> None:
    if frame != build_hiring_decision_frame_v4_1(graph):
        raise ValueError("decision_frame_not_canonical_for_candidate")


_CANDIDATE_DEFICIENCY = re.compile(
    r"(?:候选人|该候选人|此人|他|她)[^。；？?]{0,36}"
    r"(?:缺少|缺乏|欠缺|不具备|没有|不足以|无法|未掌握)[^。；？?]{0,32}"
    r"(?:能力|经验|技能|实践|资历|背景)|"
    r"(?:候选人|该候选人|此人)[^。；？?]{0,36}(?:能力|经验|技能|实践)[^。；？?]{0,8}"
    r"(?:不足|欠缺)", re.I,
)


def guard_narrative_frame_v4_1(
    narrative: RecruiterNarrativeV4, *, frame: HiringDecisionFrameV1,
    graph: RecruiterClaimGraphV4,
) -> None:
    """Check paragraph intent and absence-vs-inability; V4 still checks claim prose."""
    failures = diagnose_narrative_frame_v4_1(narrative, frame=frame, graph=graph)
    if failures:
        raise ValueError(next(iter(failures.values())))


def diagnose_narrative_frame_v4_1(
    narrative: RecruiterNarrativeV4, *, frame: HiringDecisionFrameV1,
    graph: RecruiterClaimGraphV4,
) -> dict[str, str]:
    """Return actual failing sections without changing the guard's accept/reject rules."""
    guard_decision_frame_v4_1(frame, graph=graph)
    if narrative.candidate_id != frame.candidate_id or narrative.result_rank != frame.result_rank:
        return {"identity": "decision_frame_candidate_mismatch"}
    lookup = {claim.claim_id: claim for claim in graph.claims}
    sections = (
        ("summary", (narrative.summary,), {"review_recommendation"}, frame.why_consider),
        ("strengths", narrative.strengths, {"technical_alignment", "skill_requirement_match"},
         frame.current_signal),
        ("risks", narrative.risks, {"project_depth_validation", "interview_focus"},
         (*frame.what_to_verify, *frame.risk_boundary)),
        ("interview_focus", narrative.interview_focus,
         {"project_depth_validation", "interview_focus"}, frame.what_to_verify),
    )
    failures: dict[str, str] = {}
    for section, paragraphs, allowed_types, entries in sections:
        frame_refs = {ref for entry in entries for ref in entry.claim_refs}
        for index, paragraph in enumerate(paragraphs):
            target = "summary" if section == "summary" else f"{section}[{index}]"
            if not paragraph.claim_refs or any(ref not in lookup for ref in paragraph.claim_refs):
                failures[target] = "decision_frame_unknown_claim"
                continue
            selected = [lookup[ref] for ref in paragraph.claim_refs]
            if any(claim.claim_type not in allowed_types or claim.candidate_id != frame.candidate_id
                   for claim in selected):
                failures[target] = "decision_frame_claim_type_or_owner_mismatch"
                continue
            if any(ref not in frame_refs for ref in paragraph.claim_refs):
                failures[target] = "claim_outside_decision_frame_section"
                continue
            if _CANDIDATE_DEFICIENCY.search(paragraph.text):
                failures[target] = "candidate_deficiency_not_inferred_from_open_requirement"
    return failures


__all__ = ["DecisionFrameEntryV1", "HiringDecisionFrameV1",
           "guard_claim_frame_mapping_v4_1", "build_hiring_decision_frame_v4_1",
           "guard_decision_frame_v4_1", "guard_narrative_frame_v4_1",
           "diagnose_narrative_frame_v4_1"]
