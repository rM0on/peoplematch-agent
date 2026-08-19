from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Callable, Optional
from uuid import uuid4

from app.exceptions import (
    DomainError,
    MatchRunExecutionError,
    MatchRunNotFoundError,
    ProfileNotFoundError,
    RankingContractMismatchError,
)
from app.models.match_run import MatchResultModel, MatchRunModel, RunStepModel
from app.schemas.cross_encoder import CrossEncoderRerankingRequest
from app.schemas.match_runs import (
    CrossEncoderMatchRunRequest,
    LtrMatchRunRequest,
    MatchRunRequest,
    RankingVariant,
)
from app.schemas.ranking import RankingRequest
from app.services.cross_encoder.contract import (
    PAIR_ORDER,
    RERANKER_VERSION,
    SCORE_DIRECTION,
    SCORE_TYPE,
    TEXT_CONTRACT_FINGERPRINT,
    TEXT_SCHEMA_VERSION,
)
from app.services.features.contract import FEATURE_FINGERPRINT, FEATURE_VERSION
from app.services.match_runs.contracts import (
    CANDIDATE_INPUT_CONTRACT_VERSION,
    CE_MODEL_ID,
    CE_MODEL_REVISION,
    CE_SNAPSHOT_FINGERPRINT,
    DIAGNOSTICS_CONTRACT_VERSION,
    RANKER_MODEL_SHA256,
    RANKING_INPUT_CONTRACT_VERSION,
    RETRIEVAL_CONFIGURATION_FINGERPRINT,
    STEP_REFS_CONTRACT_VERSION,
    WORKFLOW_FINGERPRINT,
    WORKFLOW_VERSION,
    build_candidate_input_snapshot,
    build_job_input_snapshot,
    canonical_fingerprint,
    selected_feature_diagnostics,
    workflow_steps,
)
from app.services.ranking.contract import RANKER_VERSION
from app.services.retrieval.documents import RETRIEVAL_DOCUMENT_VERSION


class TracedRankingServiceProxy:
    def __init__(
        self,
        service: "MatchRunService",
        run_id: str,
        ranking_service_factory,
        *,
        ce: bool,
        on_phase6_success=None,
    ):
        self.service = service
        self.run_id = run_id
        self.ranking_service_factory = ranking_service_factory
        self.ranking_service = None
        self.ce = ce
        self.last_response = None
        self.phase7_step = None
        self.phase7_tick = None
        self.on_phase6_success = on_phase6_success
        self.observed_provenance = None

    async def rank_job_candidates(self, job_id: str, request: RankingRequest):
        response = await self.service._execute_step(
            self.run_id,
            "phase6_ltr_rank",
            {"job_id": job_id, "candidate_pool_k": request.candidate_pool_k, "top_k": request.top_k},
            lambda: self._rank(job_id, request),
            lambda value: {
                "result_count": len(value.results),
                "ranker_version": value.ranker_version,
                "feature_version": value.feature_version,
            },
            success_hook=self._record_phase6_success,
        )
        self.last_response = response
        if self.ce:
            self.phase7_step, self.phase7_tick = await self.service._start_step(
                self.run_id,
                "phase7_cross_encoder_rerank",
                {"ltr_result_count": len(response.results)},
            )
        return response

    async def _record_phase6_success(self, response):
        if self.on_phase6_success is not None:
            self.observed_provenance = await self.on_phase6_success(response, self)

    async def _rank(self, job_id: str, request: RankingRequest):
        if self.ranking_service is None:
            self.ranking_service = self.ranking_service_factory()
        return await self.ranking_service.rank_job_candidates(job_id, request)


class MatchRunService:
    def __init__(
        self,
        *,
        lifecycle_repository,
        job_repository,
        candidate_repository,
        ranking_service_factory: Callable[[], Any],
        cross_encoder_service_factory: Callable[[Any], Any],
        execution_session_factory=None,
        execution_graph_factory=None,
        utc_now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        monotonic: Callable[[], float] = perf_counter,
        run_id_factory: Callable[[], str] = lambda: str(uuid4()),
    ) -> None:
        self.lifecycle_repository = lifecycle_repository
        self.job_repository = job_repository
        self.candidate_repository = candidate_repository
        self.ranking_service_factory = ranking_service_factory
        self.cross_encoder_service_factory = cross_encoder_service_factory
        self.execution_session_factory = execution_session_factory
        self.execution_graph_factory = execution_graph_factory
        self.utc_now = utc_now
        self.monotonic = monotonic
        self.run_id_factory = run_id_factory
        self._step_sequences: dict[str, dict[str, int]] = {}

    @staticmethod
    def _safe_failure(error: Exception) -> tuple[str, str, int]:
        if isinstance(error, MatchRunExecutionError):
            return (
                str(error.details["failure_code"]),
                "A match-run stage failed",
                error.status_code,
            )
        if isinstance(error, DomainError):
            return error.code, str(error)[:500], error.status_code
        return "match_run_execution_failed", "A match-run stage failed", 500

    def _sequence(self, run_id: str, step_name: str) -> int:
        return self._step_sequences[run_id][step_name]

    async def _start_step(self, run_id: str, step_name: str, input_refs: dict[str, Any]):
        started_at = self.utc_now()
        started_tick = self.monotonic()
        step = RunStepModel(
            run_id=run_id,
            sequence=self._sequence(run_id, step_name),
            step_name=step_name,
            status="RUNNING",
            started_at=started_at,
            input_refs=input_refs,
            output_refs=None,
            contract_version=STEP_REFS_CONTRACT_VERSION,
        )
        try:
            await self.lifecycle_repository.start_step(step)
        except Exception as error:
            await self._fail_step(run_id, step, started_tick, error)
            raise self._execution_error(run_id, error) from error
        return step, started_tick

    def _execution_error(self, run_id: str, error: Exception) -> MatchRunExecutionError:
        code, _, status = self._safe_failure(error)
        return MatchRunExecutionError(run_id, code, status)

    async def _fail_step(
        self, run_id: str, step: RunStepModel, started_tick: float, error: Exception
    ) -> None:
        code, detail, _ = self._safe_failure(error)
        finished_at = self.utc_now()
        duration_ms = max(0.0, (self.monotonic() - started_tick) * 1000.0)
        await self.lifecycle_repository.finalize_failed(
            run_id,
            sequence=step.sequence,
            step=step,
            finished_at=finished_at,
            duration_ms=duration_ms,
            error_code=code,
            error_detail_safe=detail,
        )

    async def _execute_step(
        self,
        run_id: str,
        step_name: str,
        input_refs: dict[str, Any],
        operation,
        output_refs,
        success_hook=None,
    ):
        step, started_tick = await self._start_step(run_id, step_name, input_refs)
        try:
            value = await operation()
            if success_hook is not None:
                await success_hook(value)
        except MatchRunExecutionError:
            raise
        except Exception as error:
            await self._fail_step(run_id, step, started_tick, error)
            raise self._execution_error(run_id, error) from error
        finished_at = self.utc_now()
        try:
            await self.lifecycle_repository.complete_step(
                run_id,
                step.sequence,
                finished_at=finished_at,
                duration_ms=max(0.0, (self.monotonic() - started_tick) * 1000.0),
                output_refs=output_refs(value),
            )
        except Exception as error:
            await self._fail_step(run_id, step, started_tick, error)
            raise self._execution_error(run_id, error) from error
        return value

    def _request_parameters(self, payload: MatchRunRequest) -> dict[str, Any]:
        return payload.model_dump(
            mode="json", exclude={"job_id", "ranking_variant"}, exclude_none=True
        )

    def _run_input_fingerprint(
        self,
        payload: MatchRunRequest,
        job_snapshot: dict[str, Any],
        observed_provenance: dict[str, Any],
    ) -> str:
        return canonical_fingerprint(
            {
                "job_snapshot": job_snapshot,
                "ranking_variant": payload.ranking_variant,
                "request_parameters": self._request_parameters(payload),
                "workflow_version": WORKFLOW_VERSION,
                "workflow_fingerprint": WORKFLOW_FINGERPRINT,
                "provenance": {
                    "retrieval_document_version": observed_provenance[
                        "retrieval_document_version"
                    ],
                    "retrieval_configuration_fingerprint": observed_provenance[
                        "retrieval_configuration_fingerprint"
                    ],
                    "feature_version": observed_provenance["feature_version"],
                    "feature_fingerprint": observed_provenance["feature_fingerprint"],
                    "ranker_version": observed_provenance["ranker_version"],
                    "ranker_model_sha256": observed_provenance["ranker_model_sha256"],
                },
            }
        )

    async def _resolve_inputs(
        self, run_id: str, payload: MatchRunRequest, *, job_repository=None
    ):
        repository = job_repository or self.job_repository
        job = await repository.get_record_by_id(payload.job_id)
        if job is None:
            raise ProfileNotFoundError(f"Job {payload.job_id} was not found")
        snapshot = build_job_input_snapshot(job)
        await self.lifecycle_repository.resolve_job(
            run_id=run_id,
            job_id=job.job_id,
            ranking_input_snapshot=snapshot,
            ranking_input_fingerprint=None,
        )
        return job, snapshot

    async def _build_results(
        self, run_id: str, ltr_response, ce_response=None, *, candidate_repository=None
    ):
        repository = candidate_repository or self.candidate_repository
        by_id = {item.entity_id: item for item in ltr_response.results}
        final = ce_response.results if ce_response is not None else ltr_response.results
        results = []
        fingerprint_rows = []
        for rank, final_item in enumerate(final, start=1):
            ltr_item = by_id[final_item.entity_id]
            candidate = await repository.get_record_by_id(final_item.entity_id)
            if candidate is None:
                raise ProfileNotFoundError(
                    f"Candidate {final_item.entity_id} was not found"
                )
            snapshot = build_candidate_input_snapshot(candidate)
            snapshot_fingerprint = canonical_fingerprint(snapshot)
            retrieval = ltr_item.retrieval
            features = ltr_item.feature_vector.model_dump(mode="python")
            diagnostics = selected_feature_diagnostics(ltr_item.feature_diagnostics)
            values = {
                "run_id": run_id,
                "candidate_id": final_item.entity_id,
                "result_rank": rank,
                "candidate_input_contract_version": CANDIDATE_INPUT_CONTRACT_VERSION,
                "candidate_input_fingerprint": snapshot_fingerprint,
                "candidate_input_snapshot": snapshot,
                "retrieval_rank": retrieval.rank,
                "matched_channels": list(retrieval.matched_channels),
                "dense_rank": retrieval.dense_rank,
                "dense_score": retrieval.dense_score,
                "sparse_rank": retrieval.sparse_rank,
                "sparse_score": retrieval.sparse_score,
                "fusion_score": retrieval.fusion_score,
                **features,
                "feature_diagnostics_contract_version": DIAGNOSTICS_CONTRACT_VERSION,
                "feature_diagnostics": diagnostics,
                "ltr_rank": ltr_item.ltr_rank,
                "ltr_score_raw": ltr_item.ltr_score_raw,
                "cross_encoder_rank": getattr(final_item, "cross_encoder_rank", None),
                "cross_encoder_score_raw": getattr(
                    final_item, "cross_encoder_score_raw", None
                ),
            }
            results.append(MatchResultModel(**values))
            fingerprint_rows.append(
                {
                    key: value
                    for key, value in values.items()
                    if key not in {"run_id", "candidate_input_snapshot"}
                }
            )
        return results, fingerprint_rows

    @staticmethod
    def _retrieval_provenance(
        response, *, configuration_fingerprint: Optional[str] = None
    ) -> dict[str, Any]:
        diagnostics = response.retrieval_diagnostics
        return {
            "document_version": diagnostics.document_version,
            "configuration_fingerprint": configuration_fingerprint,
            "index_freshness": diagnostics.index_freshness,
            "embedding_provider": diagnostics.embedding_provider,
            "embedding_model": diagnostics.embedding_model,
            "strategy": diagnostics.strategy.value,
            "rrf_k": diagnostics.rrf_k,
            "corpus_size": diagnostics.corpus_size,
            "eligible_count": diagnostics.eligible_count,
            "filters_applied": diagnostics.filters_applied,
        }

    @staticmethod
    def _phase6_provenance(response, ranking_proxy) -> dict[str, Any]:
        diagnostics = response.retrieval_diagnostics
        ranking_model = getattr(ranking_proxy.ranking_service, "ranking_model", None)
        metadata = getattr(ranking_model, "metadata", {}) or {}
        configuration_fingerprint = getattr(
            diagnostics, "retrieval_configuration_fingerprint", None
        ) or metadata.get("retrieval_configuration_fingerprint")
        observed = {
            "retrieval_document_version": diagnostics.document_version,
            "retrieval_configuration_fingerprint": configuration_fingerprint,
            "feature_version": response.feature_version,
            "feature_fingerprint": response.feature_fingerprint,
            "ranker_version": response.ranker_version,
            "ranker_model_sha256": response.model_sha256,
        }
        expected = {
            "retrieval_document_version": RETRIEVAL_DOCUMENT_VERSION,
            "retrieval_configuration_fingerprint": RETRIEVAL_CONFIGURATION_FINGERPRINT,
            "feature_version": FEATURE_VERSION,
            "feature_fingerprint": FEATURE_FINGERPRINT,
            "ranker_version": RANKER_VERSION,
            "ranker_model_sha256": RANKER_MODEL_SHA256,
        }
        if observed != expected:
            mismatches = [
                key for key, value in expected.items() if observed.get(key) != value
            ]
            raise RankingContractMismatchError(
                "Observed ranking provenance mismatch: " + ", ".join(mismatches)
            )
        return observed

    @staticmethod
    def _ce_provenance(response) -> dict[str, Any]:
        return {
            "reranker_version": response.reranker_version,
            "model_id": response.model_id,
            "model_revision": response.model_revision,
            "snapshot_fingerprint": response.snapshot_fingerprint,
            "text_schema_version": response.text_schema_version,
            "text_contract_fingerprint": response.text_contract_fingerprint,
            "pair_order": response.pair_order,
            "score_type": SCORE_TYPE,
            "score_direction": SCORE_DIRECTION,
            "calibration": False,
        }

    async def execute(self, payload: MatchRunRequest, *, request_id: str):
        run_id = self.run_id_factory()
        self._step_sequences[run_id] = {
            name: index for index, name in enumerate(workflow_steps(payload.ranking_variant), 1)
        }
        run = MatchRunModel(
            run_id=run_id,
            requested_job_id=payload.job_id,
            job_id=None,
            request_id=request_id,
            ranking_variant=payload.ranking_variant.value,
            status="RUNNING",
            started_at=self.utc_now(),
            request_parameters=self._request_parameters(payload),
            workflow_version=WORKFLOW_VERSION,
            workflow_fingerprint=WORKFLOW_FINGERPRINT,
            ranking_input_contract_version=RANKING_INPUT_CONTRACT_VERSION,
            ranking_input_fingerprint=None,
            ranking_input_snapshot=None,
            retrieval_document_version=None,
            retrieval_configuration_fingerprint=None,
            feature_version=None,
            feature_fingerprint=None,
            ranker_version=None,
            ranker_model_sha256=None,
            ce_provenance=None,
            result_count=0,
        )
        try:
            await self.lifecycle_repository.create_running(run)
        except Exception:
            self._step_sequences.pop(run_id, None)
            raise
        try:
            if self.execution_session_factory is None:
                return await self._execute_pipeline(
                    payload,
                    run_id,
                    job_repository=self.job_repository,
                    candidate_repository=self.candidate_repository,
                    ranking_service_factory=self.ranking_service_factory,
                    cross_encoder_service_factory=self.cross_encoder_service_factory,
                )
            async with self.execution_session_factory() as execution_session:
                async with execution_session.begin():
                    graph = self.execution_graph_factory(execution_session)
                    return await self._execute_pipeline(
                        payload,
                        run_id,
                        job_repository=graph["job_repository"],
                        candidate_repository=graph["candidate_repository"],
                        ranking_service_factory=graph["ranking_service_factory"],
                        cross_encoder_service_factory=graph[
                            "cross_encoder_service_factory"
                        ],
                    )
        finally:
            self._step_sequences.pop(run_id, None)

    async def _execute_pipeline(
        self,
        payload: MatchRunRequest,
        run_id: str,
        *,
        job_repository,
        candidate_repository,
        ranking_service_factory,
        cross_encoder_service_factory,
    ):
        resolved_snapshot = None
        _resolved_job, resolved_snapshot = await self._execute_step(
            run_id,
            "resolve_inputs",
            {"requested_job_id": payload.job_id},
            lambda: self._resolve_inputs(
                run_id, payload, job_repository=job_repository
            ),
            lambda value: {
                "job_id": value[0].job_id,
                "ranking_input_fingerprint": None,
            },
        )

        ranking_proxy = TracedRankingServiceProxy(
            self,
            run_id,
            ranking_service_factory,
            ce=payload.ranking_variant == RankingVariant.CROSS_ENCODER_EXPERIMENT,
        )
        async def record_phase6_success(response, proxy):
            observed = self._phase6_provenance(response, proxy)
            await self.lifecycle_repository.resolve_job(
                run_id=run_id,
                ranking_input_fingerprint=self._run_input_fingerprint(
                    payload, resolved_snapshot, observed
                ),
                retrieval_document_version=observed["retrieval_document_version"],
                retrieval_configuration_fingerprint=observed[
                    "retrieval_configuration_fingerprint"
                ],
                feature_version=observed["feature_version"],
                feature_fingerprint=observed["feature_fingerprint"],
                ranker_version=observed["ranker_version"],
                ranker_model_sha256=observed["ranker_model_sha256"],
            )
            return observed

        ranking_proxy.on_phase6_success = record_phase6_success
        ce_response = None
        if isinstance(payload, LtrMatchRunRequest):
            ltr_response = await ranking_proxy.rank_job_candidates(
                payload.job_id,
                RankingRequest(
                    candidate_pool_k=payload.candidate_pool_k,
                    top_k=payload.top_k,
                    filters=payload.filters,
                ),
            )
        else:
            try:
                ce_service = cross_encoder_service_factory(ranking_proxy)
                ce_response = await ce_service.rerank_job_candidates(
                    payload.job_id,
                    CrossEncoderRerankingRequest(
                        retrieval_pool_k=payload.retrieval_pool_k,
                        cross_encoder_pool_k=payload.cross_encoder_pool_k,
                        top_k=payload.top_k,
                        filters=payload.filters,
                    ),
                )
            except MatchRunExecutionError:
                raise
            except Exception as error:
                if ranking_proxy.phase7_step is None:
                    await self.lifecycle_repository.finalize_failed(
                        run_id,
                        sequence=None,
                        step=None,
                        finished_at=self.utc_now(),
                        duration_ms=0.0,
                        error_code=self._safe_failure(error)[0],
                        error_detail_safe=self._safe_failure(error)[1],
                    )
                    raise self._execution_error(run_id, error) from error
                else:
                    step, tick = ranking_proxy.phase7_step, ranking_proxy.phase7_tick
                await self._fail_step(run_id, step, tick, error)
                raise self._execution_error(run_id, error) from error
            if ranking_proxy.phase7_step is None:
                error = RuntimeError("Cross-Encoder did not execute Phase 6")
                await self.lifecycle_repository.finalize_failed(
                    run_id,
                    sequence=None,
                    step=None,
                    finished_at=self.utc_now(),
                    duration_ms=0.0,
                    error_code=self._safe_failure(error)[0],
                    error_detail_safe=self._safe_failure(error)[1],
                )
                raise self._execution_error(run_id, error) from error
            try:
                await self.lifecycle_repository.complete_step(
                    run_id,
                    ranking_proxy.phase7_step.sequence,
                    finished_at=self.utc_now(),
                    duration_ms=max(
                        0.0, (self.monotonic() - ranking_proxy.phase7_tick) * 1000.0
                    ),
                    output_refs={
                        "result_count": len(ce_response.results),
                        "reranker_version": ce_response.reranker_version,
                        "text_schema_version": ce_response.text_schema_version,
                    },
                )
            except Exception as error:
                await self._fail_step(
                    run_id, ranking_proxy.phase7_step, ranking_proxy.phase7_tick, error
                )
                raise self._execution_error(run_id, error) from error
            ltr_response = ranking_proxy.last_response

        persist_step, persist_tick = await self._start_step(
            run_id, "persist_results", {"ranking_result_count": len((ce_response or ltr_response).results)}
        )
        try:
            results, fingerprint_rows = await self._build_results(
                run_id,
                ltr_response,
                ce_response,
                candidate_repository=candidate_repository,
            )
            ce_provenance = self._ce_provenance(ce_response) if ce_response else None
            observed = ranking_proxy.observed_provenance
            retrieval_provenance = self._retrieval_provenance(
                ltr_response,
                configuration_fingerprint=observed[
                    "retrieval_configuration_fingerprint"
                ],
            )
            result_fingerprint = canonical_fingerprint(
                {
                    "ranking_variant": payload.ranking_variant,
                    "provenance": {
                        "workflow_fingerprint": WORKFLOW_FINGERPRINT,
                        "feature_fingerprint": observed["feature_fingerprint"],
                        "ranker_model_sha256": observed["ranker_model_sha256"],
                        "ce": ce_provenance,
                        "retrieval": retrieval_provenance,
                    },
                    "results": fingerprint_rows,
                }
            )
            await self.lifecycle_repository.finalize_results_atomically(
                run_id,
                results,
                finished_at=self.utc_now(),
                duration_ms=max(0.0, (self.monotonic() - persist_tick) * 1000.0),
                output_refs={"result_count": len(results), "result_fingerprint": result_fingerprint},
                result_fingerprint=result_fingerprint,
                ce_provenance=ce_provenance,
                retrieval_provenance=retrieval_provenance,
            )
        except MatchRunExecutionError:
            raise
        except Exception as error:
            await self._fail_step(run_id, persist_step, persist_tick, error)
            raise self._execution_error(run_id, error) from error
        return await self.lifecycle_repository.get_by_run_id(run_id)

    async def get(self, run_id: str):
        run = await self.lifecycle_repository.get_by_run_id(run_id)
        if run is None:
            raise MatchRunNotFoundError(f"Match run {run_id} was not found")
        return run

    async def list(self, **filters):
        return await self.lifecycle_repository.list_runs(**filters)
