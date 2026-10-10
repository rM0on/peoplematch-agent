from __future__ import annotations

import re

from app.services.explanation.presentation.adapter import NarrativeProjection
from app.services.explanation.presentation.contracts_v2_3 import RecruiterNarrativeV2_3
from app.services.explanation.presentation.facts_v2_2 import build_evidence_package_v2_2
from app.services.explanation.presentation.validator_v2 import NarrativeV2ValidationError, _check_section
from app.services.explanation.presentation.validator_v2_2 import (
    _OTHER_CANDIDATE, _UNSUPPORTED_PERSONAL,
)
from app.services.explanation.presentation.validator_v2_1 import (
    _unsupported_personal_work, _unsupported_production_claim,
)


_ABSTRACT = re.compile(
    r"技术视野|技术能力较强|综合能力突出|有较好基础|匹配度较高|匹配度高|"
    r"值得进一步关注|能力突出|能力较强|高度匹配|高度重合|技术实力|优秀候选人"
)
_GENERIC_ANCHORS = frozenset({"python"})


class NarrativeV2_3ValidationError(ValueError):
    def __init__(self) -> None:
        super().__init__("Recruiter narrative V2.3 decision claim validation failed")


def invalid_narrative_v2_3_sections(
    narrative: RecruiterNarrativeV2_3, *, projection: NarrativeProjection,
) -> tuple[str, ...]:
    package = build_evidence_package_v2_2(projection)
    lookup = {fact.fact_id: fact for fact in package.all_facts}
    invalid = []
    for index, item in enumerate(narrative.decision_summary.rationale):
        label = f"decision_summary.rationale[{index}]"
        selected = [lookup[ident] for ident in item.supporting_facts if ident in lookup]
        try:
            if (any(_ABSTRACT.search(text) or _OTHER_CANDIDATE.search(text)
                    or _UNSUPPORTED_PERSONAL.search(text) or _unsupported_personal_work(text)
                    or _unsupported_production_claim(text)
                    for text in (item.statement, item.verification_focus))
                    or not any(f.kind == "requirement_alignment" for f in selected)
                    or not any(f.kind in {"project_practice", "technical_scope"} for f in selected)
                    or not any(f.kind in {"project_practice", "technical_scope", "interview_verification"}
                               and any(term.casefold() in item.verification_focus.casefold()
                                       for term in f.terms if len(term) >= 3)
                               for f in selected)):
                raise NarrativeV2_3ValidationError()
            _check_section((item.statement,), item.supporting_facts, facts=lookup,
                           job_role=projection.role_title, allow_unknown_scale=True)
            _check_section((item.verification_focus,), item.supporting_facts, facts=lookup,
                           cautious=True, job_role=projection.role_title, allow_unknown_scale=True)
        except (NarrativeV2ValidationError, NarrativeV2_3ValidationError):
            invalid.append(label)
    if narrative.decision_summary.decision == "prioritize_review":
        cited = {ident for item in narrative.decision_summary.rationale for ident in item.supporting_facts}
        if not (any(f.kind == "requirement_alignment"
                    and f.term.casefold() not in _GENERIC_ANCHORS and f.fact_id in cited
                    for f in package.requirement_alignment)
                and any(f.fact_id in cited for f in package.technical_scope)):
            invalid.append("decision_summary.decision")
    return tuple(invalid)


def validate_narrative_v2_3_projection(
    narrative: RecruiterNarrativeV2_3, *, projection: NarrativeProjection,
) -> None:
    if (narrative.candidate_id != projection.candidate_id
            or narrative.result_rank != projection.result_rank
            or invalid_narrative_v2_3_sections(narrative, projection=projection)):
        raise NarrativeV2_3ValidationError()


__all__ = ["NarrativeV2_3ValidationError", "invalid_narrative_v2_3_sections",
           "validate_narrative_v2_3_projection"]
