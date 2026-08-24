from __future__ import annotations

from app.services.explanation.evidence.contracts import MissingRequirementFact
from app.services.explanation.evidence.diagnostics import requirement_evidence_id


class MissingRequirementBuilder:
    """Translate persisted requirement diagnostics without inferring new claims."""

    def build(self, bundle) -> list[MissingRequirementFact]:
        requirements = list(bundle.job.requirements)
        output: list[MissingRequirementFact] = []
        for candidate in bundle.candidates:
            diagnostic_values = {
                fact.name: fact.value
                for fact in candidate.facts
                if fact.kind.value == "diagnostic"
            }
            matched = set(diagnostic_values.get("matched_must_have_requirement_ids", []))
            matched.update(diagnostic_values.get("matched_nice_to_have_requirement_ids", []))
            weak = set(diagnostic_values.get("weak_matched_must_have_requirement_ids", []))
            missing = set(diagnostic_values.get("missing_must_have_requirement_ids", []))
            supported = set(diagnostic_values.get("evidence_supported_requirement_ids", []))
            for requirement in requirements:
                requirement_id = requirement.requirement_id
                requirement_evidence = requirement_evidence_id(requirement_id)
                if requirement_evidence in matched:
                    status = "matched"
                elif requirement_evidence in weak:
                    status = "partial"
                elif requirement_evidence in missing:
                    status = "missing"
                else:
                    status = "not_assessed"
                if status == "missing":
                    evidence_status = "absent"
                elif requirement_evidence in supported:
                    evidence_status = "available"
                elif status in {"matched", "partial"}:
                    evidence_status = "claim_only"
                else:
                    evidence_status = "not_assessed"
                output.append(
                    MissingRequirementFact(
                        candidate_id=candidate.candidate_id,
                        result_rank=candidate.result_rank,
                        requirement_id=requirement_id,
                        priority=requirement.priority.value,
                        status=status,
                        evidence_status=evidence_status,
                        evidence_refs=[requirement_evidence_id(requirement_id)],
                    )
                )
        return output


__all__ = ["MissingRequirementBuilder"]
