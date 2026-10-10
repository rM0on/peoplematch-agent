"""Opt-in Proposition-to-language experiment; not part of product runtime.

The provider sees typed semantic boundaries and short request-scoped handles,
never opaque proposition IDs. Structural attribution is checked here; semantic
entailment of open prose still requires separate human review.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
from typing import Annotated, Literal

from pydantic import Field, StrictBool, StringConstraints, model_validator

from app.schemas.shared import ContractModel
from app.services.explanation.generation.provider import ExplanationProviderRequest
from app.services.explanation.presentation.adapter import NarrativeProjection
from app.services.explanation.presentation.contracts_proposition_v1 import (
    NarrativeFieldV1, RecruiterPropositionSetV1,
)
from app.services.explanation.presentation.propositions_v1 import validate_recruiter_propositions_v1


FIELDS = ("decision_summary", "why_consider", "technical_signal", "interview_focus", "uncertainty")


@dataclass(frozen=True)
class PropositionHandleEntryV1:
    handle: str
    proposition_id: str
    candidate_id: str
    allowed_fields: tuple[NarrativeFieldV1, ...]


@dataclass(frozen=True)
class PropositionHandleBindingV1:
    candidate_id: str
    result_rank: int
    entries: tuple[PropositionHandleEntryV1, ...]

    def allowed_handles(self, field: str) -> tuple[str, ...]:
        if field not in FIELDS:
            raise ValueError("unknown_narrative_field")
        return tuple(entry.handle for entry in self.entries if field in entry.allowed_fields)

    def resolve(self, handles: list[str], *, field: str) -> list[str]:
        if not handles or len(handles) > 4 or len(handles) != len(set(handles)):
            raise ValueError("invalid_proposition_handles")
        allowed = {entry.handle: entry for entry in self.entries if field in entry.allowed_fields}
        result = []
        for handle in handles:
            entry = allowed.get(handle)
            if entry is None or entry.candidate_id != self.candidate_id:
                raise ValueError("unknown_or_wrong_role_proposition_handle")
            result.append(entry.proposition_id)
        return result


def build_proposition_binding_v1(propositions: RecruiterPropositionSetV1) -> PropositionHandleBindingV1:
    if not propositions.propositions or any(
        item.candidate_id != propositions.candidate_id or item.result_rank != propositions.result_rank
        for item in propositions.propositions
    ):
        raise ValueError("proposition_candidate_mismatch")
    ordered = sorted(propositions.propositions, key=lambda item: item.proposition_id)
    if len({item.proposition_id for item in ordered}) != len(ordered):
        raise ValueError("duplicate_proposition_id")
    entries = tuple(PropositionHandleEntryV1(
        handle=f"P{index:02d}", proposition_id=item.proposition_id,
        candidate_id=item.candidate_id, allowed_fields=item.allowed_fields,
    ) for index, item in enumerate(ordered, 1))
    binding = PropositionHandleBindingV1(propositions.candidate_id, propositions.result_rank, entries)
    if any(not binding.allowed_handles(field) for field in FIELDS):
        raise ValueError("incomplete_proposition_field_coverage")
    return binding


class ProviderPropositionParagraphV1(ContractModel):
    text: Annotated[str, StringConstraints(min_length=8, max_length=300)]
    # A selection map uses JSON's unique member names rather than an array
    # keyword unsupported by this provider. Raw duplicate keys are rejected
    # before Pydantic parses the payload; no duplicate is ever normalized.
    proposition_handles: dict[str, StrictBool]

    @model_validator(mode="after")
    def handles_are_unique(self) -> ProviderPropositionParagraphV1:
        if not 1 <= len(self.proposition_handles) <= 4 or not all(self.proposition_handles.values()):
            raise ValueError("invalid_selected_proposition_count")
        return self


class PropositionProviderOutputV1(ContractModel):
    contract_version: Literal["recruiter_proposition_generation_v1"]
    candidate_id: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    result_rank: int = Field(ge=1, le=10)
    decision_summary: ProviderPropositionParagraphV1
    why_consider: list[ProviderPropositionParagraphV1] = Field(min_length=1, max_length=2)
    technical_signal: list[ProviderPropositionParagraphV1] = Field(min_length=1, max_length=2)
    interview_focus: list[ProviderPropositionParagraphV1] = Field(min_length=1, max_length=2)
    uncertainty: list[ProviderPropositionParagraphV1] = Field(min_length=1, max_length=2)


class ResolvedPropositionParagraphV1(ContractModel):
    text: Annotated[str, StringConstraints(min_length=8, max_length=300)]
    proposition_refs: list[str] = Field(min_length=1, max_length=4)


class ResolvedPropositionNarrativeV1(ContractModel):
    contract_version: Literal["recruiter_proposition_generation_v1"]
    candidate_id: str
    result_rank: int
    decision_summary: ResolvedPropositionParagraphV1
    why_consider: list[ResolvedPropositionParagraphV1]
    technical_signal: list[ResolvedPropositionParagraphV1]
    interview_focus: list[ResolvedPropositionParagraphV1]
    uncertainty: list[ResolvedPropositionParagraphV1]


def build_proposition_response_schema_v1(binding: PropositionHandleBindingV1) -> dict:
    """Reuse the V5 native-schema wire pattern with field-specific enums."""
    schema = PropositionProviderOutputV1.model_json_schema()
    paragraph = schema.pop("$defs")["ProviderPropositionParagraphV1"]
    for field in FIELDS:
        inline = deepcopy(paragraph)
        handles = list(binding.allowed_handles(field))
        inline["properties"]["proposition_handles"] = {
            "type": "object", "properties": {handle: {"type": "boolean"} for handle in handles},
            "required": [], "additionalProperties": False,
        }
        if field == "decision_summary":
            schema["properties"][field] = inline
        else:
            schema["properties"][field]["items"] = inline
    return schema


_SYSTEM_INSTRUCTION = """你是一名资深技术招聘负责人，给 Hiring Manager 写简短、自然的候选评估。
只使用本请求 proposition_catalog 中的语义：fact 是材料中明确出现的内容；alignment 只是与岗位方向有关，不能写成候选人已具备能力或经验；hypothesis 是下一轮待确认事项，不能预设候选人负责、主导或完成；unknown 是目前无法确认，不能写成候选人缺陷。recommendation 的 predicate=consider_targeted_screen 只允许建议定向人工筛查，不得写优先；predicate=prioritize_technical_review 才允许建议优先人工技术复核；二者都不是录用结论。
回答为什么值得继续看、相关技术方向、下一轮要问什么、目前还不能确定什么。可以自然合并多个命题并调整语言顺序；不要逐条复述目录、罗列技术栈或输出系统术语。每个段落的 proposition_handles 是 JSON 对象，不是数组；仅写入实际选中的 1–4 个预设 Handle 键，值固定为 true，未选中的键必须省略。不得引入目录外的新技能、职责、规模、结果或候选判断。只输出满足 JSON Schema 的 JSON。"""


def build_proposition_generation_request_v1(
    projection: NarrativeProjection, propositions: RecruiterPropositionSetV1,
    *, max_output_tokens: int,
) -> ExplanationProviderRequest:
    validate_recruiter_propositions_v1(propositions, projection=projection)
    if not projection.role_title.strip() or type(max_output_tokens) is not int or not 512 <= max_output_tokens <= 4096:
        raise ValueError("proposition_generation_request_invalid")
    binding = build_proposition_binding_v1(propositions)
    lookup = {item.proposition_id: item for item in propositions.propositions}
    catalog = []
    for entry in binding.entries:
        item = lookup[entry.proposition_id]
        catalog.append({
            "handle": entry.handle, "kind": item.kind, "subject": item.subject,
            "predicate": item.predicate, "modality": item.modality,
            "topic_terms": item.topic_terms,
            "job_requirement_terms": item.job_requirement_terms,
            "allowed_fields": item.allowed_fields,
        })
    payload = {
        "candidate_id": propositions.candidate_id,
        "result_rank": propositions.result_rank,
        "role_title": projection.role_title,
        "proposition_catalog": catalog,
    }
    user_instruction = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(user_instruction.encode("utf-8")) > 131072:
        raise ValueError("proposition_catalog_too_large")
    return ExplanationProviderRequest(
        system_instruction=_SYSTEM_INSTRUCTION,
        user_instruction=user_instruction,
        output_contract_version="recruiter_proposition_generation_v1",
        max_output_tokens=max_output_tokens,
        response_schema=build_proposition_response_schema_v1(binding),
    )


def resolve_proposition_output_v1(
    output: PropositionProviderOutputV1, binding: PropositionHandleBindingV1,
) -> ResolvedPropositionNarrativeV1:
    if output.candidate_id != binding.candidate_id or output.result_rank != binding.result_rank:
        raise ValueError("provider_output_candidate_mismatch")

    def paragraph(item: ProviderPropositionParagraphV1, field: str) -> dict:
        if not set(item.proposition_handles) <= set(binding.allowed_handles(field)):
            raise ValueError("unknown_or_wrong_role_proposition_handle_key")
        selected = [entry.handle for entry in binding.entries
                    if entry.handle in item.proposition_handles and item.proposition_handles[entry.handle]]
        return {"text": item.text,
                "proposition_refs": binding.resolve(selected, field=field)}

    return ResolvedPropositionNarrativeV1.model_validate({
        "contract_version": output.contract_version,
        "candidate_id": output.candidate_id,
        "result_rank": output.result_rank,
        "decision_summary": paragraph(output.decision_summary, "decision_summary"),
        **{field: [paragraph(item, field) for item in getattr(output, field)]
           for field in FIELDS if field != "decision_summary"},
    })


def parse_proposition_provider_output_v1(content: str) -> PropositionProviderOutputV1:
    """Reject duplicate raw JSON members before an object map can erase them."""
    def unique_object(pairs: list[tuple[str, object]]) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate_json_key")
            result[key] = value
        return result

    return PropositionProviderOutputV1.model_validate(
        json.loads(content, object_pairs_hook=unique_object))


__all__ = [
    "PropositionProviderOutputV1", "ResolvedPropositionNarrativeV1",
    "build_proposition_binding_v1", "build_proposition_response_schema_v1",
    "build_proposition_generation_request_v1", "parse_proposition_provider_output_v1",
    "resolve_proposition_output_v1",
]
