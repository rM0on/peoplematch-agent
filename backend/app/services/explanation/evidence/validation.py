from __future__ import annotations

from app.services.explanation.contracts import evidence_bundle_fingerprint
from app.services.explanation.evidence.fingerprints import evidence_content_fingerprint


def _reference_index(bundle):
    index = {}
    for item in bundle.job.requirements:
        index[item.evidence_id] = (
            "job_requirement",
            None,
            None,
            None,
            item.requirement_id,
        )
    for candidate in bundle.candidates:
        for items, kind in (
            (candidate.skills, "skill"),
            (candidate.projects, "project"),
            (candidate.project_evidence, "project_evidence"),
        ):
            for item in items:
                index[item.evidence_id] = (
                    kind,
                    candidate.candidate_id,
                    candidate.result_rank,
                    None,
                    getattr(item, "name", None)
                    or getattr(item, "project_id", None)
                    or getattr(item, "source_evidence_id", None),
                )
        for fact in candidate.facts:
            index[fact.evidence_id] = (
                fact.kind.value,
                candidate.candidate_id,
                candidate.result_rank,
                fact.comparison_candidate_id,
                fact.name.value if hasattr(fact.name, "value") else fact.name,
            )
    return index


def validate_fact_references(
    bundle,
    *,
    candidate_id: str,
    result_rank: int,
    evidence_refs: list[str],
    expected_run_id: str | None = None,
    allowed_kinds: set[str] | None = None,
    allowed_names: set[str] | None = None,
) -> None:
    if expected_run_id is not None and bundle.source.match_run_id != expected_run_id:
        raise ValueError("Evidence references belong to another MatchRun Evidence Bundle")
    owner = next(
        (candidate for candidate in bundle.candidates if candidate.result_rank == result_rank),
        None,
    )
    if owner is None or owner.candidate_id != candidate_id:
        raise ValueError("fact Candidate owner does not match Evidence Bundle")
    index = _reference_index(bundle)
    rank_one = bundle.candidates[0]
    for ref in evidence_refs:
        metadata = index.get(ref)
        if metadata is None:
            raise ValueError(f"evidence reference {ref} does not exist in Evidence Bundle")
        kind, ref_candidate_id, ref_rank, comparison_candidate_id, fact_name = metadata
        if ref_candidate_id is not None and (
            ref_candidate_id != candidate_id or ref_rank != result_rank
        ):
            raise ValueError(f"evidence reference {ref} owner does not match fact Candidate")
        if kind == "comparison" and comparison_candidate_id != rank_one.candidate_id:
            raise ValueError(f"evidence reference {ref} does not reference the rank-1 Candidate")
        if allowed_kinds is not None and kind not in allowed_kinds:
            raise ValueError(f"evidence reference {ref} is incompatible with generated fact")
        if allowed_names is not None and fact_name not in allowed_names:
            raise ValueError(
                f"evidence reference {ref} violates the semantic evidence mapping"
            )


def validate_evidence_facts(bundle, facts) -> None:
    """Validate every generated fact reference against its historical bundle."""
    expected_fingerprint = evidence_bundle_fingerprint(bundle)
    if facts.bundle_fingerprint != expected_fingerprint:
        raise ValueError("Evidence facts bundle fingerprint does not match Evidence Bundle")
    if facts.normalized_content_fingerprint != evidence_content_fingerprint(bundle):
        raise ValueError(
            "Evidence facts normalized content fingerprint does not match Evidence Bundle"
        )
    expected_candidates = [
        (candidate.candidate_id, candidate.result_rank) for candidate in bundle.candidates
    ]
    actual_candidates = [
        (candidate.candidate_id, candidate.result_rank) for candidate in facts.candidates
    ]
    if actual_candidates != expected_candidates:
        raise ValueError("Candidate fact coverage does not match Evidence Bundle ranks")

    from app.services.explanation.evidence.comparison_builder import Top1ComparisonBuilder
    from app.services.explanation.evidence.fact_builder import (
        RANKING_CONTEXT_SOURCE_KINDS,
        build_match_reasons,
        build_ranking_context,
    )
    from app.services.explanation.evidence.requirement_builder import MissingRequirementBuilder

    requirements_by_candidate = {}
    for requirement in MissingRequirementBuilder().build(bundle):
        requirements_by_candidate.setdefault(
            (requirement.candidate_id, requirement.result_rank), []
        ).append(requirement)
    comparisons_by_candidate = {
        (item.candidate_id, item.result_rank): item.comparison
        for item in Top1ComparisonBuilder().build(bundle)
    }
    for candidate_facts in facts.candidates:
        bundle_candidate = next(
            item
            for item in bundle.candidates
            if item.candidate_id == candidate_facts.candidate_id
            and item.result_rank == candidate_facts.result_rank
        )
        expected_requirements = requirements_by_candidate[
            (candidate_facts.candidate_id, candidate_facts.result_rank)
        ]
        reason_semantics = {
            "skill_fit": (
                {"skill", "project", "job_requirement"},
                None,
            ),
            "project_evidence": ({"project", "project_evidence"}, None),
            "location": ({"diagnostic"}, {"location_relation"}),
            "seniority": ({"diagnostic"}, {"seniority_relation"}),
        }
        risk_semantics = {
            "missing_requirement": ({"job_requirement"}, None),
            "weak_evidence": ({"job_requirement"}, None),
            "overclaim_signal": ({"diagnostic"}, {"overclaim_level"}),
        }
        for item in candidate_facts.match_reasons:
            kinds, names = reason_semantics[item.category]
            validate_fact_references(
                bundle,
                candidate_id=candidate_facts.candidate_id,
                result_rank=candidate_facts.result_rank,
                evidence_refs=item.evidence_refs,
                allowed_kinds=kinds,
                allowed_names=names,
            )
            if item.category == "skill_fit":
                reference_index = _reference_index(bundle)
                referenced_kinds = {
                    reference_index[evidence_ref][0]
                    for evidence_ref in item.evidence_refs
                }
                if not referenced_kinds & {"skill", "project"} or (
                    "job_requirement" not in referenced_kinds
                ):
                    raise ValueError(
                        "skill_fit requires both Candidate and Job evidence"
                    )
        if candidate_facts.match_reasons != build_match_reasons(
            bundle, bundle_candidate
        ):
            raise ValueError(
                "match reason semantics do not match historical evidence"
            )
        for item in candidate_facts.ranking_context:
            kind = RANKING_CONTEXT_SOURCE_KINDS[item.dimension]
            validate_fact_references(
                bundle,
                candidate_id=candidate_facts.candidate_id,
                result_rank=candidate_facts.result_rank,
                evidence_refs=item.evidence_refs,
                allowed_kinds={kind},
                allowed_names={item.dimension},
            )
        if candidate_facts.ranking_context != build_ranking_context(bundle_candidate):
            raise ValueError(
                "ranking context does not match recorded feature and ranking evidence"
            )
        for item in candidate_facts.risks:
            kinds, names = risk_semantics[item.category]
            validate_fact_references(
                bundle,
                candidate_id=candidate_facts.candidate_id,
                result_rank=candidate_facts.result_rank,
                evidence_refs=item.evidence_refs,
                allowed_kinds=kinds,
                allowed_names=names,
            )
        expected_risks = [
            (
                "missing_requirement" if item.status == "missing" else "weak_evidence",
                "missing_requirement"
                if item.status == "missing"
                else "partial_requirement_evidence",
                item.evidence_refs,
            )
            for item in expected_requirements
            if item.status in {"missing", "partial"}
        ]
        overclaim = next(
            (
                item
                for item in bundle_candidate.facts
                if item.kind.value == "diagnostic" and item.name == "overclaim_level"
            ),
            None,
        )
        if overclaim is not None and overclaim.value == "high":
            expected_risks.append(
                (
                    "overclaim_signal",
                    "recorded_overclaim_signal",
                    [overclaim.evidence_id],
                )
            )
        actual_risks = [
            (item.category, item.statement_key, item.evidence_refs)
            for item in candidate_facts.risks
        ]
        if actual_risks != expected_risks:
            raise ValueError("risk semantics do not match historical evidence")
        for item in candidate_facts.missing_requirements:
            if item.candidate_id != candidate_facts.candidate_id or item.result_rank != candidate_facts.result_rank:
                raise ValueError("missing requirement fact owner does not match Candidate fact set")
            validate_fact_references(
                bundle,
                candidate_id=candidate_facts.candidate_id,
                result_rank=candidate_facts.result_rank,
                evidence_refs=item.evidence_refs,
                allowed_kinds={"job_requirement"},
            )
        if candidate_facts.missing_requirements != expected_requirements:
            raise ValueError(
                "missing requirement semantics do not match historical diagnostics"
            )
        comparison = candidate_facts.comparison
        expected_comparison = comparisons_by_candidate[
            (candidate_facts.candidate_id, candidate_facts.result_rank)
        ]
        if comparison != expected_comparison:
            raise ValueError(
                "top-1 comparison semantics do not match historical evidence"
            )
        if comparison is None:
            if candidate_facts.result_rank != 1:
                raise ValueError("non-top-one Candidate requires top-1 comparison facts")
            continue
        if (
            comparison.candidate_id != candidate_facts.candidate_id
            or comparison.result_rank != candidate_facts.result_rank
            or comparison.top1_candidate_id != bundle.candidates[0].candidate_id
        ):
            raise ValueError("top-1 comparison owner does not match Evidence Bundle")
        for item in comparison.comparisons:
            if item.dimension == "retrieval_rank":
                kinds = {"retrieval"}
                names = {"retrieval_rank"}
            elif item.dimension == "requirement_evidence_coverage":
                kinds = {"diagnostic"}
                names = {"evidence_supported_requirement_ids"}
            else:
                kinds = {"comparison"}
                names = {item.dimension}
            validate_fact_references(
                bundle,
                candidate_id=candidate_facts.candidate_id,
                result_rank=candidate_facts.result_rank,
                evidence_refs=item.evidence_refs,
                allowed_kinds=kinds,
                allowed_names=names,
            )


__all__ = ["validate_evidence_facts", "validate_fact_references"]
