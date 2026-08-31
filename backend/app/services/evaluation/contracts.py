from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class EvaluationRunStatus(str, Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    INVALID = "INVALID"


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
    phase4_test_exposure: Optional[str] = None
    quality_result_fingerprint: Optional[str] = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    file_sha256: Optional[Dict[str, str]] = None
    warnings: Optional[List[str]] = None
    failure_reason: Optional[str] = None
