import type { RecruiterProposition } from "./trusted-recruiter";

export type RequirementReviewRow = {
  requirement_id: string;
  priority: "must_have" | "nice_to_have";
  text: string;
  diagnostic_status: "matched" | "partial" | "missing" | "not_assessed";
  evidence_status: "available" | "claim_only" | "absent" | "not_assessed";
  source_refs: string[];
  propositions: RecruiterProposition[];
};
export type RequirementSourceDescriptor = {
  evidence_ref: string;
  source_kind: "historical_skill_claim" | "historical_project" | "historical_project_record";
  description: string;
};
export type RequirementReview = {
  contract_version: "requirement_review_v1";
  role_title: string;
  match_run_id: string; explanation_run_id: string; source_explanation_id: number;
  candidate_id: string; result_rank: number; ranking_fingerprint: string;
  source_output_fingerprint: string; source_bundle_fingerprint: string;
  requirements: RequirementReviewRow[];
  source_descriptors: RequirementSourceDescriptor[];
  cross_requirement_propositions: RecruiterProposition[];
};
