"""Opt-in, synthetic-only field diagnostics; never persisted or sent to providers."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.explanation.presentation.claims_v4 import RecruiterClaimGraphV4
from app.services.explanation.presentation.contracts_v5 import RecruiterNarrativeV5
from app.services.explanation.presentation.decision_frame_v4_1 import HiringDecisionFrameV1
from app.services.explanation.presentation.hiring_context_v5 import HiringContextGraphV5
from app.services.explanation.presentation.service_v5 import diagnose_narrative_v5


@dataclass(frozen=True)
class V5SemanticDiagnostic:
    run_id: str
    field: str
    item_index: int | None
    generated_text: str
    claim_refs: tuple[str, ...]
    claim_types: tuple[str, ...]
    source_fact_ids: tuple[str, ...]
    source_fact_types: tuple[str, ...]
    decision_frame_type: str
    validator_pass: bool
    validator_reason_code: str | None
    validator_rule: str | None
    guard_pass: bool
    guard_reason_code: str | None
    guard_actual_section: str | None
    classification_pending: bool = True


_REASON_CODES = {
    "unknown_or_duplicate_claim_ref": "CLAIM_REF_MISSING",
    "decision_frame_unknown_claim": "CLAIM_REF_MISSING",
    "claim_type_or_owner_mismatch": "CLAIM_TYPE_MISMATCH",
    "decision_frame_claim_type_or_owner_mismatch": "CLAIM_TYPE_MISMATCH",
    "claim_outside_decision_frame_section": "FRAME_TYPE_MISMATCH",
    "candidate_deficiency_not_inferred_from_open_requirement": "OPEN_REQUIREMENT_AS_DEFICIENCY",
    "forbidden_responsibility_scale_outcome_or_hiring_decision": "FORBIDDEN_FACT_UPGRADE",
    "unsupported_ability_conclusion": "CAPABILITY_UPGRADE",
    "technical_concept_outside_claim_scope": "TECHNICAL_CONCEPT_OUTSIDE_SCOPE",
    "unrecognized_technical_surface": "UNRECOGNIZED_TECHNICAL_SURFACE",
    "technical_observation_missing": "TECHNICAL_OBSERVATION_MISSING",
    "missing_cited_technical_direction": "MISSING_CITED_TECHNICAL_DIRECTION",
    "verification_modality_missing": "VERIFICATION_MODALITY_MISSING",
    "review_action_missing": "REVIEW_ACTION_MISSING",
}


def collect_v5_semantic_diagnostics(
    narrative: RecruiterNarrativeV5, *, run_id: str,
    graph: RecruiterClaimGraphV4, frame: HiringDecisionFrameV1,
    context: HiringContextGraphV5,
    known_claim_owners: dict[str, str] | None = None,
) -> tuple[V5SemanticDiagnostic, ...]:
    """Capture only individual synthetic paragraphs and their verified provenance.

    The optional owner registry is required to distinguish a *known* foreign
    Claim ID from an unknown ID. It never changes validation decisions.
    """
    if not run_id or not run_id.startswith("synthetic-"):
        raise ValueError("synthetic_diagnostic_run_id_required")
    failures = diagnose_narrative_v5(narrative, graph=graph, frame=frame, context=context)
    claims = {claim.claim_id: claim for claim in graph.claims}
    facts = {fact.fact_id: fact for fact in graph.fact_graph.facts}
    rows: list[V5SemanticDiagnostic] = []
    sections = (("decision_summary", (narrative.decision_summary,)),
                ("why_consider", narrative.why_consider),
                ("technical_signal", narrative.technical_signal),
                ("interview_focus", narrative.interview_focus),
                ("uncertainty", narrative.uncertainty))
    for section, paragraphs in sections:
        for index, paragraph in enumerate(paragraphs):
            field = section if section == "decision_summary" else f"{section}[{index}]"
            selected = tuple(claims[ref] for ref in paragraph.claim_refs if ref in claims)
            source_ids = tuple(sorted({fact_id for claim in selected for fact_id in claim.source_fact_ids}))
            validator_rule = failures.get(field)
            guard_rule = failures.get(f"{field}.frame")
            foreign_ref = any(known_claim_owners and ref in known_claim_owners
                              and known_claim_owners[ref] != graph.candidate_id
                              for ref in paragraph.claim_refs)
            validator_code = _REASON_CODES.get(validator_rule, "VALIDATOR_REJECTED") if validator_rule else None
            guard_code = _REASON_CODES.get(guard_rule, "GUARD_REJECTED") if guard_rule else None
            if foreign_ref:
                if validator_rule == "unknown_or_duplicate_claim_ref":
                    validator_code = "CLAIM_OWNER_MISMATCH"
                if guard_rule == "decision_frame_unknown_claim":
                    guard_code = "CLAIM_OWNER_MISMATCH"
            frame_type = {
                "decision_summary": "why_consider",
                "why_consider": "current_signal",
                "technical_signal": "current_signal",
                "interview_focus": "what_to_verify",
                "uncertainty": "risk_boundary" if any(
                    ref in {entry_ref for entry in frame.risk_boundary for entry_ref in entry.claim_refs}
                    for ref in paragraph.claim_refs) else "what_to_verify",
            }[section]
            if any(ref not in claims for ref in paragraph.claim_refs):
                frame_type = "unresolved_claim_ref"
            rows.append(V5SemanticDiagnostic(
                run_id=run_id, field=field,
                item_index=None if section == "decision_summary" else index,
                generated_text=paragraph.text, claim_refs=tuple(paragraph.claim_refs),
                claim_types=tuple(claim.claim_type for claim in selected),
                source_fact_ids=source_ids,
                source_fact_types=tuple(facts[fact_id].kind for fact_id in source_ids if fact_id in facts),
                decision_frame_type=frame_type,
                validator_pass=validator_rule is None,
                validator_reason_code=validator_code, validator_rule=validator_rule,
                guard_pass=guard_rule is None, guard_reason_code=guard_code,
                guard_actual_section=field if guard_rule else None,
            ))
    return tuple(rows)


__all__ = ["V5SemanticDiagnostic", "collect_v5_semantic_diagnostics"]
