from __future__ import annotations

from app.repositories.bad_case_repository import BadCaseAggregate
from app.schemas.bad_cases import (
    BadCaseAnalysisResponse,
    BadCaseSourceResponse,
    BadCaseSummaryResponse,
    BadCaseTransitionResponse,
    ResolutionActionResponse,
)
from app.schemas.phase10 import (
    BadCaseApiDetailResponse,
    BadCaseEvidenceLinkResponse,
    BadCaseTransitionApiResponse,
    PHASE10_REVIEW_EXPORT_VERSION,
    Phase10ReviewExportV1,
    ReviewResolutionActionExport,
    ReviewRootCauseExport,
)


def project_summary(root) -> BadCaseSummaryResponse:
    return BadCaseSummaryResponse.model_validate(
        {
            "bad_case_id": root.bad_case_id,
            "case_contract_version": root.case_contract_version,
            "taxonomy_version": root.taxonomy_version,
            "primary_match_run_id": root.primary_match_run_id,
            "primary_match_result_id": root.primary_match_result_id,
            "historical_job_id": root.historical_job_id,
            "historical_candidate_id": root.historical_candidate_id,
            "result_rank": root.result_rank,
            "primary_explanation_run_id": root.primary_explanation_run_id,
            "primary_match_explanation_id": root.primary_match_explanation_id,
            "symptom_code": root.symptom_code,
            "symptom_family": root.symptom_family,
            "severity": root.severity,
            "status": root.status,
            "revision": root.revision,
            "duplicate_of_bad_case_id": root.duplicate_of_bad_case_id,
            "related_case_id": root.related_case_id,
            "created_at": root.created_at,
            "updated_at": root.updated_at,
        }
    )


def project_detail(aggregate: BadCaseAggregate) -> BadCaseApiDetailResponse:
    root = project_summary(aggregate.root).model_dump()
    return BadCaseApiDetailResponse.model_validate(
        {
            **root,
            "sources": [
                BadCaseSourceResponse.model_validate(
                    {
                        "source_type": (
                            "feedback" if item.feedback_id is not None else "system_signal"
                        ),
                        "feedback_id": item.feedback_id,
                        "system_signal_id": item.system_signal_id,
                        "created_at": item.created_at,
                    }
                )
                for item in aggregate.sources
            ],
            "evidence_links": [
                BadCaseEvidenceLinkResponse.model_validate(
                    {
                        "evidence_link_id": item.id,
                        "explanation_run_id": item.explanation_run_id,
                        "evidence_reference": item.evidence_reference,
                        "field_locator": item.field_locator,
                        "purpose": item.purpose,
                        "evidence_kind": item.evidence_kind,
                        "candidate_id": item.candidate_id,
                        "result_rank": item.result_rank,
                    }
                )
                for item in aggregate.evidence_links
            ],
            "analyses": [
                BadCaseAnalysisResponse.model_validate(
                    {
                        "analysis_id": item.id,
                        "revision_number": item.revision_number,
                        "assessment": item.assessment,
                        "root_cause_type": item.root_cause_type,
                        "root_cause_code": item.root_cause_code,
                        "description": item.description,
                        "supporting_evidence_link_id": item.supporting_evidence_link_id,
                        "created_at": item.created_at,
                    }
                )
                for item in aggregate.analyses
            ],
            "resolution_actions": [
                ResolutionActionResponse.model_validate(
                    {
                        "action_id": item.id,
                        "action_type": item.action_type,
                        "description": item.description,
                        "status": item.status,
                        "supersedes_action_id": item.supersedes_action_id,
                        "safe_change_reference": item.safe_change_reference,
                        "created_at": item.created_at,
                        "completed_at": item.completed_at,
                    }
                )
                for item in aggregate.resolution_actions
            ],
            "transitions": [
                BadCaseTransitionApiResponse.model_validate(
                    {
                        "transition_id": item.id,
                        "from_status": item.from_status,
                        "to_status": item.to_status,
                        "reason": item.reason,
                        "origin": item.origin,
                        "previous_revision": item.previous_revision,
                        "new_revision": item.new_revision,
                        "verification_reference": item.verification_reference,
                        "created_at": item.created_at,
                    }
                )
                for item in aggregate.transitions
            ],
            "child_limit": aggregate.child_limit,
            "truncated_collections": sorted(aggregate.truncated_collections),
        }
    )


def project_review_export(aggregate: BadCaseAggregate) -> Phase10ReviewExportV1:
    verification_reference = next(
        (
            item.verification_reference
            for item in reversed(aggregate.transitions)
            if item.to_status == "VERIFIED" and item.verification_reference is not None
        ),
        None,
    )
    return Phase10ReviewExportV1.model_validate(
        {
            "contract_version": PHASE10_REVIEW_EXPORT_VERSION,
            "bad_case_id": aggregate.root.bad_case_id,
            "match_run_id": aggregate.root.primary_match_run_id,
            "match_result_id": aggregate.root.primary_match_result_id,
            "symptom_code": aggregate.root.symptom_code,
            "symptom_family": aggregate.root.symptom_family,
            "severity": aggregate.root.severity,
            "status": aggregate.root.status,
            "source_types": sorted(
                {
                    "feedback" if item.feedback_id is not None else "system_signal"
                    for item in aggregate.sources
                }
            ),
            "root_cause_assessments": [
                ReviewRootCauseExport(
                    assessment=assessment,
                    root_cause_type=root_type,
                    root_cause_code=root_code,
                )
                for assessment, root_type, root_code in sorted(
                    {
                        (item.assessment, item.root_cause_type, item.root_cause_code)
                        for item in aggregate.analyses
                    }
                )
            ],
            "evidence_kinds": sorted(
                {
                    item.evidence_kind or "field_locator"
                    for item in aggregate.evidence_links
                }
            ),
            "resolution_actions": [
                ReviewResolutionActionExport(action_type=action_type, status=status)
                for action_type, status in sorted(
                    {(item.action_type, item.status) for item in aggregate.resolution_actions}
                )
            ],
            "verification_state": (
                "case_specific_verified"
                if aggregate.root.status == "VERIFIED"
                else "not_verified"
            ),
            "verification_reference": verification_reference,
        }
    )


__all__ = ["project_detail", "project_review_export", "project_summary"]
