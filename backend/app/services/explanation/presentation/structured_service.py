"""Read-only canonical recruiter propositions from persisted grounded explanation."""

from __future__ import annotations

from pydantic import ValidationError

from app.exceptions import DomainError
from app.repositories.recruiter_narrative_repository import NarrativeSourceIntegrityError
from app.schemas.recruiter_proposition import StructuredRecruiterBriefV1
from app.services.explanation.contracts import candidate_output_fingerprint, evidence_bundle_fingerprint
from app.services.explanation.presentation.adapter import build_narrative_projection
from app.services.explanation.presentation.propositions_v1 import (
    build_recruiter_propositions_from_evidence_v1,
    validate_recruiter_propositions_v1,
)


class RecruiterPropositionSourceNotFoundError(DomainError):
    code = "recruiter_proposition_source_not_found"
    status_code = 404

    def __init__(self) -> None:
        super().__init__("Source explanation was not found")


class RecruiterPropositionSourceInvalidError(DomainError):
    code = "recruiter_proposition_source_invalid"
    status_code = 409

    def __init__(self) -> None:
        super().__init__("Source explanation cannot support recruiter propositions")


class RecruiterPropositionService:
    def __init__(self, repository) -> None:
        self.repository = repository

    async def get(self, match_explanation_id: int) -> StructuredRecruiterBriefV1:
        try:
            source = await self.repository.load_source(match_explanation_id)
        except NarrativeSourceIntegrityError:
            raise RecruiterPropositionSourceInvalidError() from None
        if source is None:
            raise RecruiterPropositionSourceNotFoundError()
        try:
            if (source.match_explanation_id != match_explanation_id
                    or source.candidate_output_fingerprint != candidate_output_fingerprint(source.output)
                    or source.evidence_bundle_fingerprint != evidence_bundle_fingerprint(source.bundle)):
                raise ValueError("source_fingerprint_or_identity_mismatch")
            projection = build_narrative_projection(bundle=source.bundle, source=source.output)
            propositions = build_recruiter_propositions_from_evidence_v1(
                bundle=source.bundle, source=source.output,
            )
            validate_recruiter_propositions_v1(propositions, projection=projection)
            grouped = {kind: tuple(item for item in propositions.propositions if item.kind == kind)
                       for kind in (
                           "human_review_recommendation", "technical_alignment",
                           "project_observation", "listed_skill_observation",
                           "material_unknown", "interview_target",
                       )}
            if len(grouped["human_review_recommendation"]) > 1:
                raise ValueError("multiple_review_actions")
            return StructuredRecruiterBriefV1(
                match_run_id=source.bundle.source.match_run_id,
                explanation_run_id=source.explanation_run_id,
                source_explanation_id=source.match_explanation_id,
                candidate_id=propositions.candidate_id,
                result_rank=propositions.result_rank,
                ranking_fingerprint=source.bundle.source.result_fingerprint,
                source_output_fingerprint=source.candidate_output_fingerprint,
                source_bundle_fingerprint=source.evidence_bundle_fingerprint,
                review_action=(grouped["human_review_recommendation"][0]
                               if grouped["human_review_recommendation"] else None),
                why_review=grouped["technical_alignment"],
                technical_signals=(grouped["project_observation"]
                                   + grouped["listed_skill_observation"]),
                unknowns=grouped["material_unknown"],
                verification_targets=grouped["interview_target"],
            )
        except (ValidationError, ValueError):
            raise RecruiterPropositionSourceInvalidError() from None


__all__ = [
    "RecruiterPropositionService", "RecruiterPropositionSourceInvalidError",
    "RecruiterPropositionSourceNotFoundError",
]
