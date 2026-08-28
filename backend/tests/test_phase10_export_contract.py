from __future__ import annotations

from datetime import datetime, timezone
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.phase10 import (
    PHASE10_REVIEW_EXPORT_VERSION,
    Phase10ReviewExportV1,
)


CONTRACT_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "contracts"
    / "phase10_review_export_v1.json"
)


def _payload() -> dict:
    return {
        "contract_version": PHASE10_REVIEW_EXPORT_VERSION,
        "bad_case_id": "20000000-0000-0000-0000-000000000001",
        "match_run_id": "run-phase10-export",
        "match_result_id": 1,
        "symptom_code": "unsupported_explanation",
        "symptom_family": "EXPLANATION",
        "severity": "HIGH",
        "status": "VERIFIED",
        "source_types": ["feedback"],
        "root_cause_assessments": [
            {
                "assessment": "confirmed",
                "root_cause_type": "explanation",
                "root_cause_code": "explanation_unsupported_claim",
            }
        ],
        "evidence_kinds": ["skill"],
        "resolution_actions": [
            {
                "action_type": "grounding_integrity_action",
                "status": "completed",
            }
        ],
        "verification_state": "case_specific_verified",
        "verification_reference": "commit:phase10-verify-export",
    }


def test_phase10_review_export_is_closed_versioned_and_privacy_safe() -> None:
    export = Phase10ReviewExportV1.model_validate(_payload())
    assert export.contract_version == "phase10_review_export_v1"
    serialized = export.model_dump(mode="json")
    forbidden = {
        "comment",
        "description",
        "candidate_name",
        "company_name",
        "resume",
        "job_description",
        "provider_prompt",
        "provider_response",
        "metric",
        "ndcg",
        "mrr",
        "split",
        "current_profile",
    }
    assert forbidden.isdisjoint(serialized)
    assert json.dumps(serialized, sort_keys=True) == json.dumps(
        export.model_dump(mode="json"), sort_keys=True
    )

    with pytest.raises(ValidationError):
        Phase10ReviewExportV1.model_validate(
            {**_payload(), "metric": {"ndcg": 0.99}}
        )
    with pytest.raises(ValidationError):
        Phase10ReviewExportV1.model_validate(
            {**_payload(), "contract_version": "phase10_review_export_v2"}
        )
    with pytest.raises(ValidationError):
        Phase10ReviewExportV1.model_validate(
            {**_payload(), "symptom_code": "model_quality_bad"}
        )
    with pytest.raises(ValidationError):
        Phase10ReviewExportV1.model_validate(
            {**_payload(), "status": "EVALUATED"}
        )
    with pytest.raises(ValidationError):
        Phase10ReviewExportV1.model_validate({**_payload(), "source_types": []})
    with pytest.raises(ValidationError):
        Phase10ReviewExportV1.model_validate(
            {**_payload(), "symptom_family": "RANKING"}
        )
    with pytest.raises(ValidationError):
        Phase10ReviewExportV1.model_validate(
            {
                **_payload(),
                "root_cause_assessments": [
                    {
                        "assessment": "confirmed",
                        "root_cause_type": "ranking",
                        "root_cause_code": "explanation_unsupported_claim",
                    }
                ],
            }
        )
    with pytest.raises(ValidationError):
        Phase10ReviewExportV1.model_validate(
            {**_payload(), "status": "RESOLVED"}
        )
    missing_reference = _payload()
    missing_reference.pop("verification_reference")
    with pytest.raises(ValidationError):
        Phase10ReviewExportV1.model_validate(missing_reference)
    with pytest.raises(ValidationError):
        Phase10ReviewExportV1.model_validate(
            {
                **_payload(),
                "status": "RESOLVED",
                "verification_state": "not_verified",
            }
        )
    with pytest.raises(ValidationError):
        Phase10ReviewExportV1.model_validate(
            {
                **_payload(),
                "resolution_actions": [
                    {
                        "action_type": "ranking_change_hypothesis",
                        "status": "completed",
                    }
                ],
            }
        )


def test_phase10_review_export_schema_artifact_matches_runtime_exactly() -> None:
    artifact = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert artifact == Phase10ReviewExportV1.model_json_schema()


def test_export_contract_has_no_timestamps_or_free_form_text_channels() -> None:
    schema = Phase10ReviewExportV1.model_json_schema()
    properties = schema["properties"]
    assert "created_at" not in properties
    assert "updated_at" not in properties
    assert "comment" not in properties
    assert "description" not in properties


def test_export_service_rejects_a_truncated_bad_case_projection() -> None:
    from app.services.bad_cases.service import BadCaseReviewService
    from app.services.feedback.errors import ReviewConflictError

    class TruncatedRepository:
        async def get_by_id(self, bad_case_id, *, child_limit):
            assert bad_case_id == "case-truncated"
            assert child_limit == 100
            return SimpleNamespace(
                truncated_collections=frozenset({"analyses"})
            )

    service = BadCaseReviewService(
        lambda: None,
        repository=TruncatedRepository(),
    )
    with pytest.raises(ReviewConflictError, match="complete bounded"):
        asyncio.run(service.export_review("case-truncated"))
