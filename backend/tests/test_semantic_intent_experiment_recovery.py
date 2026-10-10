"""A recovered batch must not overwrite or append to the blocked batch."""

import asyncio
import json
from types import SimpleNamespace

from app.services.llm.configuration import ProviderMode
from app.services.explanation.presentation.generation_proposition_v1 import build_proposition_binding_v1
from app.services.explanation.presentation.propositions_v1 import build_recruiter_propositions_for_interview_v1
from narrative_v2_comparison_fixture import build_comparison_group
import narrative_semantic_intent_v1_live_experiment as experiment


def test_recovery_writes_a_distinct_experiment_id_and_preserves_blocked_artifact(
    tmp_path, monkeypatch,
):
    blocked = tmp_path / "blocked.jsonl"
    blocked.write_text('{"gate":"PROVIDER_FAIL"}\n', encoding="utf-8")
    original = blocked.read_bytes()
    recovered = tmp_path / "recovered.jsonl"

    class NoCallProvider:
        async def aclose(self):
            pass

    monkeypatch.setattr(experiment, "SAMPLES", ())
    monkeypatch.setattr(experiment, "build_recruiter_narrative_provider", lambda settings: NoCallProvider())
    monkeypatch.setattr(experiment, "resolve_provider_selection", lambda settings, task: SimpleNamespace(
        mode=ProviderMode.OPENAI_COMPATIBLE, model="qwen3.7-flash-2026-07-15"))

    experiment_id = "semantic_intent_v1_phase2_recovered_proxy_20261007"
    assert asyncio.run(experiment.main(output_path=recovered, experiment_id=experiment_id)) == 0
    assert blocked.read_bytes() == original
    manifest = json.loads(recovered.read_text(encoding="utf-8").splitlines()[0])
    assert manifest["experiment"] == experiment_id
    assert manifest["previous_batch"] == "BLOCKED_BY_TRANSPORT"
    assert manifest["preregistered_samples"] == []
    saved = recovered.read_bytes()
    assert asyncio.run(experiment.main(output_path=recovered, experiment_id=experiment_id)) == 2
    assert recovered.read_bytes() == saved


def test_experiment_rejects_field_role_valid_but_unfocused_handle(tmp_path, monkeypatch):
    projection = build_comparison_group(1)["projections"][0]
    propositions = build_recruiter_propositions_for_interview_v1(projection)
    binding = build_proposition_binding_v1(propositions)
    plan = experiment.build_semantic_intent_plan_v1(projection, propositions)
    focus = set(plan.field("why_consider").proposition_ids)
    extra = next(entry.handle for entry in binding.entries
                 if entry.proposition_id not in focus and "why_consider" in entry.allowed_fields)
    payload = {
        "contract_version": "recruiter_proposition_generation_v1",
        "candidate_id": propositions.candidate_id, "result_rank": propositions.result_rank,
        "decision_summary": {"text": "建议由招聘人员决定是否继续了解。",
                             "proposition_handles": {binding.allowed_handles("decision_summary")[0]: True}},
        **{field: [{"text": "这是一条合成候选人的测试表述。",
                    "proposition_handles": {binding.allowed_handles(field)[0]: True}}]
           for field in ("why_consider", "technical_signal", "interview_focus", "uncertainty")},
    }
    payload["why_consider"][0]["proposition_handles"] = {extra: True}

    class Provider:
        async def generate(self, request):
            return SimpleNamespace(content=json.dumps(payload, ensure_ascii=False), http_status_code=200)

        async def aclose(self):
            pass

    monkeypatch.setattr(experiment, "SAMPLES", (("ai_agent_a", 1, 0, "development"),))
    monkeypatch.setattr(experiment, "build_recruiter_narrative_provider", lambda settings: Provider())
    monkeypatch.setattr(experiment, "resolve_provider_selection", lambda settings, task: SimpleNamespace(
        mode=ProviderMode.OPENAI_COMPATIBLE, model="qwen3.7-flash-2026-07-15"))
    output_path = tmp_path / "focus_rejection.jsonl"
    assert asyncio.run(experiment.main(output_path=output_path, experiment_id="focus_test")) == 2
    case = json.loads(output_path.read_text(encoding="utf-8").splitlines()[1])
    assert case["schema"] == "PASS"
    assert case["handle"] == "NOT_RUN"
    assert case["gate"] == "STRUCTURAL_FAIL"


def test_final_refinement_runner_uses_archived_pairs_and_new_independent_holdouts():
    assert experiment.SAMPLES == (
        ("ai_agent_a", 1, 0, "development"),
        ("ai_agent_b", 1, 1, "development"),
        ("recommendation_a", 2, 0, "development"),
        ("recommendation_b", 2, 1, "development"),
        ("backend_a", 3, 0, "development"),
        ("backend_b", 3, 1, "development"),
        ("data_search_holdout", 6, 0, "holdout"),
        ("vision_api_holdout", 7, 0, "holdout"),
    )
    assert "final_refinement" in experiment.OUTPUT.name
    assert experiment.PREREG.name == "2026-10-07-recruiter-proposition-phase2-final-refinement.md"
