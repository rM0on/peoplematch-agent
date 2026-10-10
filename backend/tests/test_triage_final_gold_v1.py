"""Offline integrity check for the immutable final Phase 2 manual gold."""

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path


FIXTURES = Path(__file__).parent / "fixtures"
EXPERIMENT = FIXTURES / "triage_phase2_final_20261008T0859Z.jsonl"
GOLD = FIXTURES / "triage_phase2_final_20261008T0859Z_gold_v1.json"
FIELDS = {"decision_summary", "why_consider", "technical_signal", "interview_focus", "uncertainty"}


def test_final_gold_is_anchored_to_exact_artifact_and_every_field():
    gold = json.loads(GOLD.read_text(encoding="utf-8"))
    assert gold["source_artifact_sha256"].casefold() == sha256(EXPERIMENT.read_bytes()).hexdigest()
    records = [json.loads(line) for line in EXPERIMENT.read_text(encoding="utf-8").splitlines()]
    results = {row["scenario_id"]: row for row in records if row["record_type"] == "case_result"}
    assert len(results) == len(gold["cases"]) == 8
    assert len({case["scenario_id"] for case in gold["cases"]}) == 8
    labels = Counter()
    for case in gold["cases"]:
        narrative = results[case["scenario_id"]]["narrative"]
        assert {item["field"] for item in case["items"]} == FIELDS
        assert case["recommendation_strength_compliant"] in {True, False}
        assert case["first_check_compliant"] in {True, False}
        for item in case["items"]:
            paragraphs = ([narrative["decision_summary"]] if item["field"] == "decision_summary"
                          else narrative[item["field"]])
            assert item["quote"] in paragraphs[item["index"]]["text"]
            assert item["adjudication"] in {"supported", "unsupported", "uncertain"}
            assert item["category"]
            labels[item["adjudication"]] += 1
    assert labels == {"supported": 32, "unsupported": 9, "uncertain": 4}
