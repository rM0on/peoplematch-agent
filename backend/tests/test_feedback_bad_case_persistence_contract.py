from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Index, UniqueConstraint


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT
    / "backend"
    / "alembic"
    / "versions"
    / "20260826_0005_feedback_bad_case_management.py"
)


def _models():
    feedback = importlib.import_module("app.models.feedback")
    bad_case = importlib.import_module("app.models.bad_case")
    return feedback, bad_case


def _constraint_names(table, constraint_type):
    return {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, constraint_type)
    }


def _foreign_keys(table):
    return {
        (fk.parent.name, fk.target_fullname, fk.ondelete)
        for fk in table.foreign_keys
    }


def _check_text(table, name: str) -> str:
    return str(
        next(
            constraint.sqltext
            for constraint in table.constraints
            if isinstance(constraint, CheckConstraint) and constraint.name == name
        )
    )


def test_feedback_models_have_exact_closed_persistence_columns() -> None:
    feedback, _bad_case = _models()

    assert set(feedback.FeedbackRecordModel.__table__.columns.keys()) == {
        "feedback_id",
        "contract_version",
        "feedback_type",
        "origin",
        "target_type",
        "match_run_id",
        "match_result_id",
        "comparison_match_result_id",
        "candidate_id",
        "comparison_candidate_id",
        "result_rank",
        "comparison_result_rank",
        "expected_candidate_reference",
        "job_id",
        "explanation_run_id",
        "match_explanation_id",
        "value",
        "reason_code",
        "field_locator",
        "evidence_reference",
        "comment",
        "supersedes_feedback_id",
        "created_at",
    }
    assert set(feedback.SystemSignalModel.__table__.columns.keys()) == {
        "signal_id",
        "contract_version",
        "match_run_id",
        "explanation_run_id",
        "signal_code",
        "source_stage",
        "source_error_code",
        "occurrence_identity",
        "created_at",
    }
    forbidden = {
        "metadata",
        "payload",
        "raw_resume",
        "raw_jd",
        "provider_response",
        "evaluation_label",
        "split",
    }
    assert forbidden.isdisjoint(feedback.FeedbackRecordModel.__table__.columns.keys())
    assert forbidden.isdisjoint(feedback.SystemSignalModel.__table__.columns.keys())


def test_feedback_history_foreign_keys_are_restrictive() -> None:
    feedback, _bad_case = _models()

    assert _foreign_keys(feedback.FeedbackRecordModel.__table__) >= {
        ("match_run_id", "match_runs.run_id", "RESTRICT"),
        ("match_result_id", "match_results.id", "RESTRICT"),
        ("comparison_match_result_id", "match_results.id", "RESTRICT"),
        ("explanation_run_id", "explanation_runs.explanation_run_id", "RESTRICT"),
        ("match_explanation_id", "match_explanations.id", "RESTRICT"),
        ("supersedes_feedback_id", "feedback_records.feedback_id", "RESTRICT"),
    }
    assert _foreign_keys(feedback.SystemSignalModel.__table__) >= {
        ("match_run_id", "match_runs.run_id", "RESTRICT"),
        ("explanation_run_id", "explanation_runs.explanation_run_id", "RESTRICT"),
    }


def test_feedback_tables_have_named_semantic_constraints() -> None:
    feedback, _bad_case = _models()

    checks = _constraint_names(feedback.FeedbackRecordModel.__table__, CheckConstraint)
    assert {
        "ck_feedback_records_type",
        "ck_feedback_records_target_type",
        "ck_feedback_records_origin",
        "ck_feedback_records_result_rank",
        "ck_feedback_records_comparison_rank",
        "ck_feedback_records_contract_version",
        "ck_feedback_records_value",
        "ck_feedback_records_reason_code",
        "ck_feedback_records_field_locator",
        "ck_feedback_records_semantic_shape",
        "ck_feedback_records_ranking_reason_compatibility",
        "ck_feedback_records_profile_issue_compatibility",
        "ck_feedback_records_expected_candidate_reference",
        "ck_feedback_records_self_supersession",
    } <= checks
    uniques = _constraint_names(feedback.SystemSignalModel.__table__, UniqueConstraint)
    assert "uq_system_signals_occurrence" in uniques
    signal_checks = _constraint_names(
        feedback.SystemSignalModel.__table__, CheckConstraint
    )
    assert {
        "ck_system_signals_contract_version",
        "ck_system_signals_code",
        "ck_system_signals_source_stage",
    } <= signal_checks
    signal_code_check = _check_text(
        feedback.SystemSignalModel.__table__, "ck_system_signals_code"
    )
    for human_judgment in ("wrong_top1", "false_negative", "model_bad"):
        assert human_judgment not in signal_code_check


def test_feedback_database_shape_preserves_absent_candidate_semantics() -> None:
    feedback, _bad_case = _models()

    shape = _check_text(
        feedback.FeedbackRecordModel.__table__,
        "ck_feedback_records_semantic_shape",
    )
    assert "expected_candidate" in shape
    assert "expected_candidate_reference IS NOT NULL" in shape
    assert "match_result_id IS NULL" in shape
    expected_reference = _check_text(
        feedback.FeedbackRecordModel.__table__,
        "ck_feedback_records_expected_candidate_reference",
    )
    assert "expected_candidate:" in expected_reference


def test_feedback_database_binds_reason_and_profile_locator_semantics() -> None:
    feedback, _bad_case = _models()

    ranking = _check_text(
        feedback.FeedbackRecordModel.__table__,
        "ck_feedback_records_ranking_reason_compatibility",
    )
    assert "target_type = 'top1'" in ranking
    assert "reason_code = 'wrong_top1'" in ranking
    assert "target_type = 'expected_candidate'" in ranking
    assert "reason_code = 'false_negative'" in ranking
    profile = _check_text(
        feedback.FeedbackRecordModel.__table__,
        "ck_feedback_records_profile_issue_compatibility",
    )
    assert "'missing_skill'" in profile
    assert "field_locator = 'candidate.skills'" in profile
    assert "value = 'missing_expectation'" in profile
    assert "field_locator = 'job.expectations'" in profile


def test_bad_case_models_are_relational_and_append_only() -> None:
    _feedback, bad_case = _models()

    expected = {
        "bad_cases": bad_case.BadCaseModel,
        "bad_case_source_links": bad_case.BadCaseSourceLinkModel,
        "feedback_evidence_links": bad_case.FeedbackEvidenceLinkModel,
        "bad_case_analyses": bad_case.BadCaseAnalysisModel,
        "resolution_actions": bad_case.ResolutionActionModel,
        "bad_case_transitions": bad_case.BadCaseTransitionModel,
    }
    assert {name: model.__tablename__ for name, model in expected.items()} == {
        name: name for name in expected
    }
    assert "analysis" not in bad_case.BadCaseModel.__table__.columns
    assert "resolution" not in bad_case.BadCaseModel.__table__.columns
    assert set(bad_case.BadCaseModel.__table__.columns.keys()) == {
        "bad_case_id",
        "case_contract_version",
        "taxonomy_version",
        "primary_match_run_id",
        "primary_match_result_id",
        "historical_job_id",
        "historical_candidate_id",
        "result_rank",
        "primary_explanation_run_id",
        "primary_match_explanation_id",
        "symptom_code",
        "symptom_family",
        "severity",
        "status",
        "revision",
        "related_case_id",
        "duplicate_of_bad_case_id",
        "created_at",
        "updated_at",
    }
    assert set(bad_case.BadCaseAnalysisModel.__table__.columns.keys()) == {
        "id",
        "bad_case_id",
        "revision_number",
        "assessment",
        "root_cause_type",
        "root_cause_code",
        "description",
        "supporting_evidence_link_id",
        "created_at",
    }
    assert "origin" in bad_case.BadCaseTransitionModel.__table__.columns
    assert {
        "uq_bad_case_analysis_revision"
    } <= _constraint_names(bad_case.BadCaseAnalysisModel.__table__, UniqueConstraint)
    assert {
        "ck_bad_case_source_exactly_one",
    } <= _constraint_names(bad_case.BadCaseSourceLinkModel.__table__, CheckConstraint)
    assert {
        "ck_feedback_evidence_link_exactly_one",
    } <= _constraint_names(bad_case.FeedbackEvidenceLinkModel.__table__, CheckConstraint)


def test_bad_case_source_foreign_keys_are_restrictive() -> None:
    _feedback, bad_case = _models()

    assert _foreign_keys(bad_case.BadCaseModel.__table__) >= {
        ("primary_match_run_id", "match_runs.run_id", "RESTRICT"),
        ("primary_match_result_id", "match_results.id", "RESTRICT"),
        ("primary_explanation_run_id", "explanation_runs.explanation_run_id", "RESTRICT"),
        ("primary_match_explanation_id", "match_explanations.id", "RESTRICT"),
        ("related_case_id", "bad_cases.bad_case_id", "RESTRICT"),
        ("duplicate_of_bad_case_id", "bad_cases.bad_case_id", "RESTRICT"),
    }
    assert _foreign_keys(bad_case.BadCaseSourceLinkModel.__table__) >= {
        ("bad_case_id", "bad_cases.bad_case_id", "RESTRICT"),
        ("feedback_id", "feedback_records.feedback_id", "RESTRICT"),
        ("system_signal_id", "system_signals.signal_id", "RESTRICT"),
    }
    for model in (
        bad_case.FeedbackEvidenceLinkModel,
        bad_case.BadCaseAnalysisModel,
        bad_case.ResolutionActionModel,
        bad_case.BadCaseTransitionModel,
    ):
        assert ("bad_case_id", "bad_cases.bad_case_id", "RESTRICT") in _foreign_keys(
            model.__table__
        )
    assert (
        "supporting_evidence_link_id",
        "feedback_evidence_links.id",
        "RESTRICT",
    ) in _foreign_keys(bad_case.BadCaseAnalysisModel.__table__)


def test_bad_case_child_references_are_bound_to_same_case_owner() -> None:
    _feedback, bad_case = _models()

    assert {
        "uq_feedback_evidence_link_owner",
    } <= _constraint_names(bad_case.FeedbackEvidenceLinkModel.__table__, UniqueConstraint)
    assert {
        "uq_bad_case_analysis_owner",
    } <= _constraint_names(bad_case.BadCaseAnalysisModel.__table__, UniqueConstraint)
    assert {
        "uq_resolution_action_owner",
    } <= _constraint_names(bad_case.ResolutionActionModel.__table__, UniqueConstraint)
    assert {
        "fk_bad_case_analyses_support_owner",
    } <= _constraint_names(bad_case.BadCaseAnalysisModel.__table__, ForeignKeyConstraint)
    assert {
        "fk_resolution_actions_supersedes_owner",
    } <= _constraint_names(bad_case.ResolutionActionModel.__table__, ForeignKeyConstraint)
    assert {
        "fk_bad_case_transitions_analysis_owner",
        "fk_bad_case_transitions_action_owner",
    } <= _constraint_names(bad_case.BadCaseTransitionModel.__table__, ForeignKeyConstraint)


def test_bad_case_parent_has_closed_lifecycle_constraints() -> None:
    _feedback, bad_case = _models()

    checks = _constraint_names(bad_case.BadCaseModel.__table__, CheckConstraint)
    assert {
        "ck_bad_cases_category",
        "ck_bad_cases_symptom_family",
        "ck_bad_cases_severity",
        "ck_bad_cases_status",
        "ck_bad_cases_revision",
        "ck_bad_cases_result_rank",
        "ck_bad_cases_duplicate_owner",
        "ck_bad_cases_contract_version",
        "ck_bad_cases_taxonomy_version",
        "ck_bad_cases_symptom_family_consistency",
        "ck_bad_cases_related_owner",
    } <= checks
    transition_checks = _constraint_names(
        bad_case.BadCaseTransitionModel.__table__, CheckConstraint
    )
    assert {
        "ck_bad_case_transitions_revision",
        "ck_bad_case_transitions_status_change",
        "ck_bad_case_transitions_reason",
        "ck_bad_case_transitions_origin",
        "ck_bad_case_transitions_reason_compatibility",
    } <= transition_checks
    assert "REVIEWED" in _check_text(
        bad_case.BadCaseModel.__table__, "ck_bad_cases_status"
    )
    assert "REVIEWING" not in _check_text(
        bad_case.BadCaseModel.__table__, "ck_bad_cases_status"
    )


def test_bad_case_child_taxonomy_is_closed_at_database_boundary() -> None:
    _feedback, bad_case = _models()

    assert {
        "ck_bad_case_analyses_root_cause_code",
        "ck_bad_case_analyses_root_cause_compatibility",
    } <= _constraint_names(bad_case.BadCaseAnalysisModel.__table__, CheckConstraint)
    assert {
        "ck_resolution_actions_action_type",
        "ck_resolution_actions_status",
        "ck_resolution_actions_lifecycle",
    } <= _constraint_names(bad_case.ResolutionActionModel.__table__, CheckConstraint)
    assert {
        "ck_feedback_evidence_links_purpose",
        "ck_feedback_evidence_links_kind",
        "ck_feedback_evidence_links_owner",
        "ck_feedback_evidence_links_field_locator",
        "ck_feedback_evidence_links_purpose_shape",
        "ck_feedback_evidence_links_namespace_owner",
    } <= _constraint_names(bad_case.FeedbackEvidenceLinkModel.__table__, CheckConstraint)
    namespace_owner = _check_text(
        bad_case.FeedbackEvidenceLinkModel.__table__,
        "ck_feedback_evidence_links_namespace_owner",
    )
    assert "result_rank" in namespace_owner
    assert "job_requirement:" in namespace_owner
    assert "comparison:" in namespace_owner
    assert "project_evidence:" in namespace_owner
    assert {
        "ck_resolution_actions_self_supersession",
    } <= _constraint_names(bad_case.ResolutionActionModel.__table__, CheckConstraint)


def test_bad_case_transition_database_matrix_is_exact() -> None:
    _feedback, bad_case = _models()

    compatibility = _check_text(
        bad_case.BadCaseTransitionModel.__table__,
        "ck_bad_case_transitions_reason_compatibility",
    )
    assert "from_status IN ('CREATED', 'REVIEWED')" in compatibility
    assert (
        "from_status IN ('CREATED', 'REVIEWED', 'ROOT_CAUSE_IDENTIFIED', "
        "'ACTION_PLANNED')" in compatibility
    )
    checks = _constraint_names(
        bad_case.BadCaseTransitionModel.__table__, CheckConstraint
    )
    assert "ck_bad_case_transitions_verification" in checks


def test_bad_case_indexes_cover_historical_review_queries() -> None:
    _feedback, bad_case = _models()

    indexes = {index.name for index in bad_case.BadCaseModel.__table__.indexes}
    assert {
        "ix_bad_cases_match_run_id",
        "ix_bad_cases_match_result_id",
        "ix_bad_cases_explanation_run_id",
        "ix_bad_cases_historical_job_id",
        "ix_bad_cases_historical_candidate_id",
        "ix_bad_cases_status",
        "ix_bad_cases_severity",
        "ix_bad_cases_symptom_code",
        "ix_bad_cases_created_at",
    } <= indexes


def test_phase10_migration_is_additive_and_follows_phase94() -> None:
    spec = importlib.util.spec_from_file_location("phase10_migration_0005", MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.revision == "20260826_0005"
    assert module.down_revision == "20260825_0004"
    source = MIGRATION.read_text(encoding="utf-8")
    for table in (
        "feedback_records",
        "system_signals",
        "bad_cases",
        "bad_case_source_links",
        "feedback_evidence_links",
        "bad_case_analyses",
        "resolution_actions",
        "bad_case_transitions",
    ):
        assert f'"{table}"' in source
    assert "alter_column" not in source
    assert "drop_column" not in source
    for frozen_table in (
        "match_runs",
        "match_results",
        "explanation_runs",
        "match_explanations",
    ):
        assert f'op.create_table("{frozen_table}"' not in source
        assert f'op.drop_table("{frozen_table}"' not in source
        assert f'op.alter_table("{frozen_table}"' not in source


def test_phase10_migration_mirrors_all_named_model_constraints_and_indexes() -> None:
    feedback, bad_case = _models()
    source = MIGRATION.read_text(encoding="utf-8")
    tables = (
        feedback.FeedbackRecordModel.__table__,
        feedback.SystemSignalModel.__table__,
        bad_case.BadCaseModel.__table__,
        bad_case.BadCaseSourceLinkModel.__table__,
        bad_case.FeedbackEvidenceLinkModel.__table__,
        bad_case.BadCaseAnalysisModel.__table__,
        bad_case.ResolutionActionModel.__table__,
        bad_case.BadCaseTransitionModel.__table__,
    )

    for table in tables:
        for column in table.columns:
            assert f'"{column.name}"' in source
        for constraint in table.constraints:
            if constraint.name is not None:
                assert f'"{constraint.name}"' in source
        for index in table.indexes:
            assert f'"{index.name}"' in source
    assert 'sa.Column("category"' not in source
    assert "REVIEWING" not in source
    assert "REVIEWED" in source
