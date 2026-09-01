import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DemoApiError } from "@/lib/demo-api";
import type { DemoRun } from "@/types/demo";

import { MatchingResultsScreen } from "./matching-results-screen";


const apiMocks = vi.hoisted(() => ({ fetchDemoSamples: vi.fn(), runDemo: vi.fn() }));

vi.mock("@/lib/demo-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/demo-api")>()),
  fetchDemoSamples: apiMocks.fetchDemoSamples,
  runDemo: apiMocks.runDemo,
}));

const candidateDraft = {
  name: "Candidate Parse Demo",
  skills: [{ name: "Python", category: "backend", self_reported_level: "advanced" }],
  projects: [{
    project_id: "project-1", name: "Matching Console Sandbox",
    summary: "Built a local matching console with deterministic tests.", role: "Project developer",
    technologies: ["Python", "FastAPI"], outcomes: ["Documented evaluation workflow"],
    skills_demonstrated: ["Python"],
  }],
  project_evidence: [{
    evidence_id: "evidence-1", project_id: "project-1", supports_skills: ["Python"],
    evidence_type: "tests", statement: "The synthetic test suite demonstrates matching behavior.",
    artifact_ref: "sandbox://demo/tests", verification_status: "available",
  }],
  github_url: null,
  ai_tools: ["FastAPI"],
  target_roles: ["AI Matching Engineer"],
  preferred_locations: { cities: ["Shanghai"], remote_policy: "hybrid", relocation_open: false },
  seniority: "mid",
  work_style: { team_stage_preference: ["zero_to_one"], collaboration_style: "Collaborative" },
  missing_fields: ["years_of_experience"],
  overclaim_risk: { level: "low", reasons: [] },
};

const jobDraft = {
  company_name: "Northstar Sandbox Labs", role_title: "AI Matching Engineer",
  must_have: [{ requirement_id: "requirement-1", text: "Build matching foundations", category: "role_direction", evidence_expectation: "A working project" }],
  nice_to_have: [], role_direction: ["matching"], team_tags: ["zero_to_one"],
  location: { cities: ["Shanghai"], remote_policy: "hybrid", relocation_supported: true },
  seniority_requirement: ["mid"], product_stage: "zero_to_one", evaluation_focus: ["project evidence"],
};

const demoRun = {
  candidate: {
    draft: candidateDraft, record: { candidate_id: "cand_parse_demo", ...candidateDraft },
    extraction: { provider: "deterministic_mock", provider_kind: "mock", attempts: 1, repaired: false, persisted: true, input_fingerprint: "a".repeat(64) },
  },
  job: {
    draft: jobDraft, record: { job_id: "job_parse_demo", ...jobDraft },
    extraction: { provider: "deterministic_mock", provider_kind: "mock", attempts: 1, repaired: false, persisted: true, input_fingerprint: "b".repeat(64) },
  },
  index: { document_version: "retrieval_doc_v4", candidate_collection: "candidates", job_collection: "jobs", candidate_count: 49, job_count: 25 },
  matchRun: {
    run_id: "run-demo", requested_job_id: "job_parse_demo", job_id: "job_parse_demo", ranking_variant: "ltr",
    status: "COMPLETED", created_at: "2026-09-01T00:00:00Z", completed_at: "2026-09-01T00:00:01Z",
    result_count: 2, result_fingerprint: "c".repeat(64),
    results: [
      { match_result_id: 41, candidate_id: "cand_parse_demo", result_rank: 1, retrieval_rank: 3, ltr_rank: 1, ltr_score_raw: 1.254321, cross_encoder_rank: null, cross_encoder_score_raw: null, skill_fit_score: 0.9, project_evidence_score: 0.8, role_direction_score: 0.7, location_score: 1, seniority_score: 0.5, feature_diagnostics: {} },
      { match_result_id: 42, candidate_id: "candidate_002", result_rank: 2, retrieval_rank: 1, ltr_rank: 2, ltr_score_raw: 0.875, cross_encoder_rank: null, cross_encoder_score_raw: null, skill_fit_score: 0.8, project_evidence_score: 0.6, role_direction_score: 0.7, location_score: 1, seniority_score: 1, feature_diagnostics: {} },
    ],
    steps: [
      { sequence: 1, step_name: "retrieve_candidates", status: "COMPLETED", duration_ms: 12.5 },
      { sequence: 2, step_name: "rank_candidates", status: "COMPLETED", duration_ms: 4.5 },
    ],
  },
  explanationRun: {
    explanation_run_id: "explanation-demo", match_run_id: "run-demo", status: "COMPLETED", explanation_count: 2,
    created_at: "2026-09-01T00:00:01Z", completed_at: "2026-09-01T00:00:02Z",
    explanations: [
      { match_explanation_id: 51, output_schema_version: "explanation_output_v1", candidate_id: "cand_parse_demo", result_rank: 1, summary: { text: "结构化项目证据支持该候选人的当前排名。", evidence_refs: ["candidate:1:project:1"] }, match_reasons: [{ category: "skill_fit", text: "技能与岗位要求有记录内重合。", evidence_refs: ["candidate:1:skill:1"] }], risk_points: [], missing_skills: [{ requirement_id: "requirement-1", requirement_text: "incident response", priority: "nice_to_have", status: "missing", evidence_status: "absent", evidence_refs: ["job_requirement:1"] }], interview_questions: [{ question: "请说明一次排序坏案例复盘。", evidence_refs: ["candidate:1:project:1"] }], why_not_top1: null },
      { match_explanation_id: 52, output_schema_version: "explanation_output_v1", candidate_id: "candidate_002", result_rank: 2, summary: { text: "该候选人保留在第二位。", evidence_refs: ["candidate:2:ranking:1"] }, match_reasons: [], risk_points: [], missing_skills: [], interview_questions: [], why_not_top1: null },
    ],
  },
} satisfies DemoRun;

afterEach(() => {
  cleanup();
  apiMocks.fetchDemoSamples.mockReset();
  apiMocks.runDemo.mockReset();
});

describe("MatchingResultsScreen Phase 12 demo", () => {
  it("opens as a Chinese-first evidence-aware product instead of a score mock", () => {
    render(<MatchingResultsScreen />);
    expect(screen.getByRole("heading", { name: "Evidence-aware 人岗匹配" })).toBeTruthy();
    expect(screen.getByText(/LLM 负责结构化与解释，不直接决定排序/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "加载安全示例" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "开始完整匹配" })).toBeTruthy();
    expect(screen.getByLabelText("候选人简历文本")).toBeTruthy();
    expect(screen.getByLabelText("岗位描述文本")).toBeTruthy();
    expect(screen.getByText("尚未运行匹配")).toBeTruthy();
    expect(document.body.textContent).not.toContain("Design Mock");
    expect(document.body.textContent).not.toContain("Final score");
  });

  it("loads the exact synthetic fixture and keeps it editable", async () => {
    const user = userEvent.setup();
    apiMocks.fetchDemoSamples.mockResolvedValue({ data_origin: "synthetic_sandbox", candidate_text: "Synthetic candidate fixture\n", job_text: "Synthetic job fixture\n" });
    render(<MatchingResultsScreen />);
    await user.click(screen.getByRole("button", { name: "加载安全示例" }));
    expect((screen.getByLabelText("候选人简历文本") as HTMLTextAreaElement).value).toBe("Synthetic candidate fixture\n");
    expect((screen.getByLabelText("岗位描述文本") as HTMLTextAreaElement).value).toBe("Synthetic job fixture\n");
    expect(screen.getByText("示例数据为 synthetic sandbox，不包含真实个人信息。")).toBeTruthy();
  });

  it("shows real MatchRun evidence, raw margin, trace, and grounded explanation", async () => {
    const user = userEvent.setup();
    apiMocks.runDemo.mockImplementation(async ({ onStage }) => {
      for (const stage of ["candidate", "job", "index", "ranking", "explanation", "complete"] as const) onStage?.(stage);
      return demoRun;
    });
    render(<MatchingResultsScreen />);
    fireEvent.change(screen.getByLabelText("候选人简历文本"), { target: { value: "candidate source ".repeat(8) } });
    fireEvent.change(screen.getByLabelText("岗位描述文本"), { target: { value: "job source ".repeat(10) } });
    await user.click(screen.getByRole("button", { name: "开始完整匹配" }));
    expect(screen.getByRole("heading", { name: "AI Matching Engineer" })).toBeTruthy();
    expect(screen.getByText("本次输入候选人")).toBeTruthy();
    expect(screen.getAllByText("1.254321")).toHaveLength(2);
    expect(screen.getByText("raw LTR margin，不是概率")).toBeTruthy();
    expect(screen.getByText("结构化项目证据支持该候选人的当前排名。")).toBeTruthy();
    expect(screen.getByText("candidate:1:project:1")).toBeTruthy();
    expect(screen.getByText("run-demo")).toBeTruthy();
    expect(screen.getByText("retrieve_candidates")).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/准确率|95\.9%|final score/i);
    await user.click(screen.getByRole("button", { name: /查看第 2 名/ }));
    expect(screen.getAllByText("0.875000")).toHaveLength(2);
    expect(screen.getByText("该候选人保留在第二位。")).toBeTruthy();
  });

  it("surfaces a recoverable provider error without stack or secret material", async () => {
    const user = userEvent.setup();
    apiMocks.runDemo.mockRejectedValue(new DemoApiError("Extraction provider is unavailable", 503, "provider_unavailable", "request-safe"));
    render(<MatchingResultsScreen />);
    fireEvent.change(screen.getByLabelText("候选人简历文本"), { target: { value: "candidate source ".repeat(8) } });
    fireEvent.change(screen.getByLabelText("岗位描述文本"), { target: { value: "job source ".repeat(10) } });
    await user.click(screen.getByRole("button", { name: "开始完整匹配" }));
    const alert = screen.getByRole("alert");
    expect(alert.textContent).toContain("模型服务暂不可用");
    expect(alert.textContent).toContain("request-safe");
    expect(alert.textContent).not.toMatch(/traceback|bearer|api[_-]?key/i);
    expect(screen.getByRole("button", { name: "重新尝试" })).toBeTruthy();
  });

  it("preserves the persisted Phase 10 review entry as a separate historical workflow", async () => {
    const user = userEvent.setup();
    render(<MatchingResultsScreen />);
    const trigger = screen.getByRole("button", { name: "复核历史结果" });
    trigger.focus();
    await user.click(trigger);
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText(/只针对已持久化的历史 MatchRun/)).toBeTruthy();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });
});
