"""Reproducible, offline-only evaluation of historical synthetic Narrative audits.

This module never calls a Provider. Gold labels are human adjudications, not
model-selected proposition handles. Original blind atoms are archived separately
from the gold and replayed through the unmodified deterministic auditor.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path

from app.services.explanation.presentation.contracts_proposition_v1 import RecruiterPropositionSetV1
from app.services.explanation.presentation.generation_proposition_v1 import (
    FIELDS, ResolvedPropositionNarrativeV1, build_proposition_binding_v1,
)
from app.services.explanation.presentation.facts_v2 import build_atomic_facts
from app.services.explanation.presentation.facts_v3 import build_atomic_fact_graph_v3
from app.services.explanation.presentation.claims_v4 import build_recruiter_claim_graph_v4
from app.services.explanation.presentation.propositions_v1 import build_recruiter_propositions_v1
from app.services.explanation.presentation.semantic_audit_proposition_v1 import (
    BlindNarrativeAuditOutputV1, evaluate_blind_semantic_audit_v1,
)
from narrative_v2_comparison_fixture import build_comparison_group


FIXTURES = Path(__file__).parent / "fixtures"
GOLD = FIXTURES / "recruiter_proposition_phase2_semantic_gold_v1.json"
HISTORICAL = FIXTURES / "recruiter_proposition_phase2_historical_predictions_v1.json"
PROVENANCE = FIXTURES / "recruiter_proposition_phase2_provenance_v1.json"

AUDIT_CATEGORY_BY_GOLD = {
    "material_technology_fact": "project_technology",
    "listed_skill_fact": "listed_skill",
    "job_alignment": "job_alignment",
    "human_review_recommendation": "human_review_action",
    "material_unknown": "material_unknown",
    "interview_target": "interview_target",
    "alignment_to_experience": "candidate_experience_or_ability",
    "alignment_to_capability": "candidate_experience_or_ability",
    "project_technology_to_candidate_action": "candidate_action_or_responsibility",
    # The blind extractor contract has no dedicated project-use upgrade kind.
    # Keep this gold distinction; exclude it from category accuracy only.
    "project_technology_to_project_use": None,
    "project_technology_to_candidate_experience": "candidate_experience_or_ability",
    "weak_overlap_to_strong_match": "strong_alignment",
    "alignment_strength_upgrade": "strong_alignment",
    "unsupported_responsibility": "candidate_action_or_responsibility",
    "unsupported_scale": "scale_or_outcome",
    "unsupported_outcome": "scale_or_outcome",
    "unsupported_familiarity_proficiency": "candidate_experience_or_ability",
}

# Topic-extraction, quote coverage and schema errors are useful diagnostics,
# but are not themselves evidence that the generated prose added a false fact.
UNSUPPORTED_ISSUE_CODES = frozenset({
    "UNSUPPORTED_SEMANTIC_CATEGORY", "NO_SUPPORTING_PROPOSITION",
    "REVIEW_STRENGTH_EXCEEDS_SUPPORT", "TOPIC_OUTSIDE_PROPOSITION_SCOPE",
})


def load_semantic_gold_v1() -> tuple[dict, dict, dict]:
    return tuple(json.loads(path.read_text(encoding="utf-8"))
                 for path in (GOLD, HISTORICAL, PROVENANCE))


def _paragraph_text(narrative: dict, field: str, index: int) -> str:
    value = narrative[field]
    if field == "decision_summary":
        if index != 0:
            raise ValueError("invalid_gold_paragraph_index")
        return value
    try:
        return value[index]
    except (IndexError, TypeError) as error:
        raise ValueError("invalid_gold_paragraph_index") from error


def _historical_narrative(case: dict) -> dict:
    narrative = case["narrative"]
    return {field: narrative[field]["text"] if field == "decision_summary"
            else [item["text"] for item in narrative[field]] for field in FIELDS}


def _validate_case(gold: dict, historical: dict, provenance: dict) -> None:
    if not (gold["scenario_id"] == historical["scenario_id"] == provenance["scenario_id"]):
        raise ValueError("scenario_identity_mismatch")
    if not (gold["candidate_id"] == historical["candidate_id"] == provenance["candidate_id"]
            and gold["result_rank"] == historical["narrative"]["result_rank"]
            == provenance["result_rank"]):
        raise ValueError("candidate_identity_mismatch")
    if gold["narrative"] != _historical_narrative(historical):
        raise ValueError("historical_narrative_mismatch")
    if set(gold["narrative"]) != set(FIELDS):
        raise ValueError("narrative_field_mismatch")
    if not historical["semantic_atoms"]:
        raise ValueError("historical_blind_atoms_missing")
    valid_categories = set(AUDIT_CATEGORY_BY_GOLD)
    valid_labels = {"supported", "unsupported", "uncertain"}
    gold_addresses = set()
    for item in gold["gold"]:
        text = _paragraph_text(gold["narrative"], item["field"], item["index"])
        if text.count(item["quote"]) != 1:
            raise ValueError("gold_quote_not_unique_in_paragraph")
        if item["category"] not in valid_categories or item["adjudication"] not in valid_labels:
            raise ValueError("gold_label_invalid")
        if item["adjudication"] == "unsupported" and "issue" not in item:
            raise ValueError("unsupported_gold_issue_missing")
        gold_addresses.add((item["field"], item["index"]))
    expected_addresses = {("decision_summary", 0)} | {
        (field, index) for field in FIELDS[1:]
        for index, _ in enumerate(gold["narrative"][field])
    }
    if gold_addresses != expected_addresses:
        raise ValueError("gold_paragraph_coverage_incomplete")
    for row in historical["semantic_atoms"]:
        text = _paragraph_text(gold["narrative"], row["field"], row["item_index"])
        for atom in row["atoms"]:
            if atom["quote"] not in text:
                raise ValueError("historical_atom_quote_not_in_narrative")

    group = build_comparison_group(gold["group"])
    if group["role"] != gold["role"] or provenance["ranking_snapshot"] != group["ranking_before"]:
        raise ValueError("canonical_fixture_changed")
    projection = group["projections"][0 if gold["candidate_label"] == "A" else 1]
    rebuilt = build_recruiter_propositions_v1(projection)
    if rebuilt.candidate_id != gold["candidate_id"] or rebuilt.result_rank != gold["result_rank"]:
        raise ValueError("candidate_identity_mismatch")
    if [item.model_dump(mode="json") for item in rebuilt.propositions] != provenance["propositions"]:
        raise ValueError("proposition_provenance_changed")
    source_ids = {fact_id for item in rebuilt.propositions for fact_id in item.source_fact_ids}
    if (json.loads(json.dumps([asdict(fact) for fact in build_atomic_facts(projection)
                               if fact.fact_id in source_ids]))
            != provenance["source_facts_v2"]
            or json.loads(json.dumps([asdict(fact) for fact in build_atomic_fact_graph_v3(projection).facts
                                      if fact.fact_id in source_ids])) != provenance["source_facts_v3"]):
        raise ValueError("source_fact_provenance_changed")
    claim_ids = {claim_id for item in rebuilt.propositions for claim_id in item.source_claim_ids}
    v3_graph = build_atomic_fact_graph_v3(projection)
    if ([claim.model_dump(mode="json") for claim in build_recruiter_claim_graph_v4(v3_graph).claims
         if claim.claim_id in claim_ids] != provenance["source_claims_v4"]):
        raise ValueError("source_claim_provenance_changed")
    source_refs = {ref for item in rebuilt.propositions
                   for ref in (*item.evidence_refs, *item.job_requirement_refs)}
    if ({ref: list(projection.facts[ref]) for ref in sorted(source_refs) if ref in projection.facts}
            != provenance["source_evidence_terms"]):
        raise ValueError("source_evidence_provenance_changed")
    binding = build_proposition_binding_v1(rebuilt)
    narrative = ResolvedPropositionNarrativeV1.model_validate(historical["narrative"])
    if narrative.candidate_id != rebuilt.candidate_id or narrative.result_rank != rebuilt.result_rank:
        raise ValueError("candidate_identity_mismatch")
    for field in FIELDS:
        paragraphs = [narrative.decision_summary] if field == "decision_summary" else getattr(narrative, field)
        selected = historical["selected_handles"][field]
        if len(paragraphs) != len(selected):
            raise ValueError("historical_handle_count_mismatch")
        for paragraph, handles in zip(paragraphs, selected):
            if paragraph.proposition_refs != binding.resolve(handles, field=field):
                raise ValueError("historical_handle_resolution_mismatch")


def validate_semantic_gold_v1(gold: dict, historical: dict, provenance: dict) -> None:
    if not (len(gold["cases"]) == len(historical["cases"]) == len(provenance["cases"]) == 6):
        raise ValueError("six_case_fixture_required")
    ids = [case["scenario_id"] for case in gold["cases"]]
    if len(set(ids)) != 6 or set(ids) != {case["scenario_id"] for case in historical["cases"]}:
        raise ValueError("scenario_identity_mismatch")
    for a, b, c in zip(gold["cases"], historical["cases"], provenance["cases"]):
        _validate_case(a, b, c)


def _span(text: str, quote: str) -> tuple[int, int] | None:
    start = text.find(quote)
    return None if start < 0 else (start, start + len(quote))


def _overlap_fraction(text: str, gold_quote: str, predicted_quote: str) -> float:
    gold_span = _span(text, gold_quote)
    predicted_span = _span(text, predicted_quote)
    if gold_span is None or predicted_span is None:
        return 0.0
    return max(0, min(gold_span[1], predicted_span[1]) - max(gold_span[0], predicted_span[0])) / len(gold_quote)


def _ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def evaluate_historical_semantic_audit_v1(gold: dict, historical: dict, provenance: dict) -> dict:
    """Compare archived blind atoms against independently adjudicated gold.

    Matching is paragraph-local and requires >=50% of a gold item's characters
    in an extracted quote. Uncertain gold labels are excluded from binary rates.
    Missing coverage diagnostics without a quote are reported separately.
    """
    validate_semantic_gold_v1(gold, historical, provenance)
    totals = Counter()
    issue_codes = Counter()
    unsupported_categories = Counter()
    false_positives = []
    false_negatives = []
    category_errors = []
    per_case = []
    replay_matches = 0
    for gold_case, record, source in zip(gold["cases"], historical["cases"], provenance["cases"]):
        narrative = ResolvedPropositionNarrativeV1.model_validate(record["narrative"])
        propositions = RecruiterPropositionSetV1.model_validate({
            "contract_version": "recruiter_proposition_v1",
            "candidate_id": source["candidate_id"], "result_rank": source["result_rank"],
            "propositions": source["propositions"],
        })
        audit = BlindNarrativeAuditOutputV1.model_validate({
            "contract_version": "blind_narrative_semantics_v1",
            "candidate_id": record["candidate_id"], "result_rank": narrative.result_rank,
            "paragraphs": record["semantic_atoms"],
        })
        result = evaluate_blind_semantic_audit_v1(audit, narrative=narrative, propositions=propositions)
        replayed = [{"field": x.field, "item_index": x.item_index, "code": x.code, "quote": x.quote}
                    for x in result.issues]
        if replayed == record["semantic_audit_issues"]:
            replay_matches += 1
        else:
            raise ValueError("historical_auditor_replay_mismatch")
        totals["atoms"] += result.atom_count
        totals["historical_pass"] += int(result.passed)
        atoms_by_address = {(row.field, row.item_index): row.atoms for row in audit.paragraphs}
        issues_by_address = {}
        for issue in result.issues:
            issue_codes[issue.code] += 1
            issues_by_address.setdefault((issue.field, issue.item_index), []).append(issue)
            if not issue.quote:
                totals["unattributed_issue"] += 1
        case_counts = Counter()
        for item in gold_case["gold"]:
            address = item["field"], item["index"]
            text = _paragraph_text(gold_case["narrative"], *address)
            matches = [(atom, _overlap_fraction(text, item["quote"], atom.quote))
                       for atom in atoms_by_address.get(address, ())]
            matches = [(atom, fraction) for atom, fraction in matches if fraction >= 0.5]
            detected = bool(matches)
            flagged = any(issue.code in UNSUPPORTED_ISSUE_CODES and issue.quote
                          and _overlap_fraction(text, item["quote"], issue.quote) >= 0.5
                          for issue in issues_by_address.get(address, ()))
            if item["adjudication"] == "uncertain":
                totals["uncertain_gold"] += 1
                totals["uncertain_alert"] += flagged
                continue
            totals["gold_definitive"] += 1
            totals["detected"] += detected
            gold_span = _span(text, item["quote"])
            covered_positions = set()
            for atom in atoms_by_address.get(address, ()):
                predicted_span = _span(text, atom.quote)
                if predicted_span is not None:
                    covered_positions.update(range(max(gold_span[0], predicted_span[0]),
                                                   min(gold_span[1], predicted_span[1])))
            totals["gold_span_characters"] += len(item["quote"])
            totals["covered_span_characters"] += len(covered_positions)
            totals["exact_quote"] += any(atom.quote == item["quote"]
                                         for atom in atoms_by_address.get(address, ()))
            case_counts["gold_definitive"] += 1
            case_counts["detected"] += detected
            if detected:
                best = max(matches, key=lambda pair: pair[1])[0]
                expected_category = AUDIT_CATEGORY_BY_GOLD[item["category"]]
                if expected_category is None:
                    totals["category_not_comparable"] += 1
                else:
                    totals["category_matched"] += 1
                    if best.category == expected_category:
                        totals["category_correct"] += 1
                    else:
                        category_errors.append({"scenario_id": gold_case["scenario_id"],
                                                "field": item["field"], "index": item["index"],
                                                "quote": item["quote"], "expected": expected_category,
                                                "actual": best.category})
            if item["adjudication"] == "unsupported":
                totals["gold_unsupported"] += 1
                unsupported_categories[item["category"]] += 1
                case_counts["gold_unsupported"] += 1
                if flagged:
                    totals["true_positive"] += 1
                    case_counts["true_positive"] += 1
                else:
                    totals["false_negative"] += 1
                    false_negatives.append({"scenario_id": gold_case["scenario_id"],
                                            "field": item["field"], "index": item["index"],
                                            "quote": item["quote"], "category": item["category"],
                                            "extracted": detected})
            elif flagged:
                totals["false_positive"] += 1
                false_positives.append({"scenario_id": gold_case["scenario_id"],
                                        "field": item["field"], "index": item["index"],
                                        "quote": item["quote"], "category": item["category"]})
        per_case.append({"scenario_id": gold_case["scenario_id"], **case_counts})
    return {
        "sample_count": 6, "historical_audit_pass_count": totals["historical_pass"],
        "replayed_issue_match_count": replay_matches, "auditor_atom_count": totals["atoms"],
        "gold_item_count": totals["gold_definitive"] + totals["uncertain_gold"],
        "uncertain_gold_count": totals["uncertain_gold"],
        "semantic_item_detection": {"numerator": totals["detected"],
                                    "denominator": totals["gold_definitive"],
                                    "recall": _ratio(totals["detected"], totals["gold_definitive"]),
                                    "exact_quote_matches": totals["exact_quote"],
                                    "character_coverage_recall": _ratio(
                                        totals["covered_span_characters"], totals["gold_span_characters"])},
        "unsupported_detection": {
            "true_positive": totals["true_positive"], "false_positive": totals["false_positive"],
            "false_negative": totals["false_negative"],
            "gold_unsupported": totals["gold_unsupported"],
            "precision": _ratio(totals["true_positive"], totals["true_positive"] + totals["false_positive"]),
            "recall": _ratio(totals["true_positive"], totals["gold_unsupported"]),
        },
        "category_accuracy": {"numerator": totals["category_correct"],
                              "denominator": totals["category_matched"],
                              "accuracy": _ratio(totals["category_correct"], totals["category_matched"]),
                              "not_comparable": totals["category_not_comparable"]},
        "unattributed_issue_count": totals["unattributed_issue"],
        "uncertain_gold_alert_count": totals["uncertain_alert"],
        "issue_code_counts": dict(sorted(issue_codes.items())),
        "unsupported_gold_categories": dict(sorted(unsupported_categories.items())),
        "false_positives": false_positives, "false_negatives": false_negatives,
        "category_errors": category_errors, "per_case": per_case,
        "matching_rule": "same paragraph; extracted/flagged quote covers >=50% of gold item characters",
    }


if __name__ == "__main__":
    print(json.dumps(evaluate_historical_semantic_audit_v1(*load_semantic_gold_v1()),
                     ensure_ascii=False, indent=2))
