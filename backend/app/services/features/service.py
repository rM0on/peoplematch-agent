from __future__ import annotations

from pydantic import ValidationError

from app.exceptions import FeatureContractViolationError, InvalidProfileStateError
from app.schemas.features import FeatureResponseData, FeatureResult
from app.schemas.retrieval import RetrievalRequest, RetrievalResponseData
from app.services.features.contract import FEATURE_FINGERPRINT, FEATURE_VERSION
from app.services.features.extractor import extract_pair_features


class FeatureEngineeringService:
    def __init__(
        self,
        *,
        retrieval_service,
        candidate_repository,
        job_repository,
    ) -> None:
        self.retrieval_service = retrieval_service
        self.candidate_repository = candidate_repository
        self.job_repository = job_repository

    async def features_for_job_candidates(
        self, job_id: str, request: RetrievalRequest
    ) -> FeatureResponseData:
        try:
            retrieval = await self.retrieval_service.retrieve_candidates(job_id, request)
        except ValidationError as error:
            raise InvalidProfileStateError(
                "A canonical profile is invalid for feature extraction"
            ) from error
        try:
            job = await self.job_repository.get_record_by_id(job_id)
            candidates = {
                item.candidate_id: item
                for item in await self.candidate_repository.list_all_records()
            }
        except ValidationError as error:
            raise InvalidProfileStateError(
                "A canonical profile is invalid for feature extraction"
            ) from error
        if job is None:
            raise FeatureContractViolationError(
                f"Job {job_id} disappeared during feature extraction"
            )
        try:
            return self._enrich_candidates(retrieval, candidates, job)
        except ValidationError as error:
            raise FeatureContractViolationError(
                "A generated feature violates the registered contract"
            ) from error

    async def features_for_candidate_jobs(
        self, candidate_id: str, request: RetrievalRequest
    ) -> FeatureResponseData:
        try:
            retrieval = await self.retrieval_service.retrieve_jobs(candidate_id, request)
        except ValidationError as error:
            raise InvalidProfileStateError(
                "A canonical profile is invalid for feature extraction"
            ) from error
        try:
            candidate = await self.candidate_repository.get_record_by_id(candidate_id)
            jobs = {
                item.job_id: item for item in await self.job_repository.list_all_records()
            }
        except ValidationError as error:
            raise InvalidProfileStateError(
                "A canonical profile is invalid for feature extraction"
            ) from error
        if candidate is None:
            raise FeatureContractViolationError(
                f"Candidate {candidate_id} disappeared during feature extraction"
            )
        try:
            return self._enrich_jobs(retrieval, candidate, jobs)
        except ValidationError as error:
            raise FeatureContractViolationError(
                "A generated feature violates the registered contract"
            ) from error

    @staticmethod
    def _response(
        retrieval: RetrievalResponseData, results: list[FeatureResult]
    ) -> FeatureResponseData:
        return FeatureResponseData(
            feature_version=FEATURE_VERSION,
            feature_fingerprint=FEATURE_FINGERPRINT,
            results=results,
            retrieval_diagnostics=retrieval.diagnostics,
        )

    def _enrich_candidates(self, retrieval, candidates, job) -> FeatureResponseData:
        results = []
        for retrieval_result in retrieval.results:
            candidate = candidates.get(retrieval_result.entity_id)
            if candidate is None:
                raise FeatureContractViolationError(
                    "Retrieved candidate is absent from the canonical profile batch"
                )
            extracted = extract_pair_features(candidate, job, retrieval_result)
            results.append(
                FeatureResult(
                    entity_id=retrieval_result.entity_id,
                    retrieval=retrieval_result,
                    feature_vector=extracted.vector,
                    feature_diagnostics=extracted.diagnostics,
                )
            )
        return self._response(retrieval, results)

    def _enrich_jobs(self, retrieval, candidate, jobs) -> FeatureResponseData:
        results = []
        for retrieval_result in retrieval.results:
            job = jobs.get(retrieval_result.entity_id)
            if job is None:
                raise FeatureContractViolationError(
                    "Retrieved job is absent from the canonical profile batch"
                )
            extracted = extract_pair_features(candidate, job, retrieval_result)
            results.append(
                FeatureResult(
                    entity_id=retrieval_result.entity_id,
                    retrieval=retrieval_result,
                    feature_vector=extracted.vector,
                    feature_diagnostics=extracted.diagnostics,
                )
            )
        return self._response(retrieval, results)
