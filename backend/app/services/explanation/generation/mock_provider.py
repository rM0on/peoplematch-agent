from __future__ import annotations

import json

from pydantic import ValidationError

from app.services.explanation.generation.contracts import (
    ProviderExplanationPlanV1,
    PlanInterviewQuestionOperation,
    PlanMatchReason,
    PlanRiskPoint,
)
from app.services.explanation.generation.provider import (
    ExplanationProviderDescriptor,
    ExplanationProviderMalformedResponseError,
    ExplanationProviderRequest,
    ExplanationProviderResponse,
)
from app.services.explanation.generation.contracts import ProviderPromptEvidenceV1
from app.services.explanation.generation.semantic_selection import ProviderExplanationSelectionV1
from app.services.match_runs.contracts import canonical_fingerprint


_MOCK_MODEL = "deterministic-explanation-planner-v1"


class DeterministicExplanationProvider:
    """Offline provider that selects exact prompt tuples deterministically."""

    descriptor = ExplanationProviderDescriptor(
        kind="deterministic",
        name="mock",
        configured_model=_MOCK_MODEL,
        configuration_fingerprint=canonical_fingerprint(
            {
                "kind": "deterministic",
                "name": "mock",
                "model": _MOCK_MODEL,
                "version": 1,
            }
        ),
    )

    async def generate(
        self, request: ExplanationProviderRequest
    ) -> ExplanationProviderResponse:
        if request.output_contract_version == "provider_explanation_selection_v1":
            return self._generate_selection(request)
        if request.output_contract_version != "provider_explanation_plan_v1":
            raise ExplanationProviderMalformedResponseError()
        try:
            envelope = json.loads(request.user_instruction)
            if not isinstance(envelope, dict):
                raise ValueError
            evidence = ProviderPromptEvidenceV1.model_validate(envelope["evidence"])
        except (KeyError, TypeError, ValueError, ValidationError, json.JSONDecodeError):
            raise ExplanationProviderMalformedResponseError() from None

        candidates = []
        for candidate in evidence.candidates:
            semantic_reasons = [
                PlanMatchReason(
                    category=item.category,
                    template_key=item.statement_key,
                    evidence_refs=item.evidence_refs,
                )
                for item in candidate.facts.match_reasons
            ]
            reasons = semantic_reasons[:4]
            if len(reasons) < 2 and candidate.facts.ranking_context:
                context = candidate.facts.ranking_context[0]
                reasons.append(
                    PlanMatchReason(
                        category="ranking_context",
                        template_key="ranking_context_recorded",
                        evidence_refs=context.evidence_refs,
                    )
                )
            if not reasons:
                raise ExplanationProviderMalformedResponseError()

            risks = sorted(
                (
                    PlanRiskPoint(
                        category=item.category,
                        template_key=item.statement_key,
                        evidence_refs=item.evidence_refs,
                    )
                    for item in candidate.facts.risks[:4]
                ),
                key=lambda item: item.model_dump_json(),
            )
            interviews = sorted(
                (
                    PlanInterviewQuestionOperation(
                        operation="ask_evidence_clarification",
                        evidence_refs=item.evidence_refs,
                    )
                    for item in candidate.facts.missing_requirements
                    if item.status in {"missing", "partial"}
                ),
                key=lambda item: item.model_dump_json(),
            )[:3]
            comparison = candidate.facts.comparison
            candidates.append(
                {
                    "candidate_ref": candidate.candidate_ref,
                    "result_rank": candidate.result_rank,
                    "summary": {
                        "template_key": "recorded_match_summary",
                        "match_reason_index": 0,
                    },
                    "match_reasons": [
                        item.model_dump(mode="json") for item in reasons
                    ],
                    "risk_points": [item.model_dump(mode="json") for item in risks],
                    "interview_question_operations": [
                        item.model_dump(mode="json") for item in interviews
                    ],
                    "why_not_top1": (
                        None
                        if comparison is None
                        else {
                            "template_key": "why_not_top1_recorded",
                            "evidence_refs": comparison.evidence_refs,
                        }
                    ),
                    "rewrite_operations": [],
                }
            )
        plan = ProviderExplanationPlanV1(
            contract_version="provider_explanation_plan_v1",
            candidates=candidates,
        )
        return ExplanationProviderResponse(
            content=plan.model_dump_json(exclude_none=False),
            observed_model=self.descriptor.configured_model,
        )

    def _generate_selection(self, request: ExplanationProviderRequest) -> ExplanationProviderResponse:
        try:
            envelope = json.loads(request.user_instruction)
            catalog = envelope["option_catalog"]
            if catalog["contract_version"] != "provider_semantic_option_catalog_v1":
                raise ValueError
            candidates = []
            for candidate in catalog["candidates"]:
                chosen_reasons = []
                categories = set()
                for option in candidate["options"]:
                    if option["kind"] == "reason" and option["category"] not in categories:
                        chosen_reasons.append(option["handle"])
                        categories.add(option["category"])
                    if len(chosen_reasons) == 4:
                        break
                if not chosen_reasons:
                    raise ValueError
                candidates.append({
                    "candidate_ref": candidate["candidate_ref"],
                    "match_reason_handles": chosen_reasons,
                    "risk_handles": [
                        option["handle"] for option in candidate["options"]
                        if option["kind"] == "risk"
                    ][:4],
                    "interview_handles": [
                        option["handle"] for option in candidate["options"]
                        if option["kind"] == "interview"
                    ][:3],
                    "rewrite_handles": [],
                    "summary_primary_reason_handle": chosen_reasons[0],
                })
            selection = ProviderExplanationSelectionV1.model_validate({
                "contract_version": "provider_explanation_selection_v1",
                "candidates": candidates,
            })
        except (KeyError, TypeError, ValueError, ValidationError, json.JSONDecodeError):
            raise ExplanationProviderMalformedResponseError() from None
        return ExplanationProviderResponse(
            content=selection.model_dump_json(),
            observed_model=self.descriptor.configured_model,
        )


__all__ = ["DeterministicExplanationProvider"]
