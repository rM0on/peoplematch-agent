import type { ApiResponse } from "./api";


export type RankingTargetType =
  | "overall_ranking"
  | "top1"
  | "candidate_result"
  | "pairwise"
  | "expected_candidate";
export type RankingVerdict = "correct" | "wrong" | "uncertain" | "insufficient_evidence";
export type RankingReasonCode =
  | "wrong_top1"
  | "ranking_inversion"
  | "false_positive"
  | "false_negative"
  | "constraint_conflict"
  | "evidence_coverage_disagreement";
export type ExplanationTargetType =
  | "summary"
  | "match_reason"
  | "risk"
  | "missing_requirement"
  | "interview_question"
  | "top1_comparison"
  | "rewrite_operation";
export type ExplanationVerdict = "grounded" | "unsupported" | "misleading" | "incomplete";
export type ProfileTargetType = "candidate_profile" | "job_profile";
export type ProfileFieldLocator =
  | "candidate.skills"
  | "candidate.project_evidence"
  | "candidate.seniority"
  | "candidate.location"
  | "candidate.role_direction"
  | "job.requirements"
  | "job.requirement_priority"
  | "job.seniority"
  | "job.location"
  | "job.expectations";
export type ProfileDataIssue =
  | "missing_skill"
  | "incorrect_skill"
  | "missing_project_evidence"
  | "incorrect_project_evidence_status"
  | "incorrect_seniority"
  | "incorrect_location"
  | "incorrect_role_direction"
  | "unclear_requirement"
  | "missing_requirement"
  | "incorrect_requirement_priority"
  | "incorrect_seniority_requirement"
  | "incorrect_location_constraint"
  | "missing_expectation";

type FeedbackBase = {
  match_run_id: string;
  comment?: string;
  supersedes_feedback_id?: string;
};

type NonDefectRankingJudgement = {
  value: Exclude<RankingVerdict, "wrong">;
  reason_code?: never;
};

type RankingTargetSelectors =
  | ({ target_type: "overall_ranking"; subject_match_result_id?: never; comparison_match_result_id?: never; expected_candidate_reference?: never } & (
      NonDefectRankingJudgement | { value: "wrong"; reason_code: "constraint_conflict" | "evidence_coverage_disagreement" }
    ))
  | ({ target_type: "top1"; subject_match_result_id: number; comparison_match_result_id?: never; expected_candidate_reference?: never } & (
      NonDefectRankingJudgement | { value: "wrong"; reason_code: "wrong_top1" }
    ))
  | ({ target_type: "candidate_result"; subject_match_result_id: number; comparison_match_result_id?: never; expected_candidate_reference?: never } & (
      NonDefectRankingJudgement | { value: "wrong"; reason_code: "false_positive" | "constraint_conflict" | "evidence_coverage_disagreement" }
    ))
  | ({ target_type: "pairwise"; subject_match_result_id: number; comparison_match_result_id: number; expected_candidate_reference?: never } & (
      NonDefectRankingJudgement | { value: "wrong"; reason_code: "ranking_inversion" | "constraint_conflict" | "evidence_coverage_disagreement" }
    ))
  | ({ target_type: "expected_candidate"; subject_match_result_id?: never; comparison_match_result_id?: never; expected_candidate_reference: string } & (
      NonDefectRankingJudgement | { value: "wrong"; reason_code: "false_negative" }
    ));

export type RankingFeedbackCreate = FeedbackBase & {
  feedback_type: "ranking";
} & RankingTargetSelectors;

export type ExplanationFeedbackCreate = FeedbackBase & {
  feedback_type: "explanation";
  explanation_run_id: string;
  match_explanation_id: number;
  target_type: ExplanationTargetType;
  value: ExplanationVerdict;
  evidence_reference?: string;
};

type CandidateProfileIssue = Extract<ProfileDataIssue,
  | "missing_skill"
  | "incorrect_skill"
  | "missing_project_evidence"
  | "incorrect_project_evidence_status"
  | "incorrect_seniority"
  | "incorrect_location"
  | "incorrect_role_direction"
>;
type JobProfileIssue = Exclude<ProfileDataIssue, CandidateProfileIssue>;
type CandidateFieldLocator = Extract<ProfileFieldLocator, `candidate.${string}`>;
type JobFieldLocator = Extract<ProfileFieldLocator, `job.${string}`>;

export type ProfileDataFeedbackCreate = FeedbackBase & { feedback_type: "profile_data" } & (
  | {
      target_type: "candidate_profile";
      subject_match_result_id: number;
      value: CandidateProfileIssue;
      field_locator: CandidateFieldLocator;
    }
  | {
      target_type: "job_profile";
      subject_match_result_id?: never;
      value: JobProfileIssue;
      field_locator: JobFieldLocator;
    }
);

export type FeedbackCreateRequest =
  | RankingFeedbackCreate
  | ExplanationFeedbackCreate
  | ProfileDataFeedbackCreate;

type FeedbackRecordBase = {
  feedback_id: string;
  contract_version: "feedback_record_v1";
  origin: "human";
  job_id: string;
  candidate_id?: string | null;
  result_rank?: number | null;
  comparison_candidate_id?: string | null;
  comparison_result_rank?: number | null;
  created_at: string;
  match_run_id: string;
  comment?: string | null;
  supersedes_feedback_id?: string | null;
};

export type FeedbackRecord = FeedbackRecordBase & (
  | {
      feedback_type: "ranking";
      target_type: RankingTargetType;
      subject_match_result_id?: number | null;
      comparison_match_result_id?: number | null;
      expected_candidate_reference?: string | null;
      value: RankingVerdict;
      reason_code?: RankingReasonCode | null;
    }
  | {
      feedback_type: "explanation";
      explanation_run_id: string;
      match_explanation_id: number;
      target_type: ExplanationTargetType;
      value: ExplanationVerdict;
      evidence_reference?: string | null;
    }
  | {
      feedback_type: "profile_data";
      target_type: ProfileTargetType;
      subject_match_result_id?: number | null;
      value: ProfileDataIssue;
      field_locator: ProfileFieldLocator;
    }
);

export type MatchResult = {
  match_result_id: number;
  candidate_id: string;
  result_rank: number;
  retrieval_rank: number;
  ltr_rank: number;
  ltr_score_raw: number;
  cross_encoder_rank: number | null;
  cross_encoder_score_raw: number | null;
  skill_fit_score: number | null;
  project_evidence_score: number | null;
  role_direction_score: number | null;
  location_score: number | null;
  seniority_score: number | null;
  feature_diagnostics: Record<string, unknown>;
};

export type MatchRunSummary = {
  run_id: string;
  requested_job_id: string;
  job_id: string | null;
  ranking_variant: "ltr" | "cross_encoder_experiment";
  status: "RUNNING" | "COMPLETED" | "FAILED";
  created_at: string;
  completed_at: string | null;
  result_count: number;
};

export type MatchRunDetail = MatchRunSummary & {
  result_fingerprint?: string;
  results: MatchResult[];
  steps: Array<{ sequence: number; step_name: string; status: string; duration_ms: number | null }>;
};

export type MatchExplanation = {
  match_explanation_id: number;
  output_schema_version: "explanation_output_v1";
  candidate_id: string;
  result_rank: number;
  summary: { text: string; evidence_refs: string[] };
  match_reasons: Array<{ category: string; text: string; evidence_refs: string[] }>;
  risk_points: Array<{ text: string; evidence_refs: string[] }>;
  missing_skills: Array<{
    requirement_id: string;
    requirement_text: string;
    priority: "must_have" | "nice_to_have";
    status: "partial" | "missing";
    evidence_status: "available" | "claim_only" | "absent" | "not_assessed";
    evidence_refs: string[];
  }>;
  interview_questions: Array<{ question: string; evidence_refs: string[] }>;
  why_not_top1: unknown | null;
};

export type ExplanationRunSummary = {
  explanation_run_id: string;
  match_run_id: string;
  status: "RUNNING" | "COMPLETED" | "FAILED";
  explanation_count: number;
  created_at: string | null;
  completed_at: string | null;
};

export type ExplanationRunDetail = ExplanationRunSummary & {
  explanations: MatchExplanation[];
};

export type BadCaseStatus =
  | "CREATED"
  | "REVIEWED"
  | "ROOT_CAUSE_IDENTIFIED"
  | "ACTION_PLANNED"
  | "RESOLVED"
  | "VERIFIED"
  | "DISMISSED"
  | "DUPLICATE";
export type BadCaseSeverity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type BadCaseSymptomCode =
  | "wrong_top1"
  | "ranking_inversion"
  | "false_positive"
  | "false_negative"
  | "constraint_conflict"
  | "uncertain_order"
  | "expected_candidate_not_recalled"
  | "irrelevant_candidate_recalled"
  | "filter_exclusion_disagreement"
  | "pool_truncation_concern"
  | "missing_support"
  | "incorrect_support_status"
  | "project_skill_link_disagreement"
  | "requirement_coverage_disagreement"
  | "unsupported_explanation"
  | "misleading_explanation"
  | "incomplete_explanation"
  | "incorrect_gap_statement"
  | "incorrect_top1_comparison"
  | "candidate_snapshot_issue"
  | "job_snapshot_issue"
  | "requirement_issue"
  | "constraint_issue"
  | "history_integrity_failure"
  | "ownership_failure"
  | "lifecycle_failure"
  | "provider_attempt_failure";
export type SymptomFamily = "RANKING" | "RETRIEVAL" | "EVIDENCE" | "EXPLANATION" | "DATA_QUALITY" | "INTEGRITY_OPERATIONS";
export type RootCauseType = "ranking" | "retrieval" | "feature" | "evidence" | "explanation" | "data_quality" | "integrity";
export type RootCauseCode =
  | "ranking_wrong_top1"
  | "ranking_pairwise_inversion"
  | "ranking_false_positive"
  | "ranking_false_negative"
  | "ranking_tie_break_issue"
  | "ranking_constraint_policy_issue"
  | "retrieval_recall_miss"
  | "retrieval_filter_exclusion"
  | "retrieval_dense_coverage_gap"
  | "retrieval_sparse_coverage_gap"
  | "retrieval_fusion_issue"
  | "retrieval_pool_truncation"
  | "retrieval_index_integrity"
  | "feature_semantic_score_issue"
  | "feature_sparse_score_issue"
  | "feature_skill_fit_issue"
  | "feature_project_evidence_issue"
  | "feature_role_direction_issue"
  | "feature_location_issue"
  | "feature_seniority_issue"
  | "feature_missing_penalty_issue"
  | "feature_overclaim_penalty_issue"
  | "feature_availability_issue"
  | "evidence_missing_project_support"
  | "evidence_status_incorrect"
  | "evidence_skill_project_link_incorrect"
  | "evidence_requirement_alignment_incorrect"
  | "evidence_claim_promoted_without_support"
  | "evidence_owner_mismatch"
  | "explanation_unsupported_claim"
  | "explanation_misleading_template"
  | "explanation_incomplete_selection"
  | "explanation_incorrect_gap"
  | "explanation_comparison_mismatch"
  | "explanation_reference_ownership"
  | "explanation_clarity_issue"
  | "data_candidate_skill_missing"
  | "data_candidate_skill_incorrect"
  | "data_project_evidence_missing"
  | "data_candidate_seniority_incorrect"
  | "data_candidate_location_incorrect"
  | "data_job_requirement_unclear"
  | "data_job_requirement_missing"
  | "data_job_requirement_priority_incorrect"
  | "data_job_level_incorrect"
  | "data_job_expectation_missing"
  | "integrity_snapshot_fingerprint"
  | "integrity_result_fingerprint"
  | "integrity_cross_owner_reference"
  | "integrity_terminal_overwrite"
  | "integrity_attempt_audit";
export type ResolutionActionType =
  | "data_correction_proposal"
  | "retrieval_change_hypothesis"
  | "filter_policy_hypothesis"
  | "fusion_policy_hypothesis"
  | "pool_policy_hypothesis"
  | "feature_rule_hypothesis"
  | "feature_contract_hypothesis"
  | "ranking_change_hypothesis"
  | "ranking_contract_hypothesis"
  | "constraint_policy_hypothesis"
  | "data_integrity_action"
  | "evidence_rule_hypothesis"
  | "evidence_integrity_action"
  | "planning_policy_hypothesis"
  | "template_change_hypothesis"
  | "grounding_integrity_action"
  | "integrity_repair_action"
  | "documentation_action"
  | "no_change";
export type EvidenceKind = "job_requirement" | "skill" | "project" | "project_evidence" | "feature" | "ranking" | "diagnostic" | "comparison" | "field_locator";
export type EvidencePurpose = "supports_observation" | "disputed_reference" | "missing_expected_evidence" | "supports_analysis" | "supports_verification";
export type TruncatedCollection = "sources" | "evidence_links" | "analyses" | "resolution_actions" | "transitions";
export type TransitionReason =
  | "review_completed"
  | "root_cause_supported"
  | "action_created"
  | "actions_completed"
  | "verification_linked"
  | "case_dismissed"
  | "duplicate_linked"
  | "case_reopened";

export type BadCaseSummary = {
  bad_case_id: string;
  case_contract_version: string;
  taxonomy_version: string;
  primary_match_run_id: string;
  primary_match_result_id: number | null;
  historical_job_id: string;
  historical_candidate_id: string | null;
  result_rank: number | null;
  primary_explanation_run_id: string | null;
  primary_match_explanation_id: number | null;
  symptom_code: BadCaseSymptomCode;
  symptom_family: SymptomFamily;
  severity: BadCaseSeverity;
  status: BadCaseStatus;
  revision: number;
  duplicate_of_bad_case_id: string | null;
  related_case_id: string | null;
  created_at: string;
  updated_at: string;
};

export type BadCaseDetail = BadCaseSummary & {
  sources: Array<{
    source_type: "feedback" | "system_signal";
    feedback_id?: string | null;
    system_signal_id?: string | null;
    created_at: string;
  }>;
  evidence_links: Array<{
    evidence_link_id: number;
    explanation_run_id: string | null;
    evidence_reference: string | null;
    field_locator: ProfileFieldLocator | null;
    purpose: EvidencePurpose;
    evidence_kind: EvidenceKind | null;
    candidate_id: string | null;
    result_rank: number | null;
  }>;
  analyses: Array<{
    analysis_id: number;
    revision_number: number;
    assessment: "suspected" | "supported" | "confirmed" | "rejected";
    root_cause_type: RootCauseType;
    root_cause_code: RootCauseCode;
    description: string;
    supporting_evidence_link_id: number | null;
    created_at: string;
  }>;
  resolution_actions: Array<{
    action_id: number;
    action_type: ResolutionActionType;
    description: string;
    status: "planned" | "in_progress" | "completed" | "cancelled" | "superseded";
    supersedes_action_id: number | null;
    safe_change_reference: string | null;
    created_at: string;
    completed_at: string | null;
  }>;
  transitions: Array<{
    transition_id: number;
    from_status: BadCaseStatus;
    to_status: BadCaseStatus;
    reason: TransitionReason;
    origin: "manual_review" | "system_rule";
    previous_revision: number;
    new_revision: number;
    verification_reference: string | null;
    created_at: string;
  }>;
  child_limit: number;
  truncated_collections: TruncatedCollection[];
};

export type BadCaseCreateCommand = {
  source_type: "feedback";
  feedback_id: string;
  symptom_code: BadCaseSymptomCode;
  severity: BadCaseSeverity;
};

export type BadCaseReviewCommand =
  | {
      command: "transition";
      expected_status: BadCaseStatus;
      expected_revision: number;
      status: BadCaseStatus;
      transition_reason: TransitionReason;
      verification_reference?: string;
      duplicate_of_bad_case_id?: string;
    }
  | {
      command: "analysis";
      expected_status: BadCaseStatus;
      expected_revision: number;
      status?: BadCaseStatus;
      transition_reason?: TransitionReason;
      analysis: {
        assessment: "suspected" | "supported" | "confirmed" | "rejected";
        root_cause_type: RootCauseType;
        root_cause_code: RootCauseCode;
        description: string;
        supporting_evidence_link_id?: number;
      };
    }
  | {
      command: "resolution";
      expected_status: BadCaseStatus;
      expected_revision: number;
      status?: BadCaseStatus;
      transition_reason?: TransitionReason;
      resolution: {
        action_type: ResolutionActionType;
        description: string;
        status?: "planned" | "in_progress" | "completed" | "cancelled" | "superseded";
        supersedes_action_id?: number;
        safe_change_reference?: string;
      };
    };

export type Paginated<T> = { items: T[]; total: number; limit: number; offset: number };
export type FeedbackResponse = ApiResponse<FeedbackRecord>;
