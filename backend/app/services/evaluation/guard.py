from __future__ import annotations

from collections.abc import Sequence
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.services.evaluation.contracts import (
    PHASE4_TEST_EXPOSURE_CAVEAT,
    TestAccessReason,
    TestExecutionAudit,
)


class TestSeal(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    protocol: str
    metrics: str
    strategies: str
    slices: str
    report: str


def validate_split_request(
    split: str,
    query_ids: Sequence[str],
    *,
    allow_test: bool,
    expected: TestSeal,
    actual: TestSeal,
    split_by_query: dict[str, str],
    source_dirty: bool = False,
    access_reason: str | TestAccessReason | None = None,
    protocol_git_commit: Optional[str] = None,
    freeze_gate_attested: bool = False,
    phase4_exposure_acknowledged: bool = False,
    phase4_exposure_caveat: Optional[str] = None,
    prior_final_run_id: Optional[str] = None,
    prior_final_input_fingerprint: Optional[str] = None,
) -> Optional[TestExecutionAudit]:
    if not query_ids:
        raise ValueError("evaluation query set is empty")
    observed = {split_by_query.get(query_id) for query_id in query_ids}
    if None in observed or observed != {split}:
        raise ValueError("mixed or unknown split query IDs")
    if split == "test":
        if not allow_test:
            raise ValueError("Test evaluation requires explicit --allow-test")
        if access_reason is None:
            raise ValueError("Test evaluation requires an explicit access reason")
        try:
            parsed_reason = TestAccessReason(access_reason)
        except ValueError as error:
            raise ValueError("unknown Test access reason") from error
        if not protocol_git_commit:
            raise ValueError("Test evaluation requires the protocol Git commit")
        if not freeze_gate_attested:
            raise ValueError("Test evaluation requires a positive freeze-gate attestation")
        if not phase4_exposure_acknowledged:
            raise ValueError("Test evaluation requires Phase 4 Test exposure acknowledgement")
        if phase4_exposure_caveat != PHASE4_TEST_EXPOSURE_CAVEAT:
            raise ValueError("Test evaluation requires the frozen Phase 4 exposure caveat")
        if expected != actual:
            raise ValueError("Test seal fingerprint mismatch")
        if source_dirty:
            raise ValueError("Test evaluation requires a clean frozen source state")
        if parsed_reason == TestAccessReason.REPRODUCTION and not (
            prior_final_run_id and prior_final_input_fingerprint
        ):
            raise ValueError("reproduction requires a prior final run reference and input fingerprint")
        return TestExecutionAudit(
            allow_test=True,
            access_reason=parsed_reason,
            protocol_git_commit=protocol_git_commit,
            freeze_gate_attested=True,
            phase4_test_exposure_acknowledged=True,
            phase4_test_exposure_caveat=PHASE4_TEST_EXPOSURE_CAVEAT,
            prior_final_run_id=prior_final_run_id,
            prior_final_input_fingerprint=prior_final_input_fingerprint,
        )
    return None


def validate_reproduction_input(audit: Optional[TestExecutionAudit], current_input_fingerprint: str) -> None:
    if audit is None or audit.access_reason != TestAccessReason.REPRODUCTION:
        return
    if audit.prior_final_input_fingerprint != current_input_fingerprint:
        raise ValueError("reproduction input fingerprint does not match prior final Test input")
