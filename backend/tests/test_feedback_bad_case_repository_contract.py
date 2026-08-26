from __future__ import annotations

import inspect

import pytest


def test_phase10_repository_surface_is_append_only_and_transaction_owned() -> None:
    from app.repositories.bad_case_repository import BadCaseRepository
    from app.repositories.feedback_repository import FeedbackRepository

    assert {
        "create",
        "get_by_id",
        "list_supersession_ancestry",
        "resolve_match_run",
        "resolve_match_result",
        "resolve_explanation",
        "resolve_evidence",
        "resolve_profile_snapshot",
    } <= set(dir(FeedbackRepository))
    assert {
        "create_with_source",
        "get_by_id",
        "list_cases",
        "append_source",
        "append_evidence_link",
        "append_analysis",
        "append_resolution_action",
        "transition_atomically",
    } <= set(dir(BadCaseRepository))

    forbidden_mutators = {
        "update_feedback",
        "delete_feedback",
        "update_analysis",
        "delete_analysis",
        "update_resolution_action",
        "delete_resolution_action",
        "delete_transition",
    }
    assert forbidden_mutators.isdisjoint(dir(FeedbackRepository))
    assert forbidden_mutators.isdisjoint(dir(BadCaseRepository))
    assert "session_factory" in inspect.signature(FeedbackRepository).parameters
    assert "session_factory" in inspect.signature(BadCaseRepository).parameters

    for repository, method_names in (
        (
            FeedbackRepository,
            (
                "create",
                "get_by_id",
                "list_supersession_ancestry",
                "resolve_match_run",
                "resolve_match_result",
                "resolve_explanation",
                "resolve_evidence",
                "resolve_profile_snapshot",
            ),
        ),
        (
            BadCaseRepository,
            (
                "create_with_source",
                "get_by_id",
                "list_cases",
                "append_source",
                "append_evidence_link",
                "append_analysis",
                "append_resolution_action",
                "transition_atomically",
            ),
        ),
    ):
        for method_name in method_names:
            session_parameter = inspect.signature(
                getattr(repository, method_name)
            ).parameters["session"]
            assert session_parameter.kind is inspect.Parameter.KEYWORD_ONLY
            assert session_parameter.default is None

    feedback_source = inspect.getsource(
        __import__(
            "app.repositories.feedback_repository",
            fromlist=["FeedbackRepository"],
        )
    )
    for forbidden_current_state_dependency in (
        "app.models.candidate",
        "app.models.job",
        "CandidateRepository",
        "JobRepository",
        "Qdrant",
    ):
        assert forbidden_current_state_dependency not in feedback_source

    repository_sources = feedback_source + inspect.getsource(
        __import__(
            "app.repositories.bad_case_repository",
            fromlist=["BadCaseRepository"],
        )
    )
    assert ".commit(" not in repository_sources
    assert ".rollback(" not in repository_sources


def test_evidence_index_resolves_only_validated_historical_bundle_owners() -> None:
    from app.repositories.feedback_repository import index_evidence_bundle
    from tests.test_explanation_postgres import _evidence

    bundle, _provider = _evidence(
        "00000000-0000-0000-0000-000000001003",
        "job_usr_phase10_1003",
        ["cand_usr_phase10_1003_1", "cand_usr_phase10_1003_2"],
    )
    index = index_evidence_bundle(bundle.model_dump(mode="json", exclude_none=False))

    requirement = index["job_requirement:req_python"]
    assert requirement.kind == "job_requirement"
    assert requirement.candidate_id is None
    assert requirement.result_rank is None

    skill = index[
        "candidate:2:skill:0123456789abcdef0123456789abcde2"
    ]
    assert skill.kind == "skill"
    assert skill.candidate_id == "cand_usr_phase10_1003_2"
    assert skill.result_rank == 2

    comparison = index["comparison:2:top1:skill_fit_score"]
    assert comparison.kind == "comparison"
    assert comparison.candidate_id == "cand_usr_phase10_1003_2"
    assert comparison.result_rank == 2


def test_evidence_index_rejects_unvalidated_or_tampered_payload() -> None:
    from app.repositories.feedback_repository import HistoricalIntegrityError
    from app.repositories.feedback_repository import index_evidence_bundle

    with pytest.raises(HistoricalIntegrityError):
        index_evidence_bundle(
            {
                "contract_version": "evidence_bundle_v1",
                "candidates": [],
                "private_escape": "RAW RESUME",
            }
        )


def test_repository_errors_are_typed_by_failure_boundary() -> None:
    from app.repositories.phase10_errors import (
        BadCaseConcurrencyError,
        BadCaseNotFoundError,
        HistoricalIntegrityError,
        HistoricalOwnershipError,
        Phase10ConflictError,
        Phase10NotFoundError,
    )

    assert issubclass(BadCaseConcurrencyError, Phase10ConflictError)
    assert issubclass(HistoricalOwnershipError, Phase10ConflictError)
    assert issubclass(HistoricalIntegrityError, Phase10ConflictError)
    assert issubclass(BadCaseNotFoundError, Phase10NotFoundError)


def test_list_bounds_fail_closed_before_query_execution() -> None:
    from app.repositories.bad_case_repository import BadCaseRepository

    for invalid in (0, -1, 101, True, 1.5, "10"):
        with pytest.raises(ValueError):
            BadCaseRepository.validate_list_window(limit=invalid, offset=0)
    for invalid in (-1, True, 1.5, "0"):
        with pytest.raises(ValueError):
            BadCaseRepository.validate_list_window(limit=10, offset=invalid)
    assert BadCaseRepository.validate_list_window(limit=100, offset=0) == (100, 0)
