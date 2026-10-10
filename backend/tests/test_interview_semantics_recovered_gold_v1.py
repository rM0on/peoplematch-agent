"""Integrity of independent human labels for the resumed eight-case batch."""

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path


FIXTURES = Path(__file__).parent / "fixtures"
RUN = FIXTURES / "interview_semantics_phase2_recovered_20261007T1542Z.jsonl"
GOLD = FIXTURES / "interview_semantics_phase2_recovered_20261007T1542Z_gold_v1.json"
FIELDS = {"decision_summary", "why_consider", "technical_signal", "interview_focus", "uncertainty"}


def test_recovered_gold_matches_exact_immutable_provider_batch() -> None:
    data = json.loads(GOLD.read_text(encoding="utf-8"))
    raw = RUN.read_bytes()
    assert data["source_artifact_sha256"].lower() == sha256(raw).hexdigest()
    records = [json.loads(line) for line in raw.decode("utf-8").splitlines()]
    cases = {record["scenario_id"]: record for record in records if record["record_type"] == "case"}
    assert len(cases) == len(data["cases"]) == 8
    assert len({case["scenario_id"] for case in data["cases"]}) == 8
    counts = Counter()
    for case in data["cases"]:
        source = cases[case["scenario_id"]]
        assert case["split"] == source["split"]
        assert {item["field"] for item in case["items"]} == FIELDS
        for item in case["items"]:
            field, index = item["field"], item["index"]
            text = (source["narrative"][field]["text"] if field == "decision_summary"
                    else source["narrative"][field][index]["text"])
            assert item["quote"] and item["quote"] in text
            assert item["adjudication"] in {"supported", "unsupported", "uncertain"}
            assert item["category"] and item["rationale"]
            counts[item["adjudication"]] += 1
    assert sum(counts.values()) >= 60
    assert counts["unsupported"] >= 1
