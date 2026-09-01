export type DemoStage =
  | "candidate"
  | "job"
  | "index"
  | "ranking"
  | "explanation"
  | "complete";

export type ExtractionMetadata = {
  provider: string;
  provider_kind: "mock" | "openai_compatible";
  attempts: number;
  repaired: boolean;
  persisted: boolean;
  input_fingerprint: string;
};

export type CandidateDraft = {
  name: string;
  skills: Array<{ name: string; category: string; self_reported_level: string }>;
  projects: Array<{
    project_id: string;
    name: string;
    summary: string;
    role: string;
    technologies: string[];
    outcomes: string[];
    skills_demonstrated: string[];
  }>;
  project_evidence: Array<{
    evidence_id: string;
    project_id: string;
    supports_skills: string[];
    evidence_type: string;
    statement: string;
    artifact_ref: string | null;
    verification_status: string;
  }>;
  github_url: string | null;
  ai_tools: string[];
  target_roles: string[];
  preferred_locations: { cities: string[]; remote_policy: string; relocation_open: boolean };
  seniority: string;
  work_style: { team_stage_preference: string[]; collaboration_style: string };
  missing_fields: string[];
  overclaim_risk: { level: string; reasons: string[] };
};

export type JobDraft = {
  company_name: string;
  role_title: string;
  must_have: Array<{
    requirement_id: string;
    text: string;
    category: string;
    evidence_expectation: string;
  }>;
  nice_to_have: Array<{
    requirement_id: string;
    text: string;
    category: string;
    evidence_expectation: string;
  }>;
  role_direction: string[];
  team_tags: string[];
  location: { cities: string[]; remote_policy: string; relocation_supported: boolean };
  seniority_requirement: string[];
  product_stage: string;
  evaluation_focus: string[];
};

export type CandidateParseData = {
  draft: CandidateDraft;
  record: ({ candidate_id: string } & CandidateDraft) | null;
  extraction: ExtractionMetadata;
};

export type JobParseData = {
  draft: JobDraft;
  record: ({ job_id: string } & JobDraft) | null;
  extraction: ExtractionMetadata;
};

export type DemoIndexData = {
  document_version: "retrieval_doc_v4";
  candidate_collection: string;
  job_collection: string;
  candidate_count: number;
  job_count: number;
};

export type DemoMatchResult = {
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

export type DemoMatchRun = {
  run_id: string;
  requested_job_id: string;
  job_id: string;
  ranking_variant: "ltr";
  status: "COMPLETED";
  created_at: string;
  completed_at: string;
  result_count: number;
  result_fingerprint: string;
  results: DemoMatchResult[];
  steps: Array<{
    sequence: number;
    step_name: string;
    status: string;
    duration_ms: number | null;
  }>;
};

export type DemoExplanation = {
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

export type DemoExplanationRun = {
  explanation_run_id: string;
  match_run_id: string;
  status: "COMPLETED";
  explanation_count: number;
  created_at: string | null;
  completed_at: string | null;
  explanations: DemoExplanation[];
};

export type DemoRun = {
  candidate: CandidateParseData;
  job: JobParseData;
  index: DemoIndexData;
  matchRun: DemoMatchRun;
  explanationRun: DemoExplanationRun;
};

export type DemoSamples = {
  data_origin: "synthetic_sandbox";
  candidate_text: string;
  job_text: string;
};
