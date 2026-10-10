"""One-shot V5 JSON-container repair; never rewrite recruiter claims or prose."""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from app.services.explanation.generation.provider import ExplanationProviderRequest
from app.services.explanation.presentation.contracts_v5 import RecruiterNarrativeV5


_PARAGRAPH_LIST_FIELDS = frozenset({
    "why_consider", "technical_signal", "interview_focus", "uncertainty",
})
_MAX_REPAIR_PROMPT_BYTES = 196608


def prepare_schema_repair_v1(
    raw_output: str, error: ValidationError,
) -> tuple[dict[str, Any], list[dict[str, str]]] | None:
    """Accept only parseable object-for-list errors already observed in V5."""
    try:
        original = json.loads(raw_output)
    except (ValueError, TypeError):
        return None
    if not isinstance(original, dict):
        return None
    diagnostics: list[dict[str, str]] = []
    for item in error.errors():
        location = item.get("loc", ())
        if (item.get("type") != "list_type" or len(location) != 1
                or location[0] not in _PARAGRAPH_LIST_FIELDS
                or not isinstance(original.get(location[0]), dict)):
            return None
        diagnostics.append({"field": location[0], "type": "list_type"})
    return (original, diagnostics) if diagnostics else None


def build_schema_repair_v1_request(
    original_request: ExplanationProviderRequest, *,
    original_output: dict[str, Any], schema_errors: list[dict[str, str]],
) -> ExplanationProviderRequest:
    if original_request.output_contract_version != "recruiter_narrative_v5" or not schema_errors:
        raise ValueError("V5 schema repair input invalid")
    payload = {
        "original_output": original_output,
        "target_json_schema": RecruiterNarrativeV5.model_json_schema(),
        "schema_errors": schema_errors,
    }
    instruction = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(instruction.encode("utf-8")) > _MAX_REPAIR_PROMPT_BYTES:
        raise ValueError("V5 schema repair prompt exceeds byte limit")
    return ExplanationProviderRequest(
        system_instruction=(
            "只修复 JSON 容器结构。将 schema_errors 指出的单个对象放入目标字段的 JSON 数组，"
            "即使只有一项也必须使用数组。不得新增、删除、改写、移动任何正文或 claim_refs；"
            "不得改变 candidate_id、result_rank、合同版本或招聘结论。"
            "仅输出完整 JSON，不附 Markdown。"
        ),
        user_instruction=instruction,
        output_contract_version=original_request.output_contract_version,
        max_output_tokens=original_request.max_output_tokens,
    )


def schema_repair_preserves_content_v1(
    original: dict[str, Any], repaired_content: str,
) -> bool:
    """Compare semantics only; never normalize the value passed to Pydantic."""
    try:
        repaired = json.loads(repaired_content)
    except (ValueError, TypeError):
        return False
    if not isinstance(repaired, dict) or set(original) != set(repaired):
        return False
    for field, value in original.items():
        if field in _PARAGRAPH_LIST_FIELDS and isinstance(value, dict):
            # This expected shape is used only for comparison, never as output.
            if repaired[field] != [value]:
                return False
        elif repaired[field] != value:
            return False
    return True


__all__ = [
    "prepare_schema_repair_v1", "build_schema_repair_v1_request",
    "schema_repair_preserves_content_v1",
]
