from __future__ import annotations

from typing import Any

from app.schemas.phase10 import Phase10ReviewExportV1


def validate_phase10_export(payload: dict[str, Any]) -> Phase10ReviewExportV1:
    if payload.get("truncated_collections"):
        raise ValueError("truncated Phase 10 export cannot be consumed")
    if payload.get("contract_version") != "phase10_review_export_v1":
        raise ValueError("unknown Phase 10 export schema")
    if payload.get("verification_state") == "case_specific_verified" and not payload.get("verification_reference"):
        raise ValueError("case-specific verification requires immutable verification provenance")
    return Phase10ReviewExportV1.model_validate(payload)
