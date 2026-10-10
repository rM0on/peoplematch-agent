import type { ApiResponse } from "@/types/api";
import type {
  BadCaseSymptomCode,
  BadCaseCreateCommand,
  BadCaseDetail,
  BadCaseReviewCommand,
  BadCaseSummary,
  EvidenceKind,
  EvidencePurpose,
  ExplanationRunDetail,
  ExplanationRunSummary,
  FeedbackCreateRequest,
  FeedbackRecord,
  MatchRunDetail,
  MatchRunSummary,
  Paginated,
  ProfileDataIssue,
  ProfileFieldLocator,
  ResolutionActionType,
  RootCauseCode,
  RootCauseType,
  SymptomFamily,
} from "@/types/phase10";


export class Phase10ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code: string,
    public readonly requestId: string | null,
  ) {
    super(message);
    this.name = "Phase10ApiError";
  }
}

type SuccessfulApiResponse<T> = ApiResponse<T> & { data: T; error: null };
type ResponseValidator<T> = (value: unknown) => value is T;

const badCaseStatuses = new Set([
  "CREATED", "REVIEWED", "ROOT_CAUSE_IDENTIFIED", "ACTION_PLANNED",
  "RESOLVED", "VERIFIED", "DISMISSED", "DUPLICATE",
]);
const badCaseSeverities = new Set(["LOW", "MEDIUM", "HIGH", "CRITICAL"]);
const truncatedCollections = new Set([
  "sources", "evidence_links", "analyses", "resolution_actions", "transitions",
]);
const rankingTargets = new Set(["overall_ranking", "top1", "candidate_result", "pairwise", "expected_candidate"]);
const rankingVerdicts = new Set(["correct", "wrong", "uncertain", "insufficient_evidence"]);
const rankingReasons = new Set(["wrong_top1", "ranking_inversion", "false_positive", "false_negative", "constraint_conflict", "evidence_coverage_disagreement"]);
const rankingWrongReasons: Record<string, ReadonlySet<string>> = {
  overall_ranking: new Set(["constraint_conflict", "evidence_coverage_disagreement"]),
  top1: new Set(["wrong_top1"]),
  candidate_result: new Set(["false_positive", "constraint_conflict", "evidence_coverage_disagreement"]),
  pairwise: new Set(["ranking_inversion", "constraint_conflict", "evidence_coverage_disagreement"]),
  expected_candidate: new Set(["false_negative"]),
};
const explanationTargets = new Set(["summary", "match_reason", "risk", "missing_requirement", "interview_question", "top1_comparison", "rewrite_operation"]);
const explanationVerdicts = new Set(["grounded", "unsupported", "misleading", "incomplete"]);
const explanationRunStatuses = new Set(["RUNNING", "COMPLETED", "FAILED"]);
const profileTargets = new Set(["candidate_profile", "job_profile"]);
const profileLocators = new Set<ProfileFieldLocator>([
  "candidate.skills", "candidate.project_evidence", "candidate.seniority", "candidate.location", "candidate.role_direction",
  "job.requirements", "job.requirement_priority", "job.seniority", "job.location", "job.expectations",
]);
const profileIssues = new Set<ProfileDataIssue>([
  "missing_skill", "incorrect_skill", "missing_project_evidence", "incorrect_project_evidence_status", "incorrect_seniority",
  "incorrect_location", "incorrect_role_direction", "unclear_requirement", "missing_requirement", "incorrect_requirement_priority",
  "incorrect_seniority_requirement", "incorrect_location_constraint", "missing_expectation",
]);
const profileIssueLocators: Record<ProfileDataIssue, ProfileFieldLocator> = {
  missing_skill: "candidate.skills",
  incorrect_skill: "candidate.skills",
  missing_project_evidence: "candidate.project_evidence",
  incorrect_project_evidence_status: "candidate.project_evidence",
  incorrect_seniority: "candidate.seniority",
  incorrect_location: "candidate.location",
  incorrect_role_direction: "candidate.role_direction",
  unclear_requirement: "job.requirements",
  missing_requirement: "job.requirements",
  incorrect_requirement_priority: "job.requirement_priority",
  incorrect_seniority_requirement: "job.seniority",
  incorrect_location_constraint: "job.location",
  missing_expectation: "job.expectations",
};
const symptomCodes = new Set<BadCaseSymptomCode>([
  "wrong_top1", "ranking_inversion", "false_positive", "false_negative", "constraint_conflict", "uncertain_order",
  "expected_candidate_not_recalled", "irrelevant_candidate_recalled", "filter_exclusion_disagreement", "pool_truncation_concern",
  "missing_support", "incorrect_support_status", "project_skill_link_disagreement", "requirement_coverage_disagreement",
  "unsupported_explanation", "misleading_explanation", "incomplete_explanation", "incorrect_gap_statement",
  "incorrect_top1_comparison", "candidate_snapshot_issue", "job_snapshot_issue", "requirement_issue", "constraint_issue",
  "history_integrity_failure", "ownership_failure", "lifecycle_failure", "provider_attempt_failure",
]);
const symptomFamilies = new Set<SymptomFamily>(["RANKING", "RETRIEVAL", "EVIDENCE", "EXPLANATION", "DATA_QUALITY", "INTEGRITY_OPERATIONS"]);
const rootCauseTypes = new Set<RootCauseType>(["ranking", "retrieval", "feature", "evidence", "explanation", "data_quality", "integrity"]);
const rootCauseCodes = new Set<RootCauseCode>([
  "ranking_wrong_top1", "ranking_pairwise_inversion", "ranking_false_positive", "ranking_false_negative", "ranking_tie_break_issue", "ranking_constraint_policy_issue",
  "retrieval_recall_miss", "retrieval_filter_exclusion", "retrieval_dense_coverage_gap", "retrieval_sparse_coverage_gap", "retrieval_fusion_issue", "retrieval_pool_truncation", "retrieval_index_integrity",
  "feature_semantic_score_issue", "feature_sparse_score_issue", "feature_skill_fit_issue", "feature_project_evidence_issue", "feature_role_direction_issue", "feature_location_issue", "feature_seniority_issue", "feature_missing_penalty_issue", "feature_overclaim_penalty_issue", "feature_availability_issue",
  "evidence_missing_project_support", "evidence_status_incorrect", "evidence_skill_project_link_incorrect", "evidence_requirement_alignment_incorrect", "evidence_claim_promoted_without_support", "evidence_owner_mismatch",
  "explanation_unsupported_claim", "explanation_misleading_template", "explanation_incomplete_selection", "explanation_incorrect_gap", "explanation_comparison_mismatch", "explanation_reference_ownership", "explanation_clarity_issue",
  "data_candidate_skill_missing", "data_candidate_skill_incorrect", "data_project_evidence_missing", "data_candidate_seniority_incorrect", "data_candidate_location_incorrect", "data_job_requirement_unclear", "data_job_requirement_missing", "data_job_requirement_priority_incorrect", "data_job_level_incorrect", "data_job_expectation_missing",
  "integrity_snapshot_fingerprint", "integrity_result_fingerprint", "integrity_cross_owner_reference", "integrity_terminal_overwrite", "integrity_attempt_audit",
]);
const resolutionActionTypes = new Set<ResolutionActionType>([
  "data_correction_proposal", "retrieval_change_hypothesis", "filter_policy_hypothesis", "fusion_policy_hypothesis", "pool_policy_hypothesis",
  "feature_rule_hypothesis", "feature_contract_hypothesis", "ranking_change_hypothesis", "ranking_contract_hypothesis", "constraint_policy_hypothesis",
  "data_integrity_action", "evidence_rule_hypothesis", "evidence_integrity_action", "planning_policy_hypothesis", "template_change_hypothesis",
  "grounding_integrity_action", "integrity_repair_action", "documentation_action", "no_change",
]);
const evidenceKinds = new Set<EvidenceKind>(["job_requirement", "skill", "project", "project_evidence", "feature", "ranking", "diagnostic", "comparison", "field_locator"]);
const evidencePurposes = new Set<EvidencePurpose>(["supports_observation", "disputed_reference", "missing_expected_evidence", "supports_analysis", "supports_verification"]);

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isString(value: unknown): value is string { return typeof value === "string"; }
function isNumber(value: unknown): value is number { return typeof value === "number" && Number.isFinite(value); }
function isInteger(value: unknown): value is number { return Number.isInteger(value); }
function isNullableString(value: unknown) { return value === null || isString(value); }
function isNullableNumber(value: unknown) { return value === null || isNumber(value); }
function isNullableInteger(value: unknown) { return value === null || isInteger(value); }
function isStringArray(value: unknown): value is string[] { return Array.isArray(value) && value.every(isString); }
function isOptionalNullableString(value: unknown) { return value === undefined || isNullableString(value); }
function isOptionalNullableInteger(value: unknown) { return value === undefined || isNullableInteger(value); }

function isMatchRunSummary(value: unknown): value is MatchRunSummary {
  return isObject(value)
    && isString(value.run_id)
    && isString(value.requested_job_id)
    && isNullableString(value.job_id)
    && ["ltr", "cross_encoder_experiment"].includes(String(value.ranking_variant))
    && ["RUNNING", "COMPLETED", "FAILED"].includes(String(value.status))
    && isString(value.created_at)
    && isNullableString(value.completed_at)
    && isInteger(value.result_count);
}

function isMatchResult(value: unknown) {
  return isObject(value)
    && isInteger(value.match_result_id)
    && isString(value.candidate_id)
    && isInteger(value.result_rank)
    && isInteger(value.retrieval_rank)
    && isInteger(value.ltr_rank)
    && isNumber(value.ltr_score_raw)
    && isNullableInteger(value.cross_encoder_rank)
    && isNullableNumber(value.cross_encoder_score_raw)
    && isNullableNumber(value.skill_fit_score)
    && isNullableNumber(value.project_evidence_score)
    && isNullableNumber(value.role_direction_score)
    && isNullableNumber(value.location_score)
    && isNullableNumber(value.seniority_score)
    && isObject(value.feature_diagnostics);
}

function isMatchRunDetail(value: unknown): value is MatchRunDetail {
  if (!isMatchRunSummary(value)) return false;
  const detail = value as Record<string, unknown>;
  return (detail.result_fingerprint === undefined || (isString(detail.result_fingerprint) && /^[a-f0-9]{64}$/.test(detail.result_fingerprint)))
    && Array.isArray(detail.results)
    && detail.results.every(isMatchResult)
    && Array.isArray(detail.steps)
    && detail.steps.every((step: unknown) => isObject(step)
      && isInteger(step.sequence)
      && isString(step.step_name)
      && isString(step.status)
      && isNullableNumber(step.duration_ms));
}

function isEvidenceText(value: unknown, textKey: string) {
  return isObject(value) && isString(value[textKey]) && isStringArray(value.evidence_refs);
}

function isExplanationRunSummary(value: unknown): value is ExplanationRunSummary {
  return isObject(value)
    && isString(value.explanation_run_id)
    && isString(value.match_run_id)
    && explanationRunStatuses.has(String(value.status))
    && isInteger(value.explanation_count)
    && isNullableString(value.created_at)
    && isNullableString(value.completed_at);
}

function isMissingRequirement(value: unknown) {
  return isObject(value)
    && isString(value.requirement_id)
    && isString(value.requirement_text)
    && (value.priority === "must_have" || value.priority === "nice_to_have")
    && (value.status === "partial" || value.status === "missing")
    && ["available", "claim_only", "absent", "not_assessed"].includes(String(value.evidence_status))
    && isStringArray(value.evidence_refs);
}

function isMatchExplanation(value: unknown) {
  return isObject(value)
    && isInteger(value.match_explanation_id)
    && value.output_schema_version === "explanation_output_v1"
    && isString(value.candidate_id)
    && isInteger(value.result_rank)
    && isEvidenceText(value.summary, "text")
    && Array.isArray(value.match_reasons)
    && value.match_reasons.every((item) => isEvidenceText(item, "text") && isString(item.category))
    && Array.isArray(value.risk_points)
    && value.risk_points.every((item) => isEvidenceText(item, "text"))
    && Array.isArray(value.missing_skills)
    && value.missing_skills.every(isMissingRequirement)
    && Array.isArray(value.interview_questions)
    && value.interview_questions.every((item) => isEvidenceText(item, "question"));
}

function isExplanationRunDetail(value: unknown): value is ExplanationRunDetail {
  if (!isExplanationRunSummary(value)) return false;
  const detail = value as Record<string, unknown>;
  return Array.isArray(detail.explanations)
    && detail.explanations.every(isMatchExplanation);
}

function isFeedbackRecord(value: unknown): value is FeedbackRecord {
  if (!isObject(value)
    || !isString(value.feedback_id)
    || value.contract_version !== "feedback_record_v1"
    || value.origin !== "human"
    || !isString(value.match_run_id)
    || !isString(value.job_id)
    || !isString(value.created_at)
    || !isOptionalNullableString(value.candidate_id)
    || !isOptionalNullableInteger(value.result_rank)
    || !isOptionalNullableString(value.comparison_candidate_id)
    || !isOptionalNullableInteger(value.comparison_result_rank)
    || !isOptionalNullableString(value.comment)
    || !isOptionalNullableString(value.supersedes_feedback_id)) return false;
  if (value.feedback_type === "ranking") {
    const target = String(value.target_type);
    const verdict = String(value.value);
    const reason = value.reason_code;
    if (!rankingTargets.has(target) || !rankingVerdicts.has(verdict)) return false;
    if (verdict === "wrong") {
      if (!rankingReasons.has(String(reason)) || !rankingWrongReasons[target].has(String(reason))) return false;
    } else if (reason !== undefined && reason !== null) return false;
    const subject = value.subject_match_result_id;
    const comparison = value.comparison_match_result_id;
    const expected = value.expected_candidate_reference;
    if (!isOptionalNullableInteger(subject)
      || !isOptionalNullableInteger(comparison)
      || !isOptionalNullableString(expected)) return false;
    if (target === "overall_ranking") return subject == null && comparison == null && expected == null;
    if (target === "top1" || target === "candidate_result") return isInteger(subject) && comparison == null && expected == null;
    if (target === "pairwise") return isInteger(subject) && isInteger(comparison) && subject !== comparison && expected == null;
    return subject == null && comparison == null && isString(expected);
  }
  if (value.feedback_type === "explanation") {
    return isString(value.explanation_run_id)
      && isInteger(value.match_explanation_id)
      && explanationTargets.has(String(value.target_type))
      && explanationVerdicts.has(String(value.value))
      && isOptionalNullableString(value.evidence_reference);
  }
  if (value.feedback_type !== "profile_data"
    || !profileTargets.has(String(value.target_type))
    || !profileIssues.has(value.value as ProfileDataIssue)
    || !profileLocators.has(value.field_locator as ProfileFieldLocator)
    || !isOptionalNullableInteger(value.subject_match_result_id)) return false;
  const issue = value.value as ProfileDataIssue;
  const locator = value.field_locator as ProfileFieldLocator;
  if (profileIssueLocators[issue] !== locator) return false;
  return value.target_type === "candidate_profile"
    ? locator.startsWith("candidate.") && isInteger(value.subject_match_result_id)
    : locator.startsWith("job.") && value.subject_match_result_id == null;
}

function isBadCaseSummary(value: unknown): value is BadCaseSummary {
  return isObject(value)
    && isString(value.bad_case_id)
    && value.case_contract_version === "bad_case_v1"
    && value.taxonomy_version === "bad_case_taxonomy_v1"
    && isString(value.primary_match_run_id)
    && isNullableInteger(value.primary_match_result_id)
    && isString(value.historical_job_id)
    && isNullableString(value.historical_candidate_id)
    && isNullableInteger(value.result_rank)
    && isNullableString(value.primary_explanation_run_id)
    && isNullableInteger(value.primary_match_explanation_id)
    && symptomCodes.has(value.symptom_code as BadCaseSymptomCode)
    && symptomFamilies.has(value.symptom_family as SymptomFamily)
    && badCaseSeverities.has(String(value.severity))
    && badCaseStatuses.has(String(value.status))
    && isInteger(value.revision)
    && isNullableString(value.duplicate_of_bad_case_id)
    && isNullableString(value.related_case_id)
    && isString(value.created_at)
    && isString(value.updated_at);
}

function isBadCaseDetail(value: unknown): value is BadCaseDetail {
  if (!isBadCaseSummary(value)) return false;
  const detail = value as Record<string, unknown>;
  return Array.isArray(detail.sources)
    && detail.sources.every((item: unknown) => isObject(item)
      && ["feedback", "system_signal"].includes(String(item.source_type))
      && (item.feedback_id === undefined || isNullableString(item.feedback_id))
      && (item.system_signal_id === undefined || isNullableString(item.system_signal_id))
      && isString(item.created_at))
    && Array.isArray(detail.evidence_links)
    && detail.evidence_links.every((item: unknown) => isObject(item)
      && isInteger(item.evidence_link_id)
      && isNullableString(item.explanation_run_id)
      && isNullableString(item.evidence_reference)
      && isNullableString(item.field_locator)
      && evidencePurposes.has(item.purpose as EvidencePurpose)
      && (item.evidence_kind === null || evidenceKinds.has(item.evidence_kind as EvidenceKind))
      && isNullableString(item.candidate_id)
      && isNullableInteger(item.result_rank))
    && Array.isArray(detail.analyses)
    && detail.analyses.every((item: unknown) => isObject(item)
      && isInteger(item.analysis_id)
      && isInteger(item.revision_number)
      && ["suspected", "supported", "confirmed", "rejected"].includes(String(item.assessment))
      && rootCauseTypes.has(item.root_cause_type as RootCauseType)
      && rootCauseCodes.has(item.root_cause_code as RootCauseCode)
      && isString(item.description)
      && isNullableInteger(item.supporting_evidence_link_id)
      && isString(item.created_at))
    && Array.isArray(detail.resolution_actions)
    && detail.resolution_actions.every((item: unknown) => isObject(item)
      && isInteger(item.action_id)
      && resolutionActionTypes.has(item.action_type as ResolutionActionType)
      && isString(item.description)
      && ["planned", "in_progress", "completed", "cancelled", "superseded"].includes(String(item.status))
      && isNullableInteger(item.supersedes_action_id)
      && isNullableString(item.safe_change_reference)
      && isString(item.created_at)
      && isNullableString(item.completed_at))
    && Array.isArray(detail.transitions)
    && detail.transitions.every((item: unknown) => isObject(item)
      && isInteger(item.transition_id)
      && badCaseStatuses.has(String(item.from_status))
      && badCaseStatuses.has(String(item.to_status))
      && isString(item.reason)
      && ["manual_review", "system_rule"].includes(String(item.origin))
      && isInteger(item.previous_revision)
      && isInteger(item.new_revision)
      && isNullableString(item.verification_reference)
      && isString(item.created_at))
    && isInteger(detail.child_limit)
    && Array.isArray(detail.truncated_collections)
    && detail.truncated_collections.every((item: unknown) => truncatedCollections.has(String(item)));
}

function isPaginated<T>(itemValidator: ResponseValidator<T>): ResponseValidator<Paginated<T>> {
  return (value): value is Paginated<T> => isObject(value)
    && Array.isArray(value.items)
    && value.items.every(itemValidator)
    && isInteger(value.total)
    && isInteger(value.limit)
    && isInteger(value.offset);
}

function apiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (!configured) {
    throw new Phase10ApiError("Backend API is not configured", 0, "api_unconfigured", null);
  }
  return configured.replace(/\/$/, "");
}

async function request<T>(path: string, validator: ResponseValidator<T>, init?: RequestInit): Promise<SuccessfulApiResponse<T>> {
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    cache: "no-store",
    headers: { Accept: "application/json", "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  let decoded: unknown;
  try {
    decoded = await response.json();
  } catch {
    throw new Phase10ApiError("Backend returned an unreadable response", response.status, "invalid_response", null);
  }
  if (!isObject(decoded) || typeof decoded.success !== "boolean" || !isString(decoded.request_id)) {
    throw new Phase10ApiError("Backend returned an invalid response", response.status, "invalid_response", null);
  }
  const error = isObject(decoded.error) ? decoded.error : null;
  if (!response.ok || !decoded.success || decoded.data === null) {
    throw new Phase10ApiError(
      isString(error?.message) ? error.message : "The review request could not be completed",
      response.status,
      isString(error?.code) ? error.code : "request_failed",
      decoded.request_id,
    );
  }
  if (decoded.error !== null) {
    throw new Phase10ApiError("Backend returned an invalid response", response.status, "invalid_response", decoded.request_id);
  }
  if (!validator(decoded.data)) {
    throw new Phase10ApiError("Backend returned an invalid response", response.status, "invalid_response", decoded.request_id);
  }
  return decoded as unknown as SuccessfulApiResponse<T>;
}

export async function createFeedback(payload: FeedbackCreateRequest) {
  return request<FeedbackRecord>("/api/v1/feedback", isFeedbackRecord, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listBadCases({ limit, offset }: { limit: number; offset: number }) {
  return request<Paginated<BadCaseSummary>>(
    `/api/v1/bad-cases?limit=${encodeURIComponent(limit)}&offset=${encodeURIComponent(offset)}`,
    isPaginated(isBadCaseSummary),
  );
}

export async function getBadCase(badCaseId: string, childLimit = 100) {
  return request<BadCaseDetail>(
    `/api/v1/bad-cases/${encodeURIComponent(badCaseId)}?child_limit=${encodeURIComponent(childLimit)}`,
    isBadCaseDetail,
  );
}

export async function reviewBadCase(badCaseId: string, payload: BadCaseReviewCommand) {
  return request<BadCaseDetail>(`/api/v1/bad-cases/${encodeURIComponent(badCaseId)}/review`, isBadCaseDetail, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function createBadCase(payload: BadCaseCreateCommand) {
  return request<BadCaseDetail>("/api/v1/bad-cases", isBadCaseDetail, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getFeedback(feedbackId: string) {
  return request<FeedbackRecord>(`/api/v1/feedback/${encodeURIComponent(feedbackId)}`, isFeedbackRecord);
}

export async function listCompletedMatchRuns(limit = 20) {
  return request<Paginated<MatchRunSummary>>(
    `/api/v1/match-runs?limit=${encodeURIComponent(limit)}&offset=0&status=COMPLETED`,
    isPaginated(isMatchRunSummary),
  );
}

export async function getMatchRun(matchRunId: string) {
  return request<MatchRunDetail>(`/api/v1/match-runs/${encodeURIComponent(matchRunId)}`, isMatchRunDetail);
}

export async function listExplanationRuns(matchRunId: string, limit = 20) {
  return request<Paginated<ExplanationRunSummary>>(
    `/api/v1/match-runs/${encodeURIComponent(matchRunId)}/explanation-runs?limit=${encodeURIComponent(limit)}&offset=0`,
    isPaginated(isExplanationRunSummary),
  );
}

export async function getExplanationRun(explanationRunId: string) {
  return request<ExplanationRunDetail>(
    `/api/v1/explanation-runs/${encodeURIComponent(explanationRunId)}`,
    isExplanationRunDetail,
  );
}
