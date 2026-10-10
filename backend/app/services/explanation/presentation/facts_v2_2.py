from __future__ import annotations

from dataclasses import dataclass

from app.services.explanation.presentation.adapter import NarrativeProjection
from app.services.explanation.presentation.facts_v2_1 import build_atomic_facts_v2_1
from app.services.match_runs.contracts import canonical_fingerprint


@dataclass(frozen=True)
class EnrichedFactV2_2:
    fact_id: str
    kind: str
    terms: tuple[str, ...]
    evidence_refs: frozenset[str]
    allowed_inference: str

    @property
    def term(self) -> str:
        return " ".join(self.terms)


@dataclass(frozen=True)
class CandidateEvidencePackageV2_2:
    skills: tuple[EnrichedFactV2_2, ...]
    project_practice: tuple[EnrichedFactV2_2, ...]
    technical_scope: tuple[EnrichedFactV2_2, ...]
    requirement_alignment: tuple[EnrichedFactV2_2, ...]
    uncertainties: tuple[EnrichedFactV2_2, ...]
    interview_verification: tuple[EnrichedFactV2_2, ...]

    @property
    def all_facts(self) -> tuple[EnrichedFactV2_2, ...]:
        return (self.skills + self.project_practice + self.technical_scope
                + self.requirement_alignment + self.uncertainties + self.interview_verification)


_SCOPES = (
    (frozenset({"rag", "retrieval"}), "RAG 检索链路", "检索设计与召回取舍"),
    (frozenset({"rag", "qdrant"}), "RAG 向量检索", "向量检索方案选择"),
    (frozenset({"rag", "fastapi"}), "AI应用 后端服务", "检索与服务接口的衔接"),
    (frozenset({"retrieval", "lambdamart"}), "推荐系统 召回排序", "召回与排序的分工"),
    (frozenset({"lambdamart", "evaluation"}), "推荐系统 评估", "排序评估方法"),
    (frozenset({"fastapi", "postgresql"}), "后端工程 服务数据", "接口与数据建模取舍"),
)


def _make(kind: str, terms: tuple[str, ...], refs: frozenset[str], inference: str) -> EnrichedFactV2_2:
    return EnrichedFactV2_2(
        fact_id="fact:" + canonical_fingerprint({"v": "2.2", "kind": kind, "terms": terms,
                                                  "refs": sorted(refs)})[:32],
        kind=kind, terms=terms, evidence_refs=refs, allowed_inference=inference,
    )


def build_evidence_package_v2_2(projection: NarrativeProjection) -> CandidateEvidencePackageV2_2:
    """Derive presentation-only scope from *selected* evidence, without ownership claims."""
    rank = str(projection.result_rank)
    own_prefix = f"candidate:{rank}:"
    base = build_atomic_facts_v2_1(projection)
    skills = tuple(_make("candidate_skill", (f.term,), frozenset(f.evidence_refs), f.allowed_inference)
                   for f in base if f.kind == "candidate_skill"
                   and all(ref.startswith(own_prefix) for ref in f.evidence_refs))
    practices = []
    scopes = []
    questions = []
    for ref in sorted(projection.positive_refs):
        if not ref.startswith(own_prefix + "project:"):
            continue
        terms = tuple(sorted(set(projection.facts.get(ref, ())), key=str.casefold))
        if not terms:
            continue
        practices.append(_make("project_practice", terms, frozenset({ref}),
                               "同一项目材料列出这些技术；只能说覆盖相关实践，不能断言个人职责、深度或成果"))
        observed = {term.casefold() for term in terms}
        for required, label, question_topic in _SCOPES:
            if not required <= observed:
                continue
            selected = tuple(term for term in terms if term.casefold() in required)
            scope = _make("technical_scope", (*selected, label), frozenset({ref}),
                          "可说项目材料覆盖该技术范围；不能说候选人亲自设计、开发、部署或取得成果")
            scopes.append(scope)
            questions.append(_make("interview_verification", (*selected, question_topic),
                                   frozenset({ref}),
                                   "可作为假设性面试问题验证方案和取舍；不能写成既有候选人经历"))
    alignments = tuple(_make("requirement_alignment", (f.term,), frozenset(f.evidence_refs), f.allowed_inference)
                       for f in base if f.kind == "requirement_alignment"
                       and any(ref.startswith(own_prefix) for ref in f.evidence_refs))
    unknown = tuple(_make("open_requirement", (f.term,), frozenset(f.evidence_refs), f.allowed_inference)
                    for f in base if f.kind == "open_requirement")
    return CandidateEvidencePackageV2_2(skills, tuple(practices), tuple(scopes), alignments,
                                        unknown, tuple(questions))


__all__ = ["CandidateEvidencePackageV2_2", "EnrichedFactV2_2", "build_evidence_package_v2_2"]
