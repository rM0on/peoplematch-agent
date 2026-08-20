from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Optional

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import selectinload, undefer

from app.exceptions import ExplanationRunConflictError, ExplanationRunNotFoundError
from app.models.explanation_run import ExplanationRunModel, MatchExplanationModel
from app.models.match_run import MatchResultModel
from app.schemas.explanations import (
    CandidateExplanationOutput,
    ExplanationRunRecord,
    ExplanationRunStatus,
    InternalEvidenceBundleV1,
    ProviderEvidenceV1,
)
from app.services.explanation.contracts import (
    EVIDENCE_BUNDLE_VERSION,
    EXPLANATION_OUTPUT_VERSION,
    PROVIDER_EVIDENCE_VERSION,
    candidate_output_fingerprint,
    evidence_bundle_fingerprint,
    explanation_result_fingerprint,
    project_provider_evidence,
    provider_evidence_fingerprint,
    validate_explanation_output_references,
)


class ExplanationRunRepository:
    """Own durable transactions for the independent explanation lifecycle."""

    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    @staticmethod
    def _payload_options():
        return (
            undefer(ExplanationRunModel.evidence_bundle_json),
            undefer(ExplanationRunModel.provider_evidence_json),
        )

    @staticmethod
    def _record_values(run: ExplanationRunModel) -> dict:
        return {
            name: getattr(run, name, None)
            for name in ExplanationRunRecord.model_fields
        }

    @classmethod
    def _validate_state(cls, run: ExplanationRunModel) -> None:
        try:
            ExplanationRunRecord.model_validate(cls._record_values(run))
        except ValidationError as error:
            raise ExplanationRunConflictError(
                "Explanation run state violates the Phase 9 contract"
            ) from error

    @staticmethod
    async def _running(session, explanation_run_id: str) -> ExplanationRunModel:
        run = await session.scalar(
            select(ExplanationRunModel)
            .where(ExplanationRunModel.explanation_run_id == explanation_run_id)
            .options(*ExplanationRunRepository._payload_options())
            .with_for_update()
        )
        if run is None:
            raise ExplanationRunNotFoundError(
                f"Explanation run {explanation_run_id} was not found"
            )
        if run.status != ExplanationRunStatus.RUNNING.value:
            raise ExplanationRunConflictError(
                "Terminal explanation runs are immutable"
            )
        return run

    async def create_running(self, run: ExplanationRunModel) -> None:
        if run.status != ExplanationRunStatus.RUNNING.value:
            raise ExplanationRunConflictError(
                "New explanation runs must start in RUNNING"
            )
        self._validate_state(run)
        async with self.session_factory() as session:
            async with session.begin():
                session.add(run)

    async def store_evidence(
        self,
        explanation_run_id: str,
        *,
        evidence_bundle: InternalEvidenceBundleV1,
        provider_evidence: ProviderEvidenceV1,
    ) -> None:
        expected_provider_evidence = project_provider_evidence(evidence_bundle)
        if provider_evidence != expected_provider_evidence:
            raise ExplanationRunConflictError(
                "Provider evidence is not the grounded projection of internal evidence"
            )

        async with self.session_factory() as session:
            async with session.begin():
                run = await self._running(session, explanation_run_id)
                if evidence_bundle.source.match_run_id != run.match_run_id:
                    raise ExplanationRunConflictError(
                        "Evidence bundle belongs to another MatchRun"
                    )
                run.evidence_bundle_version = EVIDENCE_BUNDLE_VERSION
                run.evidence_bundle_fingerprint = evidence_bundle_fingerprint(
                    evidence_bundle
                )
                run.evidence_bundle_json = evidence_bundle.model_dump(
                    mode="json", exclude_none=False
                )
                run.provider_evidence_version = PROVIDER_EVIDENCE_VERSION
                run.provider_evidence_fingerprint = provider_evidence_fingerprint(
                    provider_evidence
                )
                run.provider_evidence_json = provider_evidence.model_dump(
                    mode="json", exclude_none=False
                )
                self._validate_state(run)

    @staticmethod
    def _validated_outputs(
        explanations: Sequence[MatchExplanationModel],
    ) -> list[CandidateExplanationOutput]:
        if not explanations:
            raise ExplanationRunConflictError(
                "Completed explanation run requires Candidate outputs"
            )
        outputs: list[CandidateExplanationOutput] = []
        for explanation in explanations:
            try:
                output = CandidateExplanationOutput.model_validate(
                    explanation.validated_output_json
                )
            except ValidationError as error:
                raise ExplanationRunConflictError(
                    "Candidate explanation violates explanation_output_v1"
                ) from error
            if (
                explanation.output_schema_version != EXPLANATION_OUTPUT_VERSION
                or output.output_schema_version != EXPLANATION_OUTPUT_VERSION
                or explanation.candidate_id != output.candidate_id
                or explanation.result_rank != output.result_rank
                or explanation.candidate_output_fingerprint
                != candidate_output_fingerprint(output)
            ):
                raise ExplanationRunConflictError(
                    "Candidate explanation identity or fingerprint mismatch"
                )
            outputs.append(output)
        ranks = sorted(item.result_rank for item in outputs)
        if ranks != list(range(1, len(outputs) + 1)):
            raise ExplanationRunConflictError(
                "Candidate explanation ranks must be contiguous from one"
            )
        return outputs

    async def finalize_completed(
        self,
        explanation_run_id: str,
        explanations: Sequence[MatchExplanationModel],
        *,
        completed_at: datetime,
        provider_kind: str,
        provider_name: str,
        configured_model: str,
        observed_model: Optional[str],
        provider_configuration_fingerprint: str,
        prompt_version: str,
        prompt_fingerprint: str,
        attempt_count: int,
        repaired: bool,
    ) -> None:
        outputs = self._validated_outputs(explanations)
        result_fingerprint = explanation_result_fingerprint(outputs)
        async with self.session_factory() as session:
            async with session.begin():
                run = await self._running(session, explanation_run_id)
                if run.evidence_bundle_json is None:
                    raise ExplanationRunConflictError(
                        "Completed explanation run requires persisted Evidence Bundle"
                    )
                try:
                    persisted_bundle = InternalEvidenceBundleV1.model_validate(
                        run.evidence_bundle_json
                    )
                    for output in outputs:
                        validate_explanation_output_references(output, persisted_bundle)
                except (ValidationError, ValueError) as error:
                    raise ExplanationRunConflictError(
                        "Candidate explanation references are not grounded in Evidence Bundle"
                    ) from error
                result_ids = [item.match_result_id for item in explanations]
                source_results = (
                    await session.scalars(
                        select(MatchResultModel).where(MatchResultModel.id.in_(result_ids))
                    )
                ).all()
                by_id = {item.id: item for item in source_results}
                for explanation in explanations:
                    source = by_id.get(explanation.match_result_id)
                    if (
                        source is None
                        or source.run_id != run.match_run_id
                        or source.candidate_id != explanation.candidate_id
                        or source.result_rank != explanation.result_rank
                        or explanation.explanation_run_id != explanation_run_id
                    ):
                        raise ExplanationRunConflictError(
                            "Candidate explanation does not belong to the source MatchRun result"
                        )

                run.status = ExplanationRunStatus.COMPLETED.value
                run.effective_top_k = len(explanations)
                run.explanation_count = len(explanations)
                run.output_schema_version = EXPLANATION_OUTPUT_VERSION
                run.provider_kind = provider_kind
                run.provider_name = provider_name
                run.configured_model = configured_model
                run.observed_model = observed_model
                run.provider_configuration_fingerprint = (
                    provider_configuration_fingerprint
                )
                run.prompt_version = prompt_version
                run.prompt_fingerprint = prompt_fingerprint
                run.attempt_count = attempt_count
                run.repaired = repaired
                run.result_fingerprint = result_fingerprint
                run.completed_at = completed_at
                run.error_code = None
                run.error_detail_safe = None
                self._validate_state(run)
                session.add_all(explanations)

    async def finalize_failed(
        self,
        explanation_run_id: str,
        *,
        completed_at: datetime,
        error_code: str,
        error_detail_safe: str,
    ) -> None:
        async with self.session_factory() as session:
            async with session.begin():
                run = await self._running(session, explanation_run_id)
                run.status = ExplanationRunStatus.FAILED.value
                run.completed_at = completed_at
                run.error_code = error_code
                run.error_detail_safe = error_detail_safe
                self._validate_state(run)

    async def get_by_explanation_run_id(
        self,
        explanation_run_id: str,
        *,
        include_payloads: bool = False,
        include_explanations: bool = False,
    ) -> Optional[ExplanationRunModel]:
        options = []
        if include_payloads:
            options.extend(self._payload_options())
        if include_explanations:
            options.append(selectinload(ExplanationRunModel.explanations))
        async with self.session_factory() as session:
            statement = select(ExplanationRunModel).where(
                ExplanationRunModel.explanation_run_id == explanation_run_id
            )
            if options:
                statement = statement.options(*options)
            return (await session.scalars(statement)).unique().one_or_none()
