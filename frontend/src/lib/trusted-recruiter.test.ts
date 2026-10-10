import { describe, expect, it } from "vitest";
import { assertTrustedBriefs, reviewActionLabel, propositionLabel, primaryVerificationTarget, verificationPrompt } from "./trusted-recruiter";
import type { RecruiterProposition, StructuredRecruiterBrief } from "@/types/trusted-recruiter";

const proposition = (overrides = {}): RecruiterProposition => ({
  proposition_id: "prop-12345678", candidate_id: "cand_019", result_rank: 1,
  kind: "human_review_recommendation", subject: "human_review", predicate: "prioritize_technical_review",
  modality: "recommendation", polarity: "undetermined", topic_terms: ["FastAPI"],
  job_requirement_terms: ["FastAPI"], source_fact_ids: ["fact-1"], source_claim_ids: [],
  evidence_refs: ["candidate:1:project:one"], job_requirement_refs: ["job_requirement:req_fastapi"],
  allowed_fields: ["decision_summary", "why_consider"], ...overrides,
}) as RecruiterProposition;
const brief = (overrides = {}): StructuredRecruiterBrief => ({
  contract_version: "structured_recruiter_brief_v1", review_status: "TRUSTED_STRUCTURED",
  match_run_id: "run-1", explanation_run_id: "ex-1", source_explanation_id: 21,
  candidate_id: "cand_019", result_rank: 1, ranking_fingerprint: "a".repeat(64),
  source_output_fingerprint: "b".repeat(64), source_bundle_fingerprint: "c".repeat(64),
  review_action: proposition() as StructuredRecruiterBrief["review_action"], why_review: [],
  technical_signals: [], unknowns: [], verification_targets: [], ...overrides,
});
const run = { run_id: "run-1", result_fingerprint: "a".repeat(64),
  results: [{ candidate_id: "cand_019", result_rank: 1 }] };
const explanation = { explanation_run_id: "ex-1", match_run_id: "run-1", status: "COMPLETED",
  explanations: [{ match_explanation_id: 21, candidate_id: "cand_019", result_rank: 1 }] };

describe("trusted recruiter read model", () => {
  it("accepts exact persisted run, explanation and proposition ownership", () => {
    expect(assertTrustedBriefs(run, explanation, [brief()])).toHaveLength(1);
  });
  it.each([
    ["cross candidate", { candidate_id: "cand_033" }],
    ["rank mismatch", { result_rank: 2 }],
    ["fingerprint mismatch", { ranking_fingerprint: "d".repeat(64) }],
    ["cross run", { match_run_id: "different" }],
    ["cross explanation", { source_explanation_id: 99 }],
  ])("rejects %s", (_name, change) => {
    expect(() => assertTrustedBriefs(run, explanation, [brief(change)])).toThrow();
  });
  it("rejects missing or duplicate briefs, and cross-candidate propositions", () => {
    expect(() => assertTrustedBriefs(run, explanation, [])).toThrow();
    expect(() => assertTrustedBriefs(run, explanation, [brief(), brief()])).toThrow();
    expect(() => assertTrustedBriefs(run, explanation, [brief({
      technical_signals: [proposition({ candidate_id: "cand_033" })],
    })])).toThrow();
    expect(() => assertTrustedBriefs(run, explanation, [brief({
      technical_signals: [proposition({ evidence_refs: ["candidate:2:project:foreign"] })],
    })])).toThrow();
  });
  it("does not turn ranking order into recommendation strength", () => {
    expect(reviewActionLabel(brief().review_action)).toBe("优先人工技术复核");
    expect(reviewActionLabel(proposition({ predicate: "consider_targeted_screen" }) as StructuredRecruiterBrief["review_action"])).toBe("先做定向筛查");
    expect(reviewActionLabel(null)).toBe("人工评估");
  });
  it("keeps unknowns and technical facts at source strength", () => {
    expect(propositionLabel(proposition({ kind: "material_unknown", predicate: "requirement_evidence_not_established", topic_terms: ["Retrieval"] }) as NonNullable<StructuredRecruiterBrief["review_action"]>)).toContain("尚待核实");
    expect(propositionLabel(proposition({ kind: "project_observation", predicate: "lists_project_technologies", topic_terms: ["Docker"] }) as NonNullable<StructuredRecruiterBrief["review_action"]>)).toContain("项目材料列出");
  });
  it("prefers a verification target tied to the most important unknown", () => {
    const broadScope = proposition({ kind: "interview_target", predicate: "verify_project_scope", job_requirement_refs: [], topic_terms: ["Docker", "FastAPI"] });
    const jobTarget = proposition({ kind: "interview_target", predicate: "verify_open_requirement", job_requirement_refs: ["job_requirement:req_search"], topic_terms: ["Retrieval"] });
    const unknown = proposition({ kind: "material_unknown", predicate: "requirement_evidence_not_established", job_requirement_refs: ["job_requirement:req_search"] });
    expect(primaryVerificationTarget(brief({ verification_targets: [broadScope, jobTarget] }), [unknown])?.predicate).toBe("verify_open_requirement");
  });
  it("asks for evidence without presupposing responsibility or repeating a long JD", () => {
    const target = proposition({ kind: "interview_target", predicate: "verify_open_requirement", topic_terms: ["Retrieval"], job_requirement_terms: ["A very long JD requirement"] });
    expect(verificationPrompt(target)).toBe("先确认是否有与「Retrieval」相关、可说明的证据。");
    expect(verificationPrompt(target)).not.toMatch(/负责|主导|已具备/);
  });
});
