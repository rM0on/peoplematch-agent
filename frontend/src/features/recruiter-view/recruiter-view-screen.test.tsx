import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RecruiterViewScreen } from "./recruiter-view-screen";
import type { TrustedRecruiterRun } from "@/types/trusted-recruiter";

const mocks = vi.hoisted(() => ({ load: vi.fn(), list: vi.fn() }));
vi.mock("@/lib/trusted-recruiter", async (importOriginal) => ({ ...(await importOriginal<typeof import("@/lib/trusted-recruiter")>()), loadTrustedRecruiterRun: mocks.load }));
vi.mock("@/lib/phase10-api", () => ({ listCompletedMatchRuns: mocks.list }));

const proposition = (kind: "technical_alignment" | "material_unknown" | "interview_target" | "project_observation", predicate: string) => ({
  proposition_id: `prop-${kind}`, candidate_id: "cand_019", result_rank: 1, kind, subject: "candidate_material", predicate,
  modality: "alignment", polarity: "affirmative", topic_terms: ["Retrieval"], job_requirement_terms: ["Search systems"],
  source_fact_ids: ["fact-1"], source_claim_ids: [], evidence_refs: ["candidate:1:project:prj_1"],
  job_requirement_refs: ["job_requirement:req_search"], allowed_fields: ["technical_signal"],
});
const sample = {
  matchRun: { run_id: "run-1", status: "COMPLETED", result_fingerprint: "a".repeat(64), results: [{ match_result_id: 1, candidate_id: "cand_019", result_rank: 1, retrieval_rank: 2, ltr_rank: 1, ltr_score_raw: 1.234, feature_diagnostics: {} }] },
  explanationRun: { explanation_run_id: "ex-1", status: "COMPLETED", explanations: [] },
  briefs: [{ candidate_id: "cand_019", result_rank: 1, review_action: { predicate: "prioritize_technical_review" },
    why_review: [proposition("technical_alignment", "overlaps_job_requirement")], technical_signals: [proposition("project_observation", "lists_project_technologies")],
    unknowns: [proposition("material_unknown", "requirement_evidence_not_established")], verification_targets: [proposition("interview_target", "verify_open_requirement")],
    source_explanation_id: 8 }],
  job: { role_title: "Search Engineer", company_name: "Synthetic Co", location: { cities: ["Beijing"] }, must_have: [{ requirement_id: "req_search", text: "Search systems" }], nice_to_have: [] },
  candidates: { cand_019: { candidate_id: "cand_019", name: "Candidate 019", target_roles: ["Search Engineer"], projects: [{ project_id: "prj_1", name: "Search Sandbox" }], project_evidence: [] } },
} as unknown as TrustedRecruiterRun;

beforeEach(() => { window.history.replaceState(null, "", "/?runId=run-1"); mocks.list.mockResolvedValue({ data: { items: [{ run_id: "run-1", created_at: "2026-10-09T00:00:00Z" }] } }); mocks.load.mockResolvedValue(sample); });
afterEach(() => { cleanup(); mocks.list.mockReset(); mocks.load.mockReset(); window.history.replaceState(null, "", "/"); });

describe("Recruiter View", () => {
  it("keeps an actionable empty state when no MatchRun is selected", async () => {
    window.history.replaceState(null, "", "/");
    render(<RecruiterViewScreen />);
    expect(await screen.findByText("选择一条推荐记录")).toBeTruthy();
    expect(screen.getByRole("link", { name: /岗位推荐工作台/ })).toBeTruthy();
  });
  it("reports list API failure instead of presenting a silent empty selector", async () => {
    window.history.replaceState(null, "", "/");
    mocks.list.mockRejectedValue(new Error("network failed"));
    render(<RecruiterViewScreen />);
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByRole("alert").textContent).not.toContain("network failed");
  });
  it("shows loading without inventing a trusted result", async () => {
    mocks.load.mockReturnValue(new Promise(() => {}));
    render(<RecruiterViewScreen />);
    expect(await screen.findByRole("status")).toBeTruthy();
    expect(screen.queryByRole("navigation", { name: "Top 候选人" })).toBeNull();
  });
  it("shows trusted review action and core unknown together without turning rank into probability", async () => {
    render(<RecruiterViewScreen />);
    expect(await screen.findByRole("heading", { name: "Search Engineer" })).toBeTruthy();
    expect(screen.getAllByText("优先人工技术复核").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/核心待确认/).length).toBeGreaterThan(0);
    expect(document.body.textContent).not.toMatch(/高度推荐|匹配概率|推荐录用|Strong Hire/);
    expect(screen.getByText(/项目材料列出：Retrieval/)).toBeTruthy();
    fireEvent.click(screen.getAllByText("查看依据")[0]);
    expect(screen.getAllByText(/候选项目 · Search Sandbox/).length).toBeGreaterThan(0);
  });
  it("fails closed when the structured source is unavailable", async () => {
    mocks.load.mockRejectedValue(new Error("private raw response"));
    render(<RecruiterViewScreen />);
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.queryByText(/private raw response/)).toBeNull();
  });
  it("keeps source drill-down readable when an optional display profile is missing", async () => {
    mocks.load.mockResolvedValue({ ...sample, candidates: {} });
    render(<RecruiterViewScreen />);
    await screen.findByRole("heading", { name: "Search Engineer" });
    fireEvent.click(screen.getAllByText("查看依据")[0]);
    expect(screen.getAllByText(/候选项目 · 来源已校验/).length).toBeGreaterThan(0);
  });
  it("shows a source-backed ranking feature breakdown without probability language", async () => {
    render(<RecruiterViewScreen />);
    await screen.findByRole("heading", { name: "Search Engineer" });
    fireEvent.click(screen.getByText(/Engineering View · 排序与来源轨迹/));
    expect(screen.getByText("Ranking Model Raw Score：")).toBeTruthy();
    expect(screen.getByText("技能匹配")).toBeTruthy();
    expect(screen.getByText("项目证据")).toBeTruthy();
    expect(screen.getByText(/不是概率/)).toBeTruthy();
  });
});
