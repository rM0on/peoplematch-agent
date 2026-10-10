from __future__ import annotations

from dataclasses import dataclass

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import undefer

from app.models.explanation_run import ExplanationRunModel, MatchExplanationModel
from app.models.recruiter_narrative import RecruiterNarrativeModel
from app.schemas.explanations import CandidateExplanationOutput, InternalEvidenceBundleV1
from app.services.explanation.contracts import (
    candidate_output_fingerprint,
    evidence_bundle_fingerprint,
    validate_explanation_output_references,
)


class NarrativeSourceIntegrityError(ValueError):
    def __init__(self) -> None:
        super().__init__("Historical explanation failed integrity validation")


@dataclass(frozen=True)
class NarrativeSource:
    explanation_run_id: str
    match_explanation_id: int
    bundle: InternalEvidenceBundleV1
    output: CandidateExplanationOutput
    candidate_output_fingerprint: str
    evidence_bundle_fingerprint: str


class RecruiterNarrativeRepository:
    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    async def load_source(self, match_explanation_id: int) -> NarrativeSource | None:
        async with self.session_factory() as session:
            row = (
                await session.execute(
                    select(MatchExplanationModel, ExplanationRunModel)
                    .join(
                        ExplanationRunModel,
                        MatchExplanationModel.explanation_run_id == ExplanationRunModel.explanation_run_id,
                    )
                    .where(MatchExplanationModel.id == match_explanation_id)
                    .options(undefer(ExplanationRunModel.evidence_bundle_json))
                )
            ).one_or_none()
            if row is None:
                return None
            explanation, run = row
            try:
                if run.status != "COMPLETED" or run.evidence_bundle_json is None:
                    raise ValueError("source run is not completed")
                bundle = InternalEvidenceBundleV1.model_validate(run.evidence_bundle_json)
                output = CandidateExplanationOutput.model_validate(explanation.validated_output_json)
                if (
                    run.evidence_bundle_fingerprint != evidence_bundle_fingerprint(bundle)
                    or explanation.candidate_output_fingerprint != candidate_output_fingerprint(output)
                    or output.candidate_id != explanation.candidate_id
                    or output.result_rank != explanation.result_rank
                    or bundle.source.match_run_id != run.match_run_id
                ):
                    raise ValueError("source provenance mismatch")
                validate_explanation_output_references(output, bundle)
            except (ValidationError, ValueError):
                raise NarrativeSourceIntegrityError() from None
            return NarrativeSource(
                explanation_run_id=run.explanation_run_id,
                match_explanation_id=explanation.id,
                bundle=bundle,
                output=output,
                candidate_output_fingerprint=explanation.candidate_output_fingerprint,
                evidence_bundle_fingerprint=run.evidence_bundle_fingerprint,
            )

    async def save(self, record: RecruiterNarrativeModel) -> None:
        async with self.session_factory() as session:
            async with session.begin():
                session.add(record)

    async def get(self, narrative_id: str) -> RecruiterNarrativeModel | None:
        async with self.session_factory() as session:
            return await session.get(RecruiterNarrativeModel, narrative_id)


__all__ = ["NarrativeSource", "NarrativeSourceIntegrityError", "RecruiterNarrativeRepository"]
