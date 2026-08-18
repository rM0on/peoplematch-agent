from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
import sys
from typing import Any, Sequence
import unicodedata


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.ranking.metrics import (  # noqa: E402
    ndcg_at_k,
    pairwise_accuracy,
    reciprocal_rank,
)
from app.core.config import Settings  # noqa: E402
from app.schemas.candidate import CandidateProfile  # noqa: E402
from app.schemas.features import FeatureVector  # noqa: E402
from app.schemas.job import JobProfile  # noqa: E402
from app.services.cross_encoder.model import load_cross_encoder_model  # noqa: E402
from app.services.cross_encoder.text import (  # noqa: E402
    build_candidate_text,
    build_job_text,
    build_pair_text,
)
from app.services.dataset_validation import load_pairwise_preferences  # noqa: E402
from app.services.ranking.model import load_ranking_model  # noqa: E402
from app.services.features.contract import MODEL_FEATURE_ORDER  # noqa: E402


TEST_JOB_IDS = frozenset({"job_020", "job_021", "job_022", "job_023", "job_024"})


def _preference_parts(preference: Any) -> tuple[str, str, str]:
    if isinstance(preference, tuple):
        return preference
    return (
        str(preference.job_id),
        str(preference.winner_candidate_id),
        str(preference.loser_candidate_id),
    )


def _aggregate(rows: Sequence[dict[str, Any]]) -> dict[str, float]:
    keys = ("ndcg_at_5", "ndcg_at_10", "mrr", "pairwise_accuracy")
    if not rows:
        return {key: 0.0 for key in keys}
    return {
        key: sum(float(row[key]) for row in rows) / len(rows)
        for key in keys
    }


def _percentile(values: Sequence[int], percentile: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile / 100
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _token_length_summary(lengths: Sequence[int], max_length: int) -> dict[str, Any]:
    over = sum(length > max_length for length in lengths)
    return {
        "min": min(lengths),
        "median": _percentile(lengths, 50),
        "p95": _percentile(lengths, 95),
        "max": max(lengths),
        "over_max_count": over,
        "over_max_percentage": 100.0 * over / len(lengths),
    }


def _ordered_indices(
    rows: Sequence[dict[str, Any]],
    *,
    scores: Sequence[float],
    tie_ranks: dict[int, int] | None = None,
) -> list[int]:
    """Order rows by score, then deterministic upstream rank fallbacks."""
    return sorted(
        range(len(rows)),
        key=lambda index: (
            -float(scores[index]),
            int(tie_ranks[index]) if tie_ranks is not None else index + 1,
            index,
            str(rows[index]["candidate_id"]),
        ),
    )


def build_evaluation_report(
    *,
    query_ids: Sequence[str],
    judged_rows: Sequence[dict[str, Any]],
    ltr_scores: Sequence[float],
    ce_scores: Sequence[float],
    pairwise_preferences: Sequence[Any],
    model_metadata: dict[str, Any],
) -> dict[str, Any]:
    if set(query_ids) & TEST_JOB_IDS:
        raise ValueError("Test queries are forbidden in Phase 7 evaluation")
    if len(judged_rows) != len(ltr_scores) or len(judged_rows) != len(ce_scores):
        raise ValueError("Judged rows and score arrays must have identical length")
    if any(str(row.get("job_id")) not in set(query_ids) for row in judged_rows):
        raise ValueError("Every judged row must belong to an approved Dev query")

    rows_by_job: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    for index, row in enumerate(judged_rows):
        rows_by_job[str(row["job_id"])].append((index, row))
    preferences_by_job: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for preference in pairwise_preferences:
        job_id, winner, loser = _preference_parts(preference)
        if job_id in query_ids:
            preferences_by_job[job_id].append((winner, loser))

    per_query = {"ltr": [], "cross_encoder": []}
    for job_id in query_ids:
        indexed_rows = rows_by_job[job_id]
        preferences = preferences_by_job[job_id]
        ltr_order = _ordered_indices(
            [row for _, row in indexed_rows],
            scores=[ltr_scores[index] for index, _ in indexed_rows],
        )
        ltr_rank_by_local_index = {
            indexed_rows[local_index][0]: rank
            for rank, local_index in enumerate(ltr_order, start=1)
        }
        for name, scores in (("ltr", ltr_scores), ("cross_encoder", ce_scores)):
            local_scores = [scores[index] for index, _ in indexed_rows]
            local_tie_ranks = (
                {local_index: ltr_rank_by_local_index[indexed_rows[local_index][0]] for local_index in range(len(indexed_rows))}
                if name == "cross_encoder"
                else None
            )
            ordered_local_indices = _ordered_indices(
                [row for _, row in indexed_rows],
                scores=local_scores,
                tie_ranks=local_tie_ranks,
            )
            ordered = [indexed_rows[local_index] for local_index in ordered_local_indices]
            ordered_grades = [int(row["relevance_grade"]) for _, row in ordered]
            score_map = {
                str(row["candidate_id"]): float(scores[index])
                for index, row in indexed_rows
            }
            per_query[name].append(
                {
                    "job_id": job_id,
                    "judged_candidate_ids": [
                        str(row["candidate_id"]) for _, row in indexed_rows
                    ],
                    "ndcg_at_5": ndcg_at_k(ordered_grades, 5),
                    "ndcg_at_10": ndcg_at_k(ordered_grades, 10),
                    "mrr": reciprocal_rank(ordered_grades, relevance_threshold=2),
                    "pairwise_accuracy": pairwise_accuracy(score_map, preferences),
                }
            )

    return {
        "artifact_version": "cross_encoder_dev_report_v1",
        "title": "CROSS-ENCODER JUDGED-SET DEV RERANKING EVALUATION",
        "evaluation_scope": "cross_encoder_judged_set_dev_reranking",
        "candidate_set_policy": "identical_judged_candidates_for_ltr_and_cross_encoder",
        "incomplete_judgments": True,
        "test_evaluated": False,
        "gain_policy": "2^relevance_minus_1",
        "relevance_threshold": 2,
        "tie_policy": "0.5",
        "query_ids": list(query_ids),
        "judged_row_count": len(judged_rows),
        "model": dict(model_metadata),
        "score_semantics": {
            "field": "cross_encoder_score_raw",
            "type": "raw_logit",
            "direction": "higher_is_better",
            "calibrated": False,
        },
        "per_query": per_query,
        "metrics": {
            "ltr": _aggregate(per_query["ltr"]),
            "cross_encoder": _aggregate(per_query["cross_encoder"]),
        },
        "disclosures": {
            "ceiling_effect": "Phase 6 Dev MRR and pairwise accuracy are already 1.0; only NDCG@5 and NDCG@10 have aggregate headroom.",
            "domain_mismatch": "The frozen model was trained for MS MARCO passage ranking, not Job/Candidate matching, and was not fine-tuned here.",
            "scope": "This isolates ordering over identical explicitly judged Dev pairs; it is not full-cascade or production hiring accuracy.",
        },
    }


def _read_profiles_for_dev(
    *, query_ids: set[str], candidate_ids: set[str]
) -> tuple[dict[str, JobProfile], dict[str, CandidateProfile]]:
    jobs: dict[str, JobProfile] = {}
    with (ROOT / "data/samples/jobs.jsonl").open(encoding="utf-8") as stream:
        for raw_line in stream:
            payload = json.loads(raw_line)
            job_id = str(payload.get("job_id"))
            if job_id in query_ids:
                jobs[job_id] = JobProfile.model_validate(payload)
    candidates: dict[str, CandidateProfile] = {}
    with (ROOT / "data/samples/candidates.jsonl").open(encoding="utf-8") as stream:
        for raw_line in stream:
            payload = json.loads(raw_line)
            candidate_id = str(payload.get("candidate_id"))
            if candidate_id in candidate_ids:
                candidates[candidate_id] = CandidateProfile.model_validate(payload)
    if jobs.keys() != query_ids or candidates.keys() != candidate_ids:
        raise ValueError("Dev profile set is incomplete")
    return jobs, candidates


def _load_dev_inputs() -> tuple[list[str], list[dict[str, Any]], list[Any]]:
    artifact = json.loads((ROOT / "data/eval/phase6/ltr_dataset_v1.json").read_text(encoding="utf-8"))
    rows = list(artifact["splits"]["dev"]["rows"])
    query_ids = list(artifact["splits"]["dev"]["query_ids"])
    if set(query_ids) & TEST_JOB_IDS or len(query_ids) != 5 or len(rows) != 60:
        raise ValueError("Phase 7 requires exactly the five sealed Dev jobs and 60 rows")
    if any(row.get("split") != "dev" for row in rows):
        raise ValueError("Phase 7 Dev artifact contains a non-Dev row")
    return query_ids, rows, load_pairwise_preferences(ROOT, query_ids)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate the pinned Phase 7 Cross-Encoder on Dev judged pairs")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    settings = Settings(_env_file=None)
    query_ids, rows, preferences = _load_dev_inputs()
    jobs, candidates = _read_profiles_for_dev(
        query_ids=set(query_ids),
        candidate_ids={str(row["candidate_id"]) for row in rows},
    )
    ranking_model = load_ranking_model(
        model_path=ROOT / "artifacts/phase6/ltr_ranker_v1.txt",
        metadata_path=ROOT / "data/eval/phase6/ltr_model_metadata_v1.json",
    )
    feature_vectors = [
        FeatureVector.model_validate(
            dict(zip(MODEL_FEATURE_ORDER, row["feature_vector"]))
        )
        for row in rows
    ]
    ltr_scores = ranking_model.predict(feature_vectors).tolist()
    runtime = load_cross_encoder_model(
        model_path=Path(settings.cross_encoder_model_path),
        manifest_path=Path(settings.cross_encoder_model_manifest_path),
        text_contract_path=Path(settings.cross_encoder_text_contract_path),
    )
    pairs = []
    for row in rows:
        pair = build_pair_text(jobs[str(row["job_id"])], candidates[str(row["candidate_id"])])
        pairs.append((pair.text_a, pair.text_b))
    ce_scores = runtime.predict_pairs(pairs, batch_size=settings.cross_encoder_batch_size).tolist()
    if len(set(float(value) for value in ce_scores)) <= 1:
        raise ValueError("PHASE 7 BLOCKED — DEGENERATE CROSS-ENCODER: Dev scores are globally constant")
    for job_id in query_ids:
        query_scores = [
            ce_scores[index]
            for index, row in enumerate(rows)
            if str(row["job_id"]) == job_id
        ]
        if len(set(float(value) for value in query_scores)) <= 1:
            raise ValueError(
                f"PHASE 7 BLOCKED — DEGENERATE CROSS-ENCODER: scores are constant for {job_id}"
            )
    report = build_evaluation_report(
        query_ids=query_ids,
        judged_rows=rows,
        ltr_scores=ltr_scores,
        ce_scores=ce_scores,
        pairwise_preferences=preferences,
        model_metadata={
            "model_id": runtime.model_id,
            "revision": runtime.revision,
            "snapshot_fingerprint": runtime.snapshot_fingerprint,
            "text_schema_version": runtime.manifest["text_schema_version"],
            "text_contract_fingerprint": runtime.manifest["text_contract_fingerprint"],
        },
    )
    train_artifact = json.loads((ROOT / "data/eval/phase6/ltr_dataset_v1.json").read_text(encoding="utf-8"))
    train_rows = list(train_artifact["splits"]["train"]["rows"])
    train_jobs, train_candidates = _read_profiles_for_dev(
        query_ids=set(train_artifact["splits"]["train"]["query_ids"]),
        candidate_ids={str(row["candidate_id"]) for row in train_rows},
    )
    train_pairs = [
        build_pair_text(train_jobs[str(row["job_id"])], train_candidates[str(row["candidate_id"])])
        for row in train_rows
    ]
    train_scores = runtime.predict_pairs(
        [(pair.text_a, pair.text_b) for pair in train_pairs],
        batch_size=settings.cross_encoder_batch_size,
    )
    if len(set(float(value) for value in train_scores.tolist())) <= 1:
        raise ValueError(
            "PHASE 7 BLOCKED — DEGENERATE CROSS-ENCODER: Train scores are globally constant"
        )
    report["model_sanity"] = {
        "train_scores_finite": all(math.isfinite(float(value)) for value in train_scores.tolist()),
        "dev_scores_finite": all(math.isfinite(float(value)) for value in ce_scores),
        "train_scores_nonconstant": len(set(float(value) for value in train_scores.tolist())) > 1,
        "dev_scores_nonconstant": len(set(float(value) for value in ce_scores)) > 1,
        "dev_query_score_variation": {
            job_id: len(
                {
                    float(ce_scores[index])
                    for index, row in enumerate(rows)
                    if str(row["job_id"]) == job_id
                }
            ) > 1
            for job_id in query_ids
        },
    }
    all_pairs = train_pairs + [
        build_pair_text(jobs[str(row["job_id"])], candidates[str(row["candidate_id"])])
        for row in rows
    ]
    lengths = [
        len(
            runtime.tokenizer(
                pair.text_a,
                pair.text_b,
                truncation=False,
                add_special_tokens=True,
            )["input_ids"]
        )
        for pair in all_pairs
    ]
    report["tokenizer_audit"] = {
        "tokenizer_class": runtime.tokenizer.__class__.__name__,
        "max_length": runtime.max_length,
        "truncation_policy": "normal_deterministic_single_pair_truncation_if_needed",
        "train": _token_length_summary(lengths[: len(train_pairs)], runtime.max_length),
        "dev": _token_length_summary(lengths[len(train_pairs) :], runtime.max_length),
    }
    semantic_texts = [
        *(build_job_text(job) for job in [*train_jobs.values(), *jobs.values()]),
        *(build_candidate_text(candidate) for candidate in {**train_candidates, **candidates}.values()),
    ]
    letters = [character for text in semantic_texts for character in text if character.isalpha()]
    latin_letters = [
        character
        for character in letters
        if "LATIN" in unicodedata.name(character, "")
    ]
    report["language_audit"] = {
        "scope": "Train/Dev allowlisted semantic text only",
        "job_count": len(train_jobs) + len(jobs),
        "candidate_count": len({**train_candidates, **candidates}),
        "latin_script_letter_percentage": 100.0 * len(latin_letters) / len(letters),
        "non_ascii_character_count": sum(
            ord(character) > 127 for text in semantic_texts for character in text
        ),
        "model_language_compatible": True,
        "test_inspected": False,
    }
    print(json.dumps(report["metrics"], sort_keys=True))
    if args.write:
        output = ROOT / "data/eval/phase7/cross_encoder_dev_report_v1.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
