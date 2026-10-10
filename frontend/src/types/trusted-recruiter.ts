import type { CandidateRecord, JobDraft } from "./demo";
import type { ExplanationRunDetail, MatchRunDetail } from "./phase10";

export type RecruiterProposition = {
  proposition_id: string;
  candidate_id: string;
  result_rank: number;
  kind: "project_observation" | "listed_skill_observation" | "technical_alignment" | "interview_target" | "material_unknown" | "human_review_recommendation";
  subject: string;
  predicate: string;
  modality: string;
  polarity: string;
  topic_terms: string[];
  job_requirement_terms: string[];
  source_fact_ids: string[];
  source_claim_ids: string[];
  evidence_refs: string[];
  job_requirement_refs: string[];
  allowed_fields: string[];
};

export type StructuredRecruiterBrief = {
  contract_version: "structured_recruiter_brief_v1";
  review_status: "TRUSTED_STRUCTURED";
  match_run_id: string;
  explanation_run_id: string;
  source_explanation_id: number;
  candidate_id: string;
  result_rank: number;
  ranking_fingerprint: string;
  source_output_fingerprint: string;
  source_bundle_fingerprint: string;
  review_action: RecruiterProposition | null;
  why_review: RecruiterProposition[];
  technical_signals: RecruiterProposition[];
  unknowns: RecruiterProposition[];
  verification_targets: RecruiterProposition[];
};

export type TrustedRecruiterRun = {
  matchRun: MatchRunDetail & { result_fingerprint: string };
  explanationRun: ExplanationRunDetail;
  briefs: StructuredRecruiterBrief[];
  job: JobDraft;
  candidates: Record<string, CandidateRecord>;
};
