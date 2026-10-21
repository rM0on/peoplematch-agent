import { describe, expect, it, vi } from "vitest";
import { assertRequirementReviewOwnership, isRequirementReview, loadRequirementReview } from "./requirement-review";
import type { RequirementReview } from "@/types/requirement-review";

const fingerprint = "a".repeat(64);
const base = {
  contract_version: "requirement_review_v1", role_title: "AI Engineer", match_run_id: "run-1", explanation_run_id: "ex-1",
  source_explanation_id: 42, candidate_id: "cand-1", result_rank: 1,
  ranking_fingerprint: fingerprint, source_output_fingerprint: fingerprint, source_bundle_fingerprint: fingerprint,
  requirements: [{ requirement_id: "req-python", priority: "must_have", text: "Python",
    diagnostic_status: "matched", evidence_status: "available", source_refs: ["job_requirement:req-python"], propositions: [] }],
  source_descriptors: [],
  cross_requirement_propositions: [],
} as RequirementReview;
const run = { matchRun: { run_id: "run-1", result_fingerprint: fingerprint, results: [{ candidate_id: "cand-1", result_rank: 1 }] },
  explanationRun: { explanation_run_id: "ex-1", explanations: [{ match_explanation_id: 42, candidate_id: "cand-1", result_rank: 1 }] },
  briefs: [{ source_explanation_id: 42, candidate_id: "cand-1", result_rank: 1, source_output_fingerprint: fingerprint, source_bundle_fingerprint: fingerprint }] };

describe("requirement review contract", () => {
  it("accepts a typed canonical response and rejects malformed rows", () => {
    expect(isRequirementReview(base)).toBe(true);
    expect(isRequirementReview({ ...base, requirements: [{ ...base.requirements[0], priority: "unknown" }] })).toBe(false);
    expect(isRequirementReview({ ...base, requirements: [{ ...base.requirements[0], source_refs: [] }] })).toBe(false);
    expect(isRequirementReview({ ...base, cross_requirement_propositions: undefined })).toBe(false);
    expect(isRequirementReview({ ...base, source_descriptors: [{ evidence_ref: "candidate:1:project:project_001", source_kind: "historical_project", description: "历史项目 project_001 · 技术栈 fastapi" }] })).toBe(false);
    expect(isRequirementReview({ ...base, source_descriptors: [{ evidence_ref: "candidate:2:project:project_001", source_kind: "historical_project", description: "foreign" }] })).toBe(false);
    const proposition = { proposition_id: "prop-12345678", candidate_id: "cand-1", result_rank: 1,
      kind: "invented", subject: "candidate_material", predicate: "overlaps_job_requirement", modality: "alignment", polarity: "affirmative",
      topic_terms: ["Python"], job_requirement_terms: ["Python"], source_fact_ids: ["fact-1"], source_claim_ids: [],
      evidence_refs: ["candidate:1:skill:python"], job_requirement_refs: ["job_requirement:req-python"], allowed_fields: ["why_consider"] };
    expect(isRequirementReview({ ...base, requirements: [{ ...base.requirements[0], propositions: [proposition] }] })).toBe(false);
    const valid = { ...proposition, kind: "technical_alignment", allowed_fields: ["why_consider", "technical_signal"],
      evidence_refs: ["candidate:1:project:project_001", "job_requirement:req-python"] };
    expect(isRequirementReview({ ...base,
      source_descriptors: [{ evidence_ref: "candidate:1:project:project_001", source_kind: "historical_project", description: "历史项目 project_001 · 技术栈 fastapi" }],
      requirements: [{ ...base.requirements[0], propositions: [valid] }],
    })).toBe(true);
    expect(isRequirementReview({ ...base,
      source_descriptors: [{ evidence_ref: "candidate:1:project:project_001", source_kind: "historical_project", description: "历史项目 project_001 · 技术栈 fastapi" }],
      requirements: [{ ...base.requirements[0], propositions: [{ ...valid,
        evidence_refs: [...valid.evidence_refs, "job_requirement:req-foreign"] }] }],
    })).toBe(false);
    expect(isRequirementReview({ ...base,
      source_descriptors: [{ evidence_ref: "candidate:1:project:project_001", source_kind: "historical_project", description: "历史项目 project_001 · 技术栈 fastapi" }],
      requirements: [{ ...base.requirements[0], propositions: [{ ...valid,
        evidence_refs: [...valid.evidence_refs, "unscoped:source"] }] }],
    })).toBe(false);
    expect(isRequirementReview({ ...base, explanation_run_id: "" })).toBe(false);
    expect(isRequirementReview({ ...base,
      source_descriptors: [{ evidence_ref: "candidate:1:project:", source_kind: "historical_project", description: "synthetic malformed source" }],
      requirements: [{ ...base.requirements[0], propositions: [{ ...valid,
        evidence_refs: ["candidate:1:project:", "job_requirement:req-python"] }] }],
    })).toBe(false);
    expect(isRequirementReview({ ...base,
      source_descriptors: [{ evidence_ref: "candidate:1:skill:python", source_kind: "historical_skill_claim", description: "synthetic malformed skill hash" }],
      requirements: [{ ...base.requirements[0], propositions: [{ ...valid,
        evidence_refs: ["candidate:1:skill:python", "job_requirement:req-python"] }] }],
    })).toBe(false);
    expect(isRequirementReview({ ...base,
      source_descriptors: [{ evidence_ref: "candidate:1:project:ok:extra", source_kind: "historical_project", description: "synthetic malformed project ID" }],
      requirements: [{ ...base.requirements[0], propositions: [{ ...valid,
        evidence_refs: ["candidate:1:project:ok:extra", "job_requirement:req-python"] }] }],
    })).toBe(false);
    expect(isRequirementReview({ ...base,
      source_descriptors: [{ evidence_ref: `candidate:1:skill:${"a".repeat(32)}`, source_kind: "historical_skill_claim", description: "synthetic valid historical skill" }],
      requirements: [{ ...base.requirements[0], propositions: [{ ...valid,
        evidence_refs: [`candidate:1:skill:${"a".repeat(32)}`, "job_requirement:req-python"] }] }],
    })).toBe(true);
    expect(isRequirementReview({ ...base,
      source_descriptors: [{ evidence_ref: "candidate:1:project:project_001", source_kind: "historical_project", description: "历史项目 project_001 · 技术栈 fastapi" }],
      requirements: [{ ...base.requirements[0], propositions: [{ ...valid,
        evidence_refs: [...valid.evidence_refs, valid.evidence_refs[0]] }] }],
    })).toBe(false);
  });
  it("fails closed on run and candidate mismatches", () => {
    expect(assertRequirementReviewOwnership(base, run)).toBe(base);
    expect(() => assertRequirementReviewOwnership({ ...base, candidate_id: "cand-2" }, run)).toThrow();
    expect(() => assertRequirementReviewOwnership({ ...base, ranking_fingerprint: "b".repeat(64) }, run)).toThrow();
    expect(() => assertRequirementReviewOwnership({ ...base, requirements: [base.requirements[0], base.requirements[0]] }, run)).toThrow();
  });
  it("rejects an otherwise valid response for a different requested explanation", async () => {
    const previous = process.env.NEXT_PUBLIC_API_BASE_URL;
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8765";
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ success: true, data: { ...base, source_explanation_id: 43 } }) }));
    try { await expect(loadRequirementReview(42)).rejects.toThrow("requirement_review_source_mismatch"); }
    finally { vi.unstubAllGlobals(); process.env.NEXT_PUBLIC_API_BASE_URL = previous; }
  });
});
