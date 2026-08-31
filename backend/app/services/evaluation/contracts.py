from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


PHASE4_TEST_EXPOSURE_CAVEAT = "post_exposure_fixed_synthetic_sandbox_evaluation"


class EvaluationRunStatus(str, Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    INVALID = "INVALID"


class TestAccessReason(str, Enum):
    FINAL = "final"
    REPRODUCTION = "reproduction"


class TestExecutionAudit(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    allow_test: Literal[True]
    access_reason: TestAccessReason
    protocol_git_commit: str = Field(pattern=r"^[a-f0-9]{40}$")
    freeze_gate_attested: Literal[True]
    phase4_test_exposure_acknowledged: Literal[True]
    phase4_test_exposure_caveat: Literal[PHASE4_TEST_EXPOSURE_CAVEAT]
    prior_final_run_id: Optional[str] = None
    prior_final_input_fingerprint: Optional[str] = Field(default=None, pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_reason_contract(self) -> "TestExecutionAudit":
        has_prior_reference = bool(self.prior_final_run_id and self.prior_final_input_fingerprint)
        if self.access_reason == TestAccessReason.REPRODUCTION and not has_prior_reference:
            raise ValueError("reproduction requires prior final run reference and input fingerprint")
        if self.access_reason == TestAccessReason.FINAL and (
            self.prior_final_run_id is not None or self.prior_final_input_fingerprint is not None
        ):
            raise ValueError("final Test access cannot carry reproduction provenance")
        return self


class EvaluationManifestV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["phase11_evaluation_manifest_v1"]
    evaluation_run_id: str = Field(min_length=1, max_length=160)
    protocol_version: Literal["phase11_eval_protocol_v1"]
    metric_semantics_version: Literal["phase11_metric_semantics_v1"]
    dataset_version: Literal["1.0.0"]
    dataset_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    split: Literal["train", "dev", "test"]
    query_ids: List[str] = Field(min_length=1)
    source_commit_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    source_tree_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    status: EvaluationRunStatus
    recorded_at: str
    started_at: str
    ended_at: Optional[str] = None
    manifest_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    strategy_config: Optional[Dict[str, Any]] = None
    candidate_pool_config: Optional[Dict[str, Any]] = None
    model_artifacts: Optional[Dict[str, str]] = None
    feature_fingerprint: Optional[str] = None
    retrieval_document_version: Optional[str] = None
    retrieval_config_fingerprint: Optional[str] = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    retrieval_index_fingerprint: Optional[str] = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    judgment_policy: Optional[Dict[str, Any]] = None
    metric_specs: Optional[Dict[str, Any]] = None
    random_seed: Optional[int] = None
    claim_limitations: Optional[List[str]] = None
    evaluation_input_fingerprint: Optional[str] = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    dataset_contract: Optional[Dict[str, Any]] = None
    source_state: Optional[Dict[str, Any]] = None
    test_seal: Optional[Dict[str, str]] = None
    test_execution_audit: Optional[TestExecutionAudit] = None
    phase4_test_exposure: Optional[str] = None
    quality_result_fingerprint: Optional[str] = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    file_sha256: Optional[Dict[str, str]] = None
    warnings: Optional[List[str]] = None
    failure_reason: Optional[str] = None

    @model_validator(mode="after")
    def validate_test_audit(self) -> "EvaluationManifestV1":
        if self.split != "test":
            return self
        if self.test_execution_audit is None:
            raise ValueError("test_execution_audit is required for Test manifests")
        if self.test_seal is None:
            raise ValueError("test_seal is required for Test manifests")
        if self.source_commit_sha != self.test_execution_audit.protocol_git_commit:
            raise ValueError("Test protocol Git commit must equal source commit")
        if not self.source_state or self.source_state.get("dirty") is not False:
            raise ValueError("Test manifest requires clean source state")
        return self
