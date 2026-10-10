"""Frozen experiment replay must compare JSON semantics, not Python containers."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

import narrative_interview_semantics_v1_live_experiment as experiment
from app.services.llm.configuration import ProviderMode


class _NoCallProvider:
    async def aclose(self) -> None:
        return None


def _manifest() -> dict:
    return {
        "experiment_id": "canonical_test",
        "model": "qwen3.7-flash-2026-07-15",
        "source_sha256": {"runner": "implementation_hash"},
        "cases": (
            {"sample_id": "first", "requirements": ("Python", "RAG"),
             "projection_sha256": "fixture_hash", "request_sha256": "request_hash"},
            {"sample_id": "second", "requirements": ("Python", "Kafka"),
             "projection_sha256": "second_fixture", "request_sha256": "second_request"},
        ),
    }


def _replay(tmp_path, monkeypatch, current: dict) -> tuple[int, bool]:
    frozen = _manifest()
    (tmp_path / "canonical_test.manifest.json").write_text(
        json.dumps(frozen), encoding="utf-8")
    monkeypatch.setattr(experiment, "FIXTURES", tmp_path)
    monkeypatch.setattr(experiment, "_manifest", lambda _: current)
    monkeypatch.setattr(experiment, "_cases", lambda: [])
    monkeypatch.setattr(experiment, "build_recruiter_narrative_provider", lambda _: _NoCallProvider())
    result = asyncio.run(experiment.run("canonical_test"))
    return result, (tmp_path / "canonical_test.jsonl").exists()


def test_tuple_to_json_list_roundtrip_preserves_frozen_manifest(tmp_path, monkeypatch) -> None:
    assert _replay(tmp_path, monkeypatch, _manifest()) == (0, True)


@pytest.mark.parametrize("change", [
    "field_value", "fixture_hash", "request_hash", "implementation_hash", "case_order",
])
def test_real_manifest_changes_still_fail_closed(tmp_path, monkeypatch, change: str) -> None:
    current = _manifest()
    if change == "field_value":
        current["model"] = "another-model"
    elif change == "fixture_hash":
        current["cases"][0]["projection_sha256"] = "changed_fixture"
    elif change == "request_hash":
        current["cases"][0]["request_sha256"] = "changed_request"
    elif change == "implementation_hash":
        current["source_sha256"]["runner"] = "changed_implementation"
    else:
        current["cases"] = tuple(reversed(current["cases"]))
    assert _replay(tmp_path, monkeypatch, current) == (2, False)


def test_recovery_manifest_identifies_the_immutable_blocked_experiment(monkeypatch) -> None:
    monkeypatch.setattr(experiment, "resolve_provider_selection", lambda *_: SimpleNamespace(
        mode=ProviderMode.OPENAI_COMPATIBLE, model="qwen3.7-flash-2026-07-15"))
    monkeypatch.setattr(experiment, "_hash_file", lambda *_: "test_hash")
    monkeypatch.setattr(experiment, "_cases", lambda: [])
    manifest = experiment._manifest("independent_recovery")
    assert manifest["previous_experiment"] == "interview_semantics_phase2_20261007T1503Z"
    assert manifest["previous_status"] == "BLOCKED_BY_TRANSPORT"
