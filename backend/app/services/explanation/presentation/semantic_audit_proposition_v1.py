"""Blind, typed semantic audit for an opt-in RecruiterProposition experiment.

The extractor sees only generated prose. It is not trusted to decide PASS:
canonical propositions and exact quote coverage are checked independently.
Like any model-based extraction, recall requires empirical human calibration.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from app.schemas.shared import ContractModel
from app.services.explanation.generation.provider import ExplanationProviderRequest
from app.services.explanation.presentation.contracts_proposition_v1 import RecruiterPropositionSetV1
from app.services.explanation.presentation.facts_v3 import _concepts
from app.services.explanation.presentation.generation_proposition_v1 import (
    FIELDS, ResolvedPropositionNarrativeV1,
)


SemanticKindV1 = Literal[
    "listed_skill", "project_technology", "job_alignment", "interview_target",
    "material_unknown", "human_review_action", "strong_alignment", "candidate_experience_or_ability",
    "candidate_action_or_responsibility", "scale_or_outcome", "candidate_deficiency",
    "hire_decision", "other_assertion",
]
ReviewStrengthV1 = Literal["none", "conditional", "priority"]

_SUPPORTED_KINDS = {
    "listed_skill": "listed_skill_observation",
    "project_technology": "project_observation",
    "job_alignment": "technical_alignment",
    "interview_target": "interview_target",
    "material_unknown": "material_unknown",
    "human_review_action": "human_review_recommendation",
}


class BlindSemanticAtomV1(ContractModel):
    quote: Annotated[str, StringConstraints(min_length=2, max_length=300)]
    category: SemanticKindV1
    topics: list[Annotated[str, StringConstraints(min_length=1, max_length=80)]] = Field(max_length=12)
    review_strength: ReviewStrengthV1


class BlindParagraphAuditV1(ContractModel):
    field: Literal["decision_summary", "why_consider", "technical_signal",
                   "interview_focus", "uncertainty"]
    item_index: int = Field(ge=0, le=1)
    atoms: list[BlindSemanticAtomV1] = Field(min_length=1, max_length=12)


class BlindNarrativeAuditOutputV1(ContractModel):
    contract_version: Literal["blind_narrative_semantics_v1"]
    candidate_id: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    result_rank: int = Field(ge=1, le=10)
    paragraphs: list[BlindParagraphAuditV1] = Field(min_length=5, max_length=9)


@dataclass(frozen=True)
class SemanticAuditIssueV1:
    field: str
    item_index: int
    code: str
    quote: str = ""


@dataclass(frozen=True)
class SemanticAuditResultV1:
    issues: tuple[SemanticAuditIssueV1, ...]
    atom_count: int

    @property
    def passed(self) -> bool:
        return not self.issues


_EXTRACTOR_INSTRUCTION = """你只做盲语义抽取，不判断候选人是否真实符合岗位，也不判断有无证据。输入仅包含已经生成的正文，没有命题或引用。
请为每个段落完整抽取所有独立的事实陈述、岗位关联、面试待验证问题、材料未知和招聘动作；quote 必须逐字摘自该段落，多个 quote 合起来覆盖段落内所有有语义的文字。连接词可并入相邻 quote。每个技术主题写入 topics，使用正文中的原词；无具体技术时写空数组。
重要：问题中的预设也算陈述。“请介绍你负责的模块”应标为 candidate_action_or_responsibility；“是否负责过模块”标为 interview_target。“候选人使用 Docker 部署”是个人动作，不是 project_technology。“材料列出 Docker”才是 project_technology。“无法确认生产规模”是 material_unknown，而“具有生产规模”是 scale_or_outcome。“缺少能力”是 candidate_deficiency。
“建议优先人工技术复核”是 human_review_action 且 review_strength=priority，不是 hire_decision；只有录用、终面、offer 等录用阶段决定才是 hire_decision。“安排定向人工筛查”是 human_review_action 且 review_strength=conditional。一般“方向相关”是 job_alignment；“高度匹配、完全符合核心要求”是 strong_alignment，不得降为一般相关。job_alignment 即使含“岗位方向相关”等抽象说法，也要抽出文本实际提到的技术方向作为 topics；不得凭空补充未提到的技术。human_review_action 之外的类别 review_strength 必须是 none，包括 interview_target。quote 要覆盖句子内容，包括承接词；不要把不同独立断言合成一个更弱的类别；不确定就用 other_assertion。只输出符合 JSON Schema 的 JSON，不输出推理过程。"""


def _paragraphs(narrative: ResolvedPropositionNarrativeV1) -> dict[tuple[str, int], str]:
    result = {("decision_summary", 0): narrative.decision_summary.text}
    for field in FIELDS[1:]:
        for index, item in enumerate(getattr(narrative, field)):
            result[(field, index)] = item.text
    return result


def _inline_schema_refs(schema: dict) -> dict:
    """Syntax-only adapter for the existing native JSON-schema transport."""
    schema = deepcopy(schema)
    definitions = schema.pop("$defs", {})

    def inline(value):
        if isinstance(value, list):
            return [inline(item) for item in value]
        if not isinstance(value, dict):
            return value
        ref = value.get("$ref")
        if ref is not None:
            prefix = "#/$defs/"
            if not isinstance(ref, str) or not ref.startswith(prefix):
                raise ValueError("unsupported_semantic_audit_schema_reference")
            return inline(deepcopy(definitions[ref[len(prefix):]]))
        return {key: inline(item) for key, item in value.items()}

    return inline(schema)


def build_blind_semantic_audit_request_v1(
    narrative: ResolvedPropositionNarrativeV1, *, max_output_tokens: int,
) -> ExplanationProviderRequest:
    if type(max_output_tokens) is not int or not 512 <= max_output_tokens <= 4096:
        raise ValueError("semantic_audit_token_limit_invalid")
    payload = {
        "candidate_id": narrative.candidate_id, "result_rank": narrative.result_rank,
        "paragraphs": [
            {"field": field, "item_index": index, "text": text}
            for (field, index), text in _paragraphs(narrative).items()
        ],
    }
    user_instruction = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(user_instruction.encode("utf-8")) > 32768:
        raise ValueError("semantic_audit_input_too_large")
    return ExplanationProviderRequest(
        system_instruction=_EXTRACTOR_INSTRUCTION,
        user_instruction=user_instruction,
        output_contract_version="blind_narrative_semantics_v1",
        max_output_tokens=max_output_tokens,
        response_schema=_inline_schema_refs(BlindNarrativeAuditOutputV1.model_json_schema()),
    )


def _canonical_topics(values: list[str] | tuple[str, ...]) -> set[str]:
    result = set()
    for value in values:
        result.update(_concepts((value,)) or (value.strip().casefold(),))
    return result


def _topic_is_in_quote(topic: str, quote: str) -> bool:
    if topic.casefold() in quote.casefold():
        return True
    return bool(_concepts((topic,)) and set(_concepts((topic,))) <= set(_concepts((quote,))))


def evaluate_blind_semantic_audit_v1(
    audit: BlindNarrativeAuditOutputV1, *, narrative: ResolvedPropositionNarrativeV1,
    propositions: RecruiterPropositionSetV1,
) -> SemanticAuditResultV1:
    """Deterministic comparison over blind extraction; never consult prose refs."""
    issues: list[SemanticAuditIssueV1] = []
    if (audit.candidate_id != narrative.candidate_id or audit.result_rank != narrative.result_rank
            or propositions.candidate_id != narrative.candidate_id
            or propositions.result_rank != narrative.result_rank
            or any(item.candidate_id != narrative.candidate_id or item.result_rank != narrative.result_rank
                   for item in propositions.propositions)):
        return SemanticAuditResultV1((SemanticAuditIssueV1("identity", 0, "CANDIDATE_IDENTITY_MISMATCH"),), 0)
    expected = _paragraphs(narrative)
    actual: dict[tuple[str, int], BlindParagraphAuditV1] = {}
    for row in audit.paragraphs:
        address = (row.field, row.item_index)
        if address in actual:
            issues.append(SemanticAuditIssueV1(*address, "DUPLICATE_PARAGRAPH_AUDIT"))
        actual[address] = row
    for address in expected.keys() - actual.keys():
        issues.append(SemanticAuditIssueV1(*address, "MISSING_PARAGRAPH_AUDIT"))
    for address in actual.keys() - expected.keys():
        issues.append(SemanticAuditIssueV1(*address, "EXTRA_PARAGRAPH_AUDIT"))

    atom_count = 0
    for (field, index), text in expected.items():
        row = actual.get((field, index))
        if row is None:
            continue
        covered = [False] * len(text)
        for atom in row.atoms:
            atom_count += 1
            start = text.find(atom.quote)
            if start < 0:
                issues.append(SemanticAuditIssueV1(field, index, "QUOTE_NOT_IN_PARAGRAPH", atom.quote))
                continue
            while start >= 0:
                for position in range(start, start + len(atom.quote)):
                    covered[position] = True
                start = text.find(atom.quote, start + 1)
            if any(not _topic_is_in_quote(topic, atom.quote) for topic in atom.topics):
                issues.append(SemanticAuditIssueV1(field, index, "TOPIC_NOT_IN_QUOTE", atom.quote))
                continue
            proposition_kind = _SUPPORTED_KINDS.get(atom.category)
            if proposition_kind is None:
                issues.append(SemanticAuditIssueV1(field, index, "UNSUPPORTED_SEMANTIC_CATEGORY", atom.quote))
                continue
            if atom.category != "human_review_action" and atom.review_strength != "none":
                issues.append(SemanticAuditIssueV1(field, index, "INVALID_REVIEW_STRENGTH_ROLE", atom.quote))
                continue
            # Audit semantic support, not whether the generator chose the
            # intended UI slot. A summary may legitimately combine a fact,
            # alignment and hiring action in one natural sentence.
            supported = [item for item in propositions.propositions
                         if item.kind == proposition_kind]
            if not supported:
                issues.append(SemanticAuditIssueV1(field, index, "NO_SUPPORTING_PROPOSITION", atom.quote))
                continue
            if atom.category == "human_review_action":
                required = ("prioritize_technical_review" if atom.review_strength == "priority"
                            else "consider_targeted_screen" if atom.review_strength == "conditional"
                            else None)
                if required is None or not any(item.predicate == required for item in supported):
                    issues.append(SemanticAuditIssueV1(field, index, "REVIEW_STRENGTH_EXCEEDS_SUPPORT", atom.quote))
                    continue
            elif atom.category in {"listed_skill", "project_technology", "job_alignment"} and not atom.topics:
                issues.append(SemanticAuditIssueV1(field, index, "TECHNICAL_TOPIC_NOT_EXTRACTED", atom.quote))
                continue
            supported_topics = _canonical_topics(tuple(
                topic for item in supported for topic in item.topic_terms
            ))
            if _canonical_topics(atom.topics) - supported_topics:
                issues.append(SemanticAuditIssueV1(field, index, "TOPIC_OUTSIDE_PROPOSITION_SCOPE", atom.quote))
        if any(char.isalnum() and not covered[position] for position, char in enumerate(text)):
            issues.append(SemanticAuditIssueV1(field, index, "UNEXTRACTED_SEMANTIC_TEXT"))
    return SemanticAuditResultV1(tuple(issues), atom_count)


__all__ = [
    "BlindNarrativeAuditOutputV1", "SemanticAuditIssueV1", "SemanticAuditResultV1",
    "build_blind_semantic_audit_request_v1", "evaluate_blind_semantic_audit_v1",
]
