from __future__ import annotations

import asyncio
import copy
import json

import httpx


PRIVATE_KEY = "phase15-private-backend-test-key"
ARBITRARY_JD = (
    "招聘 AI 应用工程师，负责 RAG、Embedding 与 LLM Agent 工作流，"
    "要求具备 Python、FastAPI、PostgreSQL 和 Qdrant 项目经验。"
)


def _job_output() -> dict[str, object]:
    return {
        "company_name": "合成测试科技",
        "role_title": "AI 应用工程师",
        "must_have": [
            {
                "requirement_id": "req_python",
                "text": "具备 Python 与 FastAPI 项目经验",
                "category": "skill",
                "evidence_expectation": "提供项目代码或测试证据",
            },
            {
                "requirement_id": "req_rag",
                "text": "具备 RAG、Embedding 与 LLM Agent 工作流经验",
                "category": "project_evidence",
                "evidence_expectation": "提供可核验项目证据",
            },
        ],
        "nice_to_have": [
            {
                "requirement_id": "req_storage",
                "text": "具备 PostgreSQL 与 Qdrant 实践",
                "category": "ai_tooling",
                "evidence_expectation": "提供工程实现证据",
            }
        ],
        "role_direction": ["LLM application", "retrieval"],
        "team_tags": ["evidence_driven"],
        "location": {
            "cities": ["上海"],
            "remote_policy": "hybrid",
            "relocation_supported": False,
        },
        "seniority_requirement": ["mid"],
        "product_stage": "zero_to_one",
        "evaluation_focus": ["项目证据", "系统设计"],
    }


def test_arbitrary_jd_uses_real_adapter_and_preserves_prompt_provenance() -> None:
    from app.schemas.persistence import DataOrigin
    from app.services.explanation.generation.openai_compatible import OpenAICompatibleChatProvider
    from app.services.explanation.generation.provider import ExplanationProviderDescriptor
    from app.services.profile_extraction.openai_compatible import OpenAICompatibleStructuredOutputProvider
    from app.services.profile_extraction.parser import ProfileExtractionService
    from app.services.profile_extraction.provider import ProviderDescriptor

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "phase15-test-model",
                "choices": [{"message": {"content": json.dumps(_job_output(), ensure_ascii=False)}}],
            },
        )

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            transport = OpenAICompatibleChatProvider(
                descriptor=ExplanationProviderDescriptor(
                    kind="openai_compatible",
                    name="openai_compatible",
                    configured_model="phase15-test-model",
                    configuration_fingerprint="a" * 64,
                ),
                base_url="https://phase15-provider.invalid/v1",
                api_key=PRIVATE_KEY,
                timeout_seconds=5,
                client=client,
            )
            provider = OpenAICompatibleStructuredOutputProvider(
                transport=transport,
                descriptor=ProviderDescriptor(
                    name="openai_compatible",
                    kind="openai_compatible",
                    data_origin=DataOrigin.LLM_PARSED,
                ),
                max_output_tokens=2048,
            )
            parsed = await ProfileExtractionService(
                provider,
                provider.descriptor,
                max_attempts=1,
                timeout_seconds=5,
            ).extract_job(ARBITRARY_JD, request_id="phase15-arbitrary-jd")
            assert PRIVATE_KEY not in repr(provider)
            return parsed

    parsed = asyncio.run(scenario())
    assert parsed.extraction.provider_kind == "openai_compatible"
    assert parsed.extraction.prompt_version == "job_extraction_prompt_v1"
    assert len(parsed.extraction.prompt_fingerprint) == 64
    assert parsed.draft.role_title == "AI 应用工程师"
    assert PRIVATE_KEY not in repr(parsed)


def test_explanation_provider_cannot_mutate_historical_ranking_snapshot() -> None:
    from tests.test_explanation_generation_service import MATCH_RUN_ID, _service

    service, _tracker, match_runs, _explanations, _attempts, _provider, _pipeline = _service(
        provider_responses=["valid-plan"]
    )
    match_runs.aggregate.result_fingerprint = "c" * 64
    match_runs.aggregate.results[0].ltr_score_raw = 0.712345
    before = copy.deepcopy(match_runs.aggregate)

    asyncio.run(
        service.generate(
            MATCH_RUN_ID,
            requested_top_k=1,
            request_id="phase15-ranking-invariance",
        )
    )
    after = match_runs.aggregate

    assert after.result_fingerprint == before.result_fingerprint
    assert [
        (item.candidate_id, item.result_rank, item.ltr_score_raw)
        for item in after.results
    ] == [
        (item.candidate_id, item.result_rank, item.ltr_score_raw)
        for item in before.results
    ]
