import type {
  CandidateDraft,
  CandidatePage,
  DemoExplanation,
  DemoExplanationRun,
  DemoIndexData,
  DemoMatchResult,
  DemoMatchRun,
  DemoRun,
  DemoSamples,
  DemoStage,
  ExtractionMetadata,
  JobDraft,
  JobParseData,
  CandidateParseData,
  CandidatePoolAddition,
  CandidateRecord,
} from "@/types/demo";


type Validator<T> = (value: unknown) => value is T;

export class DemoApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code: string,
    public readonly requestId: string | null,
  ) {
    super(message);
    this.name = "DemoApiError";
  }
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isString(value: unknown): value is string {
  return typeof value === "string";
}

function isNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isInteger(value: unknown): value is number {
  return Number.isInteger(value);
}

function isNullableNumber(value: unknown): value is number | null {
  return value === null || isNumber(value);
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every(isString);
}

function isExtraction(value: unknown): value is ExtractionMetadata {
  return isObject(value)
    && isString(value.provider)
    && (value.provider_kind === "mock" || value.provider_kind === "openai_compatible")
    && (value.prompt_version === "candidate_extraction_prompt_v1"
      || value.prompt_version === "job_extraction_prompt_v1")
    && isString(value.prompt_fingerprint)
    && /^[a-f0-9]{64}$/.test(value.prompt_fingerprint)
    && isInteger(value.attempts)
    && value.attempts >= 1
    && value.attempts <= 2
    && typeof value.repaired === "boolean"
    && typeof value.persisted === "boolean"
    && isString(value.input_fingerprint)
    && /^[a-f0-9]{64}$/.test(value.input_fingerprint);
}

function isRequirement(value: unknown): boolean {
  return isObject(value)
    && isString(value.requirement_id)
    && isString(value.text)
    && isString(value.category)
    && isString(value.evidence_expectation);
}

function isCandidateDraft(value: unknown): value is CandidateDraft {
  return isObject(value)
    && isString(value.name)
    && Array.isArray(value.skills)
    && value.skills.every((skill) => isObject(skill) && isString(skill.name) && isString(skill.category)
      && (skill.self_reported_level === null || isString(skill.self_reported_level)))
    && Array.isArray(value.projects)
    && value.projects.every((project) => isObject(project)
      && isString(project.project_id)
      && isString(project.name)
      && isString(project.summary)
      && isString(project.role)
      && isStringArray(project.technologies)
      && isStringArray(project.outcomes)
      && isStringArray(project.skills_demonstrated))
    && Array.isArray(value.project_evidence)
    && value.project_evidence.every((evidence) => isObject(evidence)
      && isString(evidence.evidence_id)
      && isString(evidence.project_id)
      && isStringArray(evidence.supports_skills)
      && isString(evidence.evidence_type)
      && isString(evidence.statement)
      && (evidence.artifact_ref === null || isString(evidence.artifact_ref))
      && isString(evidence.verification_status))
    && (value.github_url === null || isString(value.github_url))
    && isStringArray(value.ai_tools)
    && isStringArray(value.target_roles)
    && isObject(value.preferred_locations)
    && isStringArray(value.preferred_locations.cities)
    && isString(value.preferred_locations.remote_policy)
    && typeof value.preferred_locations.relocation_open === "boolean"
    && isString(value.seniority)
    && isObject(value.work_style)
    && isStringArray(value.work_style.team_stage_preference)
    && isString(value.work_style.collaboration_style)
    && isStringArray(value.missing_fields)
    && isObject(value.overclaim_risk)
    && isString(value.overclaim_risk.level)
    && isStringArray(value.overclaim_risk.reasons);
}

function isCandidateRecord(value: unknown): value is CandidateRecord {
  return isObject(value)
    && isString(value.candidate_id)
    && (value.archetype === null || isString(value.archetype))
    && isString(value.raw_text)
    && ["synthetic_sandbox", "user_created", "mock_parsed", "llm_parsed"].includes(String(value.data_origin))
    && value.schema_version === "1.0"
    && (value.dataset_version === null || isString(value.dataset_version))
    && isCandidateDraft(value);
}

function isCandidateParseData(value: unknown): value is CandidateParseData {
  return isObject(value)
    && isCandidateDraft(value.draft)
    && (value.record === null || isCandidateRecord(value.record))
    && isExtraction(value.extraction);
}

function isCandidatePage(value: unknown): value is CandidatePage {
  return isObject(value)
    && Array.isArray(value.items)
    && value.items.every(isCandidateRecord)
    && isInteger(value.total)
    && isInteger(value.limit)
    && isInteger(value.offset);
}

function isJobDraft(value: unknown): value is JobDraft {
  return isObject(value)
    && isString(value.company_name)
    && isString(value.role_title)
    && Array.isArray(value.must_have)
    && value.must_have.every(isRequirement)
    && Array.isArray(value.nice_to_have)
    && value.nice_to_have.every(isRequirement)
    && isStringArray(value.role_direction)
    && isStringArray(value.team_tags)
    && isObject(value.location)
    && isStringArray(value.location.cities)
    && isString(value.location.remote_policy)
    && typeof value.location.relocation_supported === "boolean"
    && isStringArray(value.seniority_requirement)
    && isString(value.product_stage)
    && isStringArray(value.evaluation_focus);
}

function isJobParseData(value: unknown): value is JobParseData {
  return isObject(value)
    && isJobDraft(value.draft)
    && (value.record === null || (isObject(value.record) && isString(value.record.job_id) && isJobDraft(value.record)))
    && isExtraction(value.extraction);
}

function isDemoSamples(value: unknown): value is DemoSamples {
  return isObject(value)
    && value.data_origin === "synthetic_sandbox"
    && isString(value.candidate_text)
    && isString(value.job_text);
}

function isIndex(value: unknown): value is DemoIndexData {
  return isObject(value)
    && value.document_version === "retrieval_doc_v4"
    && isString(value.candidate_collection)
    && isString(value.job_collection)
    && isInteger(value.candidate_count)
    && isInteger(value.job_count);
}

function isMatchResult(value: unknown): value is DemoMatchResult {
  return isObject(value)
    && isInteger(value.match_result_id)
    && isString(value.candidate_id)
    && isInteger(value.result_rank)
    && isInteger(value.retrieval_rank)
    && isInteger(value.ltr_rank)
    && isNumber(value.ltr_score_raw)
    && isNullableNumber(value.cross_encoder_rank)
    && isNullableNumber(value.cross_encoder_score_raw)
    && isNullableNumber(value.skill_fit_score)
    && isNullableNumber(value.project_evidence_score)
    && isNullableNumber(value.role_direction_score)
    && isNullableNumber(value.location_score)
    && isNullableNumber(value.seniority_score)
    && isObject(value.feature_diagnostics);
}

function isMatchRun(value: unknown): value is DemoMatchRun {
  return isObject(value)
    && isString(value.run_id)
    && isString(value.requested_job_id)
    && isString(value.job_id)
    && value.ranking_variant === "ltr"
    && value.status === "COMPLETED"
    && isString(value.created_at)
    && isString(value.completed_at)
    && isInteger(value.result_count)
    && isString(value.result_fingerprint)
    && /^[a-f0-9]{64}$/.test(value.result_fingerprint)
    && Array.isArray(value.results)
    && value.results.every(isMatchResult)
    && Array.isArray(value.steps)
    && value.steps.every((step) => isObject(step)
      && isInteger(step.sequence)
      && isString(step.step_name)
      && isString(step.status)
      && (step.duration_ms === null || isNumber(step.duration_ms)));
}

function isEvidenceText(value: unknown): value is { text: string; evidence_refs: string[] } {
  return isObject(value) && isString(value.text) && isStringArray(value.evidence_refs);
}

function isMissingSkill(value: unknown): boolean {
  return isObject(value)
    && isString(value.requirement_id)
    && isString(value.requirement_text)
    && (value.priority === "must_have" || value.priority === "nice_to_have")
    && (value.status === "partial" || value.status === "missing")
    && ["available", "claim_only", "absent", "not_assessed"].includes(String(value.evidence_status))
    && isStringArray(value.evidence_refs);
}

function isExplanation(value: unknown): value is DemoExplanation {
  return isObject(value)
    && isInteger(value.match_explanation_id)
    && value.output_schema_version === "explanation_output_v1"
    && isString(value.candidate_id)
    && isInteger(value.result_rank)
    && isEvidenceText(value.summary)
    && Array.isArray(value.match_reasons)
    && value.match_reasons.every((reason) => isObject(reason) && isString(reason.category) && isEvidenceText(reason))
    && Array.isArray(value.risk_points)
    && value.risk_points.every(isEvidenceText)
    && Array.isArray(value.missing_skills)
    && value.missing_skills.every(isMissingSkill)
    && Array.isArray(value.interview_questions)
    && value.interview_questions.every((item) => isObject(item) && isString(item.question) && isStringArray(item.evidence_refs));
}

function isExplanationRun(value: unknown): value is DemoExplanationRun {
  return isObject(value)
    && isString(value.explanation_run_id)
    && isString(value.match_run_id)
    && value.status === "COMPLETED"
    && isInteger(value.explanation_count)
    && (value.created_at === null || isString(value.created_at))
    && (value.completed_at === null || isString(value.completed_at))
    && Array.isArray(value.explanations)
    && value.explanations.every(isExplanation);
}

function apiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (!configured) {
    throw new DemoApiError("后端 API 尚未配置。", 0, "api_unconfigured", null);
  }
  return configured.replace(/\/$/, "");
}

async function request<T>(path: string, validator: Validator<T>, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}${path}`, {
      cache: "no-store",
      headers: { Accept: "application/json", "Content-Type": "application/json", ...init?.headers },
      ...init,
    });
  } catch {
    throw new DemoApiError("无法连接后端，请确认本地服务已启动。", 0, "network_error", null);
  }
  let decoded: unknown;
  try {
    decoded = await response.json();
  } catch {
    throw new DemoApiError("后端返回了无法读取的响应。", response.status, "invalid_response", null);
  }
  if (!isObject(decoded) || typeof decoded.success !== "boolean" || !isString(decoded.request_id)) {
    throw new DemoApiError("后端响应不符合契约。", response.status, "invalid_response", null);
  }
  const error = isObject(decoded.error) ? decoded.error : null;
  if (!response.ok || !decoded.success || decoded.data === null) {
    throw new DemoApiError(
      isString(error?.message) ? error.message : "请求未完成，请重试。",
      response.status,
      isString(error?.code) ? error.code : "request_failed",
      decoded.request_id,
    );
  }
  if (decoded.error !== null || !validator(decoded.data)) {
    throw new DemoApiError("后端响应不符合契约。", response.status, "invalid_response", decoded.request_id);
  }
  return decoded.data;
}

export async function fetchDemoSamples(): Promise<DemoSamples> {
  return request("/api/v1/demo/samples", isDemoSamples);
}

export async function listCandidates(limit = 100, offset = 0): Promise<CandidatePage> {
  return request(`/api/v1/candidates?limit=${limit}&offset=${offset}`, isCandidatePage);
}

export async function previewCandidate(text: string): Promise<CandidateParseData> {
  return request("/api/v1/candidates/parse", isCandidateParseData, {
    method: "POST",
    body: JSON.stringify({ text, persist: false }),
  });
}

export async function addCandidateToPool(text: string): Promise<CandidatePoolAddition> {
  const candidate = await request("/api/v1/candidates/parse", isCandidateParseData, {
    method: "POST",
    body: JSON.stringify({ text, persist: true }),
  });
  if (!candidate.record) {
    throw new DemoApiError("候选人档案未持久化。", 200, "invalid_response", null);
  }
  const index = await request("/api/v1/demo/rebuild-retrieval-index", isIndex, {
    method: "POST",
    body: JSON.stringify({ confirm: true }),
  });
  return { candidate, index };
}

export async function runDemo({
  jobText,
  onStage,
}: {
  jobText: string;
  onStage?: (stage: DemoStage) => void;
}): Promise<DemoRun> {
  onStage?.("job");
  const job = await request("/api/v1/jobs/parse", isJobParseData, {
    method: "POST",
    body: JSON.stringify({ text: jobText, persist: true }),
  });
  if (!job.record) {
    throw new DemoApiError("岗位档案未持久化。", 200, "invalid_response", null);
  }

  onStage?.("index");
  const index = await request("/api/v1/demo/rebuild-retrieval-index", isIndex, {
    method: "POST",
    body: JSON.stringify({ confirm: true }),
  });

  onStage?.("ranking");
  const matchRun = await request("/api/v1/match-runs", isMatchRun, {
    method: "POST",
    body: JSON.stringify({
      job_id: job.record.job_id,
      ranking_variant: "ltr",
      candidate_pool_k: 20,
      top_k: 5,
    }),
  });

  onStage?.("explanation");
  const explanationRun = await request(
    `/api/v1/match-runs/${encodeURIComponent(matchRun.run_id)}/explanations`,
    isExplanationRun,
    { method: "POST", body: JSON.stringify({ top_k: 5 }) },
  );

  onStage?.("complete");
  return { job, index, matchRun, explanationRun };
}
