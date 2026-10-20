import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RequirementReviewScreen } from "./requirement-review-screen";

vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams(window.location.search) }));

const mocks = vi.hoisted(() => ({ loadRun: vi.fn(), loadReview: vi.fn() }));
vi.mock("@/lib/trusted-recruiter", async (original) => ({ ...(await original<typeof import("@/lib/trusted-recruiter")>()), loadTrustedRecruiterRun: mocks.loadRun }));
vi.mock("@/lib/requirement-review", async (original) => ({ ...(await original<typeof import("@/lib/requirement-review")>()), loadRequirementReview: mocks.loadReview }));

const fingerprint = "a".repeat(64);
const sampleRun = { matchRun: { run_id: "run-1", result_fingerprint: fingerprint, results: [{ candidate_id: "cand-1", result_rank: 1 }] },
  explanationRun: { explanation_run_id: "ex-1", explanations: [{ match_explanation_id: 42, candidate_id: "cand-1", result_rank: 1 }] },
  briefs: [{ source_explanation_id: 42, candidate_id: "cand-1", result_rank: 1, source_output_fingerprint: fingerprint, source_bundle_fingerprint: fingerprint }],
  job: { role_title: "Edited later", must_have: [{ requirement_id: "req-python", text: "Changed later" }, { requirement_id: "req-search", text: "Search systems" }], nice_to_have: [] }, candidates: { "cand-1": { name: "Candidate 1", projects: [{ project_id: "p1", name: "RAG Demo" }], project_evidence: [] } } };
const sampleReview = { contract_version: "requirement_review_v1", role_title: "AI Engineer at run time", match_run_id: "run-1", explanation_run_id: "ex-1", source_explanation_id: 42,
  candidate_id: "cand-1", result_rank: 1, ranking_fingerprint: fingerprint, source_output_fingerprint: fingerprint, source_bundle_fingerprint: fingerprint,
  source_descriptors: [{ evidence_ref: "candidate:1:project:p1", source_kind: "historical_project", description: "历史项目 p1 · 技术栈 Python、FastAPI" }],
  cross_requirement_propositions: [], requirements: [{ requirement_id: "req-python", priority: "must_have", text: "Python",
    diagnostic_status: "matched", evidence_status: "available", source_refs: ["job_requirement:req-python"],
    propositions: [{ proposition_id: "prop-12345678", candidate_id: "cand-1", result_rank: 1, kind: "technical_alignment", subject: "candidate_material", predicate: "overlaps_job_requirement", modality: "alignment", polarity: "affirmative", topic_terms: ["Python"], job_requirement_terms: ["Python"], source_fact_ids: ["fact-1"], source_claim_ids: [], allowed_fields: ["why_consider"], evidence_refs: ["candidate:1:project:p1", "job_requirement:req-python"], job_requirement_refs: ["job_requirement:req-python"] }] },
    { requirement_id: "req-search", priority: "must_have", text: "Search systems", diagnostic_status: "not_assessed", evidence_status: "not_assessed", source_refs: ["job_requirement:req-search"], propositions: [] }] };

beforeEach(() => { window.history.replaceState(null, "", "/requirement-review?runId=run-1&explanationId=42"); mocks.loadRun.mockResolvedValue(sampleRun); mocks.loadReview.mockResolvedValue(sampleReview); });
afterEach(() => { cleanup(); mocks.loadRun.mockReset(); mocks.loadReview.mockReset(); window.history.replaceState(null, "", "/"); });

describe("Requirement Review Workbench", () => {
  it("shows canonical must-haves and honest unknowns with a source drill-down", async () => {
    render(<RequirementReviewScreen />);
    expect(await screen.findByRole("heading", { name: "逐项核实岗位核心要求。" })).toBeTruthy();
    expect(await screen.findByText("Search systems")).toBeTruthy();
    expect(screen.getByText(/未知不等于缺少能力/)).toBeTruthy();
    fireEvent.click(screen.getByText("查看来源元数据"));
    expect(screen.getByText(/candidate:1:project:p1/)).toBeTruthy();
    expect(screen.getByText(/历史项目 p1 · 技术栈 Python、FastAPI/)).toBeTruthy();
    expect(document.body.textContent).not.toContain("RAG Demo");
    expect(screen.getByText(/岗位原文 · Python/)).toBeTruthy();
    expect(document.body.textContent).not.toContain("Changed later");
    expect(screen.getByText(/AI Engineer at run time/)).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/匹配概率|录用建议/);
    expect(mocks.loadRun).toHaveBeenCalledWith("run-1", "ex-1");
  });
  it("does not show a trusted matrix after an API failure", async () => {
    mocks.loadReview.mockRejectedValue(new Error("private internal details"));
    render(<RequirementReviewScreen />);
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.queryByText("Search systems")).toBeNull();
    expect(document.body.textContent).not.toContain("private internal details");
  });
  it("does not retain a previous explanation when the same route changes query", async () => {
    const secondRun = { ...sampleRun,
      explanationRun: { ...sampleRun.explanationRun, explanations: [{ match_explanation_id: 43, candidate_id: "cand-1", result_rank: 1 }] },
      briefs: [{ ...sampleRun.briefs[0], source_explanation_id: 43 }],
    };
    mocks.loadRun.mockResolvedValueOnce(sampleRun).mockResolvedValueOnce(secondRun);
    mocks.loadReview.mockResolvedValueOnce(sampleReview).mockResolvedValueOnce({
      ...sampleReview, source_explanation_id: 43, role_title: "Second role",
      requirements: [{ ...sampleReview.requirements[1], text: "Second requirement" }], source_descriptors: [],
    });
    const view = render(<RequirementReviewScreen />);
    expect(await screen.findByText("Search systems")).toBeTruthy();
    window.history.pushState(null, "", "/requirement-review?runId=run-1&explanationId=43");
    view.rerender(<RequirementReviewScreen />);
    expect(await screen.findByText("Second requirement")).toBeTruthy();
    expect(screen.queryByText("Search systems")).toBeNull();
    expect(screen.getByText(/Second role/)).toBeTruthy();
  });
});
