"""Integrity checks for the frozen, manually adjudicated recovered experiment."""

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path


FIXTURES = Path(__file__).parent / "fixtures"
RUN = FIXTURES / "recruiter_proposition_phase2_semantic_intent_recovered_20261007T0858Z.jsonl"
GOLD = FIXTURES / "recruiter_proposition_phase2_semantic_intent_recovered_gold_v1.json"
FIELDS = ("decision_summary", "why_consider", "technical_signal", "interview_focus", "uncertainty")


def test_recovered_manual_gold_has_exact_source_and_complete_field_coverage():
    gold = json.loads(GOLD.read_text(encoding="utf-8"))
    records = [json.loads(line) for line in RUN.read_text(encoding="utf-8").splitlines()]
    manifest, *cases = records
    assert sha256(RUN.read_bytes()).hexdigest().upper() == gold["source_artifact_sha256"]
    assert manifest["experiment"] == gold["source_experiment"]
    assert manifest["previous_batch"] == "BLOCKED_BY_TRANSPORT"
    assert len(cases) == len(gold["cases"]) == 8
    assert [case["scenario_id"] for case in cases] == [case["scenario_id"] for case in gold["cases"]]
    assert all(case["schema"] == case["handle"] == "PASS" and case["repair"] == 0 for case in cases)
    assert [case["split"] for case in cases] == [case["split"] for case in gold["cases"]]

    labels = Counter()
    for case, review in zip(cases, gold["cases"]):
        narrative = case["narrative"]
        addresses = set()
        for item in review["items"]:
            field, index = item["field"], item["index"]
            assert field in FIELDS
            paragraph = (narrative[field] if field == "decision_summary"
                         else narrative[field][index])
            assert paragraph["text"].count(item["quote"]) == 1
            assert item["adjudication"] in {"supported", "unsupported", "uncertain"}
            if item["adjudication"] != "supported":
                assert item["issue"]
            labels[item["adjudication"]] += 1
            addresses.add((field, index))
        expected = {("decision_summary", 0)} | {
            (field, index) for field in FIELDS[1:] for index, _ in enumerate(narrative[field])
        }
        assert addresses == expected
    assert labels == {"supported": 46, "unsupported": 3, "uncertain": 2}
