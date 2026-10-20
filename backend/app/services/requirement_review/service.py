"""A fail-closed view over already validated explanation and recruiter sources."""

from __future__ import annotations

from pydantic import ValidationError

from app.exceptions import DomainError
from app.repositories.recruiter_narrative_repository import NarrativeSourceIntegrityError
from app.schemas.requirement_review import RequirementReviewRowV1, RequirementReviewV1, RequirementSourceDescriptorV1
from app.services.explanation.evidence.requirement_builder import MissingRequirementBuilder
from app.services.explanation.presentation.structured_service import (
    RecruiterPropositionSourceInvalidError,
    RecruiterPropositionSourceNotFoundError,
)


class RequirementReviewNotFoundError(DomainError):
    code = "requirement_review_source_not_found"
    status_code = 404

    def __init__(self) -> None:
        super().__init__("Source explanation was not found")


class RequirementReviewInvalidError(DomainError):
    code = "requirement_review_source_invalid"
    status_code = 409

    def __init__(self) -> None:
        super().__init__("Source cannot support a trusted requirement review")


class RequirementReviewService:
    def __init__(self, repository, proposition_service) -> None:
        self.repository = repository
        self.proposition_service = proposition_service

    @staticmethod
    def _display_terms(values, limit: int) -> str:
        """Bound a display summary without rejecting a valid historical source."""
        shown = "、".join(item if len(item) <= 48 else f"{item[:47]}…" for item in values[:limit])
        rest = len(values) - limit
        return f"{shown}（另 {rest} 项）" if rest > 0 else (shown or "未记录")

    async def get(self, match_explanation_id: int) -> RequirementReviewV1:
        try:
            brief = await self.proposition_service.get(match_explanation_id)
        except RecruiterPropositionSourceNotFoundError:
            raise RequirementReviewNotFoundError() from None
        except RecruiterPropositionSourceInvalidError:
            raise RequirementReviewInvalidError() from None
        try:
            source = await self.repository.load_source(match_explanation_id)
        except NarrativeSourceIntegrityError:
            raise RequirementReviewInvalidError() from None
        if source is None:
            raise RequirementReviewNotFoundError()
        try:
            if (
                source.match_explanation_id != match_explanation_id
                or brief.source_explanation_id != match_explanation_id
                or brief.match_run_id != source.bundle.source.match_run_id
                or brief.explanation_run_id != source.explanation_run_id
                or brief.candidate_id != source.output.candidate_id
                or brief.result_rank != source.output.result_rank
                or brief.ranking_fingerprint != source.bundle.source.result_fingerprint
                or brief.source_output_fingerprint != source.candidate_output_fingerprint
                or brief.source_bundle_fingerprint != source.evidence_bundle_fingerprint
            ):
                raise ValueError("brief_source_mismatch")

            job_requirements = tuple(source.bundle.job.requirements)
            ids = [item.requirement_id for item in job_requirements]
            refs = {f"job_requirement:{item}" for item in ids}
            if len(ids) != len(set(ids)):
                raise ValueError("duplicate_requirement_id")
            if any(item.evidence_id != f"job_requirement:{item.requirement_id}" for item in job_requirements):
                raise ValueError("requirement_canonical_ref_mismatch")
            candidate_diagnostics = [
                item for item in MissingRequirementBuilder().build(source.bundle)
                if item.candidate_id == brief.candidate_id and item.result_rank == brief.result_rank
            ]
            diagnostic_by_id = {item.requirement_id: item for item in candidate_diagnostics}
            if len(candidate_diagnostics) != len(ids) or set(diagnostic_by_id) != set(ids):
                raise ValueError("incomplete_requirement_diagnostics")

            owners = [item for item in source.bundle.candidates
                      if item.candidate_id == brief.candidate_id and item.result_rank == brief.result_rank]
            if len(owners) != 1:
                raise ValueError("historical_candidate_source_mismatch")
            owner = owners[0]
            catalog = {}
            for skill in owner.skills:
                catalog[skill.evidence_id] = RequirementSourceDescriptorV1(
                    evidence_ref=skill.evidence_id,
                    source_kind="historical_skill_claim",
                    description=f"历史档案技能声明：{skill.name}",
                )
            for project in owner.projects:
                technologies = self._display_terms(project.technologies, 4)
                demonstrated = self._display_terms(project.skills_demonstrated, 2)
                catalog[project.evidence_id] = RequirementSourceDescriptorV1(
                    evidence_ref=project.evidence_id,
                    source_kind="historical_project",
                    description=f"历史项目 {project.project_id} · 记录技术 {technologies} · 展示技能标签 {demonstrated}",
                )
            for record in owner.project_evidence:
                supports = self._display_terms(record.supports_skills, 3)
                catalog[record.evidence_id] = RequirementSourceDescriptorV1(
                    evidence_ref=record.evidence_id,
                    source_kind="historical_project_record",
                    description=(f"历史项目材料记录 {record.project_id} · 来源 {record.source_evidence_id}"
                                 f" · 支持技能标签 {supports} · 核验状态 {record.verification_status.value}"),
                )

            linked = {item: [] for item in refs}
            cross_requirement = []
            used_sources = set()
            for proposition in brief.all_propositions():
                job_refs_in_evidence = tuple(
                    ref for ref in proposition.evidence_refs if ref.startswith("job_requirement:")
                )
                if (
                    proposition.candidate_id != brief.candidate_id
                    or proposition.result_rank != brief.result_rank
                    or len(set(proposition.evidence_refs)) != len(proposition.evidence_refs)
                    or job_refs_in_evidence != proposition.job_requirement_refs
                    or any(not ref.startswith(("candidate:", "job_requirement:")) for ref in proposition.evidence_refs)
                    or any(
                        ref.startswith("candidate:") and not ref.startswith(f"candidate:{brief.result_rank}:")
                        for ref in proposition.evidence_refs
                    )
                    or any(ref not in refs for ref in proposition.job_requirement_refs)
                ):
                    raise ValueError("proposition_source_isolation_failed")
                for evidence_ref in proposition.evidence_refs:
                    if evidence_ref.startswith("candidate:"):
                        if evidence_ref not in catalog:
                            raise ValueError("historical_candidate_evidence_not_found")
                        if proposition.job_requirement_refs:
                            used_sources.add(evidence_ref)
                if len(proposition.job_requirement_refs) > 1:
                    cross_requirement.append(proposition)
                elif proposition.job_requirement_refs:
                    linked[proposition.job_requirement_refs[0]].append(proposition)

            ordered = sorted(
                enumerate(job_requirements),
                key=lambda pair: (0 if pair[1].priority.value == "must_have" else 1, pair[0]),
            )
            rows = []
            for _, requirement in ordered:
                diagnostic = diagnostic_by_id[requirement.requirement_id]
                if diagnostic.priority != requirement.priority.value:
                    raise ValueError("requirement_priority_mismatch")
                ref = f"job_requirement:{requirement.requirement_id}"
                if tuple(diagnostic.evidence_refs) != (ref,):
                    raise ValueError("requirement_ref_mismatch")
                rows.append(RequirementReviewRowV1(
                    requirement_id=requirement.requirement_id,
                    priority=requirement.priority.value,
                    text=requirement.text,
                    diagnostic_status=diagnostic.status,
                    evidence_status=diagnostic.evidence_status,
                    source_refs=tuple(diagnostic.evidence_refs),
                    propositions=tuple(linked[ref]),
                ))
            return RequirementReviewV1(
                role_title=source.bundle.job.role_title,
                match_run_id=brief.match_run_id,
                explanation_run_id=brief.explanation_run_id,
                source_explanation_id=match_explanation_id,
                candidate_id=brief.candidate_id,
                result_rank=brief.result_rank,
                ranking_fingerprint=brief.ranking_fingerprint,
                source_output_fingerprint=brief.source_output_fingerprint,
                source_bundle_fingerprint=brief.source_bundle_fingerprint,
                requirements=tuple(rows),
                source_descriptors=tuple(catalog[ref] for ref in sorted(used_sources)),
                cross_requirement_propositions=tuple(cross_requirement),
            )
        except (ValueError, ValidationError):
            raise RequirementReviewInvalidError() from None


__all__ = ["RequirementReviewService", "RequirementReviewNotFoundError", "RequirementReviewInvalidError"]
