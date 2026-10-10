"""Presentation-only fact graph derived from selected, validated evidence.

An edge records an observed relationship, never candidate ownership, depth,
production scale, or impact. Each graph is rebuilt for one candidate.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from app.services.explanation.presentation.adapter import NarrativeProjection
from app.services.explanation.presentation.facts_v2_2 import build_evidence_package_v2_2
from app.services.match_runs.contracts import canonical_fingerprint


_ALIASES: dict[str, tuple[str, ...]] = {
    "retrieval": ("retrieval", "vector search", "向量检索", "检索", "召回"),
    "ranking": ("lambdamart", "learning to rank", "reranking", "ranking", "排序", "重排"),
    "evaluation": ("offline evaluation", "embedding evaluation", "evaluation", "评估"),
    "feature engineering": ("feature engineering", "特征工程"),
    "rag": ("rag", "retrieval augmented generation", "检索增强"),
    "agent workflow": ("agent workflow", "ai agent", "智能体编排", "智能体"),
    "fastapi": ("fastapi",),
    "postgresql": ("postgresql",),
    "redis": ("redis",),
    "docker": ("docker",),
    "qdrant": ("qdrant",),
    "python": ("python",),
    "embedding": ("embedding", "向量表示"),
    "api design": ("api design", "api 设计", "接口设计"),
    "llm application": ("llm application", "llm 应用", "大模型应用"),
    "structured output": ("structured output", "结构化输出"),
    "prompt engineering": ("prompt engineering", "提示词工程"),
    "vector database": ("vector database", "向量数据库"),
}


def _concepts(terms: tuple[str, ...]) -> tuple[str, ...]:
    joined = " ".join(terms).casefold()
    found = set()
    for concept, aliases in _ALIASES.items():
        if any(re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", joined)
               for alias in aliases):
            found.add(concept)
    return tuple(sorted(found))


@dataclass(frozen=True)
class GraphFactV3:
    fact_id: str
    kind: str
    concepts: tuple[str, ...]
    source_terms: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    source_fact_ids: tuple[str, ...]
    allowed_inference: str

    @property
    def term(self) -> str:
        return " ".join((*self.source_terms, *self.concepts))


@dataclass(frozen=True)
class GraphEdgeV3:
    source_id: str
    target_id: str
    relation: str


@dataclass(frozen=True)
class ClaimCandidateV3:
    claim_type: str
    topic: str
    fact_ids: tuple[str, ...]


@dataclass(frozen=True)
class AtomicFactGraphV3:
    candidate_id: str
    result_rank: int
    facts: tuple[GraphFactV3, ...]
    edges: tuple[GraphEdgeV3, ...]
    claim_candidates: tuple[ClaimCandidateV3, ...]


def _make(projection: NarrativeProjection, kind: str, concepts: tuple[str, ...],
          terms: tuple[str, ...], refs: tuple[str, ...], source_ids: tuple[str, ...],
          inference: str) -> GraphFactV3:
    return GraphFactV3(
        fact_id="fact:" + canonical_fingerprint({
            "version": "3", "candidate": projection.candidate_id, "rank": projection.result_rank,
            "kind": kind, "concepts": concepts, "refs": refs, "sources": source_ids,
        })[:32],
        kind=kind, concepts=concepts, source_terms=terms, evidence_refs=refs,
        source_fact_ids=source_ids, allowed_inference=inference,
    )


def build_atomic_fact_graph_v3(projection: NarrativeProjection) -> AtomicFactGraphV3:
    """Connect only selected evidence and explicit selected job requirements."""
    package = build_evidence_package_v2_2(projection)
    owner = f"candidate:{projection.result_rank}:"
    facts: dict[str, GraphFactV3] = {}
    edges: set[GraphEdgeV3] = set()
    candidates: set[ClaimCandidateV3] = set()
    skill_nodes: list[GraphFactV3] = []
    project_nodes: list[GraphFactV3] = []
    scope_nodes: list[GraphFactV3] = []

    for source in (*package.skills, *package.project_practice):
        refs = tuple(sorted(source.evidence_refs))
        if not refs or any(not ref.startswith(owner) for ref in refs):
            continue
        concepts = _concepts(source.terms)
        if not concepts:
            continue
        kind = "candidate_capability" if source.kind == "candidate_skill" else "project_evidence"
        node = _make(projection, kind, concepts, source.terms, refs, (source.fact_id,),
                     "资料列出相关技术或项目覆盖范围；仅可谈方向与待核实问题，不推断个人职责、规模或结果")
        facts[node.fact_id] = node
        candidates.add(ClaimCandidateV3("evidence_statement", ", ".join(concepts), (node.fact_id,)))
        if kind == "project_evidence":
            project_nodes.append(node)
            if len(concepts) >= 2:
                scope = _make(projection, "technical_scope", concepts, source.terms, refs,
                              (source.fact_id,), "同一项目材料覆盖这些技术；仅可组合为技术范围，不推断个人行动")
                facts[scope.fact_id] = scope
                scope_nodes.append(scope)
                edges.add(GraphEdgeV3(node.fact_id, scope.fact_id, "same_project_scope"))
                candidates.add(ClaimCandidateV3("evidence_statement", ", ".join(concepts),
                                                (scope.fact_id,)))
        else:
            skill_nodes.append(node)
    for skill in skill_nodes:
        for project in project_nodes:
            if set(skill.concepts) & set(project.concepts):
                edges.add(GraphEdgeV3(skill.fact_id, project.fact_id,
                                      "listed_skill_overlaps_project_term"))
    if len(project_nodes) >= 2:
        portfolio_concepts = tuple(sorted({concept for node in project_nodes for concept in node.concepts}))
        portfolio_terms = tuple(sorted({term for node in project_nodes for term in node.source_terms},
                                       key=str.casefold))
        portfolio_refs = tuple(sorted({ref for node in project_nodes for ref in node.evidence_refs}))
        portfolio = _make(
            projection, "candidate_portfolio_scope", portfolio_concepts,
            portfolio_terms, portfolio_refs, tuple(sorted(node.fact_id for node in project_nodes)),
            "不同项目材料合计覆盖这些技术；不可说成同一项目，也不推断个人职责、规模或结果",
        )
        facts[portfolio.fact_id] = portfolio
        for node in project_nodes:
            edges.add(GraphEdgeV3(node.fact_id, portfolio.fact_id, "distinct_project_coverage"))
        candidates.add(ClaimCandidateV3("evidence_statement", ", ".join(portfolio_concepts),
                                        (portfolio.fact_id,)))
    requirement_refs = sorted(ref for ref in projection.positive_refs if ref.startswith("job_requirement:")
                              and ref in projection.facts)
    for req_ref in requirement_refs:
        req_terms = projection.facts[req_ref]
        req_concepts = set(_concepts(req_terms))
        for node in project_nodes + [f for f in facts.values() if f.kind == "candidate_capability"]:
            common = tuple(sorted(req_concepts & set(node.concepts)))
            if not common:
                continue
            align = _make(projection, "job_alignment", common, (*node.source_terms, *common),
                          tuple(sorted((*node.evidence_refs, req_ref))), (node.fact_id,),
                          "候选材料与岗位要求存在技术方向关联；只能建议人工复核，不能断言胜任")
            facts[align.fact_id] = align
            edges.add(GraphEdgeV3(node.fact_id, align.fact_id, "observed_requirement_overlap"))
            source_scope = next((scope for scope in scope_nodes
                                 if scope.evidence_refs == node.evidence_refs), None)
            linked = (align.fact_id, source_scope.fact_id if source_scope else node.fact_id)
            candidates.add(ClaimCandidateV3("capability_inference", ", ".join(common), linked))
    for node in project_nodes:
        focus = _make(projection, "interview_validation", node.concepts, node.source_terms,
                      node.evidence_refs, (node.fact_id,),
                      "仅可就材料所列技术提出假设性设计或工程取舍问题；不得写成已有经历")
        facts[focus.fact_id] = focus
        edges.add(GraphEdgeV3(node.fact_id, focus.fact_id, "verify_observed_scope"))
        candidates.add(ClaimCandidateV3("interview_validation", ", ".join(node.concepts),
                                        (focus.fact_id,)))
        candidates.add(ClaimCandidateV3("uncertainty_statement", ", ".join(node.concepts),
                                        (focus.fact_id,)))
    open_nodes: list[GraphFactV3] = []
    for source in package.uncertainties:
        refs = tuple(sorted(source.evidence_refs))
        if not refs or any(not ref.startswith("job_requirement:") for ref in refs):
            continue
        node = _make(projection, "open_requirement", _concepts(source.terms), source.terms,
                     refs, (source.fact_id,), "岗位要求待人工确认；不能断言候选人缺乏该能力")
        facts[node.fact_id] = node
        open_nodes.append(node)
        candidates.add(ClaimCandidateV3("uncertainty_statement", node.term, (node.fact_id,)))
    if len(open_nodes) >= 2:
        group = _make(
            projection, "open_requirement_group",
            tuple(sorted({concept for node in open_nodes for concept in node.concepts})),
            tuple(sorted({term for node in open_nodes for term in node.source_terms}, key=str.casefold)),
            tuple(sorted({ref for node in open_nodes for ref in node.evidence_refs})),
            tuple(sorted(node.fact_id for node in open_nodes)),
            "同一岗位有多项待核实要求；仅可建议分别确认，不可断言候选人欠缺",
        )
        facts[group.fact_id] = group
        for node in open_nodes:
            edges.add(GraphEdgeV3(node.fact_id, group.fact_id, "same_job_open_requirements"))
        candidates.add(ClaimCandidateV3("uncertainty_statement", group.term, (group.fact_id,)))
    return AtomicFactGraphV3(
        candidate_id=projection.candidate_id, result_rank=projection.result_rank,
        facts=tuple(sorted(facts.values(), key=lambda f: f.fact_id)),
        edges=tuple(sorted(edges, key=lambda e: (e.source_id, e.target_id, e.relation))),
        claim_candidates=tuple(sorted(candidates, key=lambda c: (c.claim_type, c.topic, c.fact_ids))),
    )


__all__ = ["AtomicFactGraphV3", "GraphFactV3", "GraphEdgeV3", "ClaimCandidateV3",
           "build_atomic_fact_graph_v3", "_concepts"]
