import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DemoApiError } from "@/lib/demo-api";
import type { DemoRun } from "@/types/demo";

import { MatchingResultsScreen } from "./matching-results-screen";


const apiMocks = vi.hoisted(() => ({ fetchDemoSamples: vi.fn(), runDemo: vi.fn() }));
const providerMocks = vi.hoisted(() => ({ fetchAIProviderStatus: vi.fn() }));

vi.mock("@/lib/demo-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/demo-api")>()),
  fetchDemoSamples: apiMocks.fetchDemoSamples,
  runDemo: apiMocks.runDemo,
}));

vi.mock("@/lib/provider-status-api", () => ({
  fetchAIProviderStatus: providerMocks.fetchAIProviderStatus,
}));

const mockProviderStatus = {
  extraction: { task: "extraction", mode: "mock", configured: true, provider_name: "deterministic_mock", configured_model: null, arbitrary_input_supported: false },
  explanation: { task: "explanation", mode: "mock", configured: true, provider_name: "deterministic_mock", configured_model: null, arbitrary_input_supported: false },
};

const jobDraft = {
  company_name: "Northstar Sandbox Labs", role_title: "AI Matching Engineer",
  must_have: [{ requirement_id: "requirement-1", text: "Build matching foundations", category: "role_direction", evidence_expectation: "A working project" }],
  nice_to_have: [], role_direction: ["matching"], team_tags: ["zero_to_one"],
  location: { cities: ["Shanghai"], remote_policy: "hybrid", relocation_supported: true },
  seniority_requirement: ["mid"], product_stage: "zero_to_one", evaluation_focus: ["project evidence"],
};

const demoRun = {
  job: {
    draft: jobDraft, record: { job_id: "job_parse_demo", ...jobDraft },
    extraction: { provider: "deterministic_mock", provider_kind: "mock", prompt_version: "job_extraction_prompt_v1", prompt_fingerprint: "d".repeat(64), attempts: 1, repaired: false, persisted: true, input_fingerprint: "b".repeat(64) },
  },
  index: { document_version: "retrieval_doc_v4", candidate_collection: "candidates", job_collection: "jobs", candidate_count: 49, job_count: 25 },
  matchRun: {
    run_id: "run-demo", requested_job_id: "job_parse_demo", job_id: "job_parse_demo", ranking_variant: "ltr",
    status: "COMPLETED", created_at: "2026-09-01T00:00:00Z", completed_at: "2026-09-01T00:00:01Z",
    result_count: 2, result_fingerprint: "c".repeat(64),
    results: [
      { match_result_id: 41, candidate_id: "cand_parse_demo", result_rank: 1, retrieval_rank: 3, ltr_rank: 1, ltr_score_raw: 1.254321, cross_encoder_rank: null, cross_encoder_score_raw: null, skill_fit_score: 0.9, project_evidence_score: 0.8, role_direction_score: 0.7, location_score: 1, seniority_score: 0.5, feature_diagnostics: {} },
      { match_result_id: 42, candidate_id: "cand_005", result_rank: 2, retrieval_rank: 1, ltr_rank: 2, ltr_score_raw: 0.875, cross_encoder_rank: null, cross_encoder_score_raw: null, skill_fit_score: 0.8, project_evidence_score: 0.6, role_direction_score: 0.7, location_score: 1, seniority_score: 1, feature_diagnostics: {} },
    ],
    steps: [
      { sequence: 1, step_name: "resolve_inputs", status: "COMPLETED", duration_ms: 12.5 },
      { sequence: 2, step_name: "phase6_ltr_rank", status: "COMPLETED", duration_ms: 4.5 },
      { sequence: 3, step_name: "persist_results", status: "COMPLETED", duration_ms: 1.5 },
    ],
  },
  explanationRun: {
    explanation_run_id: "explanation-demo", match_run_id: "run-demo", status: "COMPLETED", explanation_count: 2,
    created_at: "2026-09-01T00:00:01Z", completed_at: "2026-09-01T00:00:02Z",
    explanations: [
      { match_explanation_id: 51, output_schema_version: "explanation_output_v1", candidate_id: "cand_parse_demo", result_rank: 1, summary: { text: "This explanation uses recorded matching evidence.", evidence_refs: ["candidate:1:project:1"] }, match_reasons: [{ category: "skill_fit", text: "Recorded candidate and requirement evidence is available.", evidence_refs: ["candidate:1:skill:1"] }], risk_points: [{ text: "A required recorded requirement has no available evidence.", evidence_refs: ["job_requirement:1"] }], missing_skills: [{ requirement_id: "requirement-1", requirement_text: "incident response", priority: "nice_to_have", status: "missing", evidence_status: "absent", evidence_refs: ["job_requirement:1"] }], interview_questions: [{ question: "请说明一次排序坏案例复盘。", evidence_refs: ["candidate:1:project:1"] }], why_not_top1: null },
      { match_explanation_id: 52, output_schema_version: "explanation_output_v1", candidate_id: "cand_005", result_rank: 2, summary: { text: "该候选人保留在第二位。", evidence_refs: ["candidate:2:ranking:1"] }, match_reasons: [], risk_points: [], missing_skills: [], interview_questions: [], why_not_top1: null },
    ],
  },
} satisfies DemoRun;

afterEach(() => {
  cleanup();
  apiMocks.fetchDemoSamples.mockReset();
  apiMocks.runDemo.mockReset();
  providerMocks.fetchAIProviderStatus.mockReset();
});

beforeEach(() => {
  providerMocks.fetchAIProviderStatus.mockResolvedValue(mockProviderStatus);
});

describe("MatchingResultsScreen Phase 12 demo", () => {
  it("opens as a Job-query-driven recommendation system instead of a score mock", () => {
    render(<MatchingResultsScreen />);
    expect(screen.getByRole("heading", { name: "AI 人才推荐工作台" })).toBeTruthy();
    expect(screen.getByText(/岗位 JD 是推荐查询 Query/)).toBeTruthy();
    expect(screen.getAllByText(/从人才库召回候选人/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/LLM 负责结构化与解释，不直接决定排序/)).toBeTruthy();
    for (const step of ["输入岗位需求", "结构化解析", "候选召回", "特征计算", "LambdaMART 排序", "证据解释", "历史复核"]) {
      expect(screen.getByText(step)).toBeTruthy();
    }
    expect(screen.getByRole("button", { name: "加载中文 JD 示例" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "开始推荐" })).toBeTruthy();
    expect(screen.queryByLabelText("候选人简历文本")).toBeNull();
    expect(screen.getByLabelText("岗位描述文本")).toBeTruthy();
    expect(screen.getByRole("link", { name: "推荐工作台" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "人才库管理" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "推荐记录" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Bad Case 复核" })).toBeTruthy();
    for (const unavailable of ["Overview", "Candidates", "Jobs", "Runs", "Evaluation"]) {
      expect(screen.queryByRole("button", { name: unavailable })).toBeNull();
    }
    expect(screen.getByText("尚未运行推荐")).toBeTruthy();
    expect(document.body.textContent).not.toContain("Design Mock");
    expect(document.body.textContent).not.toContain("Final score");
  });

  it("loads only the synthetic JD fixture and keeps it editable", async () => {
    const user = userEvent.setup();
    apiMocks.fetchDemoSamples.mockResolvedValue({ data_origin: "synthetic_sandbox", candidate_text: "Synthetic candidate fixture\n", job_text: "Synthetic job fixture\n" });
    render(<MatchingResultsScreen />);
    await user.click(screen.getByRole("button", { name: "加载中文 JD 示例" }));
    expect(screen.queryByLabelText("候选人简历文本")).toBeNull();
    expect((screen.getByLabelText("岗位描述文本") as HTMLTextAreaElement).value).toBe("Synthetic job fixture\n");
    expect(screen.getByText("示例数据为 synthetic sandbox，不包含真实个人信息。")).toBeTruthy();
  });

  it("submits an arbitrary JD without requiring the sample helper", async () => {
    const user = userEvent.setup();
    const arbitraryJD = "招聘 AI 应用算法工程师，负责 Python、RAG、Embedding、LLM Agent 与 FastAPI 系统研发，并能完成检索排序链路的工程交付。";
    apiMocks.runDemo.mockResolvedValue(demoRun);
    render(<MatchingResultsScreen />);

    await user.type(screen.getByLabelText("岗位描述文本"), arbitraryJD);
    await user.click(screen.getByRole("button", { name: "开始推荐" }));

    expect(apiMocks.fetchDemoSamples).not.toHaveBeenCalled();
    expect(apiMocks.runDemo).toHaveBeenCalledWith(expect.objectContaining({
      jobText: arbitraryJD,
    }));
  });

  it("shows only observable recommendation stages and returns to an actionable state", async () => {
    const user = userEvent.setup();
    let reportStage: ((stage: "job" | "index" | "ranking" | "explanation" | "complete") => void) | undefined;
    let completeRun: ((value: DemoRun) => void) | undefined;
    apiMocks.runDemo.mockImplementation(({ onStage }) => {
      reportStage = onStage;
      onStage?.("job");
      return new Promise<DemoRun>((resolve) => { completeRun = resolve; });
    });
    render(<MatchingResultsScreen />);
    fireEvent.change(screen.getByLabelText("岗位描述文本"), { target: { value: "job source ".repeat(10) } });
    await user.click(screen.getByRole("button", { name: "开始推荐" }));

    expect(screen.getAllByText("正在理解岗位需求…").length).toBeGreaterThanOrEqual(1);
    act(() => reportStage?.("index"));
    expect(screen.getAllByText("正在准备候选检索…").length).toBeGreaterThanOrEqual(1);
    act(() => reportStage?.("ranking"));
    expect(screen.getAllByText("正在召回候选人并计算 LambdaMART 排序…").length).toBeGreaterThanOrEqual(1);
    act(() => reportStage?.("explanation"));
    expect(screen.getAllByText("正在生成证据约束解释…").length).toBeGreaterThanOrEqual(1);
    expect(document.body.textContent).not.toMatch(/\d+%/);
    await act(async () => completeRun?.(demoRun));
    expect(screen.getByRole("button", { name: "开始推荐" })).not.toHaveProperty("disabled", true);
  });

  it("keeps recommendation available when read-only Provider status fails", async () => {
    const user = userEvent.setup();
    providerMocks.fetchAIProviderStatus.mockRejectedValue(new Error("status offline"));
    apiMocks.runDemo.mockResolvedValue(demoRun);
    render(<MatchingResultsScreen />);

    expect(await screen.findByText("Provider 状态不可用")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("岗位描述文本"), { target: { value: "job source ".repeat(10) } });
    await user.click(screen.getByRole("button", { name: "开始推荐" }));
    expect(await screen.findByRole("heading", { name: "AI Matching Engineer" })).toBeTruthy();
  });

  it("shows real MatchRun evidence, raw margin, trace, and grounded explanation", async () => {
    const user = userEvent.setup();
    apiMocks.runDemo.mockImplementation(async ({ onStage }) => {
      for (const stage of ["job", "index", "ranking", "explanation", "complete"] as const) onStage?.(stage);
      return demoRun;
    });
    render(<MatchingResultsScreen />);
    fireEvent.change(screen.getByLabelText("岗位描述文本"), { target: { value: "job source ".repeat(10) } });
    await user.click(screen.getByRole("button", { name: "开始推荐" }));
    expect(screen.getByRole("heading", { name: "AI Matching Engineer" })).toBeTruthy();
    expect(screen.getByText("岗位候选池 Top-K 推荐")).toBeTruthy();
    expect(screen.getByText("候选人 005")).toBeTruthy();
    expect(screen.getByText("推荐算法工程方向")).toBeTruthy();
    expect(screen.getByText("Learning To Rank 建模")).toBeTruthy();
    expect(screen.getByText("技术 ID · cand_005")).toBeTruthy();
    expect(screen.getAllByText("1.254321")).toHaveLength(2);
    expect(screen.getAllByText("排序模型分值（LTR Score）").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("高度推荐").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("该分值仅用于候选人排序，不是匹配概率、录用概率或推荐成功率。")).toBeTruthy();
    expect(screen.getByText("为什么推荐该候选人")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "推荐优势" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "风险提示" })).toBeTruthy();
    expect(screen.getByText("技术证据")).toBeTruthy();
    expect(screen.getByText("不可变运行轨迹")).toBeTruthy();
    expect(screen.getByText("历史复核").closest("li")?.getAttribute("aria-current")).toBe("step");
    expect(screen.getByText("该解释使用已记录的人岗匹配证据。")).toBeTruthy();
    expect(screen.getByText("候选人能力与岗位要求均有已记录证据支持。")).toBeTruthy();
    expect(screen.getByText("岗位必备要求暂未找到对应证据。")).toBeTruthy();
    expect(document.body.textContent).not.toContain("This explanation uses recorded matching evidence.");
    expect(document.body.textContent).not.toContain("Recorded candidate and requirement evidence is available.");
    expect(document.body.textContent).not.toContain("A required recorded requirement has no available evidence.");
    expect(screen.getByText("candidate:1:project:1")).toBeTruthy();
    expect(screen.getByText("run-demo")).toBeTruthy();
    const trace = screen.getByRole("heading", { name: "不可变运行轨迹" }).closest("section");
    expect(trace).toBeTruthy();
    expect(within(trace!).getByText("输入解析")).toBeTruthy();
    expect(within(trace!).getByText("LambdaMART 排序")).toBeTruthy();
    expect(within(trace!).getByText("结果持久化")).toBeTruthy();
    expect(within(trace!).getByText("resolve_inputs")).toBeTruthy();
    expect(within(trace!).getByText("phase6_ltr_rank")).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/准确率|95\.9%|final score/i);
    await user.click(screen.getByRole("button", { name: /查看第 2 名/ }));
    expect(screen.getAllByText("0.875000")).toHaveLength(2);
    expect(screen.getAllByText("推荐").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("该候选人保留在第二位。")).toBeTruthy();
  });

  it("surfaces a recoverable provider error without stack or secret material", async () => {
    const user = userEvent.setup();
    apiMocks.runDemo.mockRejectedValue(new DemoApiError("Extraction provider is unavailable", 503, "provider_unavailable", "request-safe"));
    render(<MatchingResultsScreen />);
    fireEvent.change(screen.getByLabelText("岗位描述文本"), { target: { value: "job source ".repeat(10) } });
    await user.click(screen.getByRole("button", { name: "开始推荐" }));
    const alert = screen.getByRole("alert");
    expect(alert.textContent).toContain("AI Provider 未配置或暂不可用");
    expect(alert.textContent).toContain("request-safe");
    expect(alert.textContent).not.toMatch(/traceback|bearer|api[_-]?key/i);
    expect(screen.getByRole("button", { name: "重新尝试" })).toBeTruthy();
  });

  it("renders rate limiting as a friendly retryable state without upstream details", async () => {
    const user = userEvent.setup();
    apiMocks.runDemo
      .mockRejectedValueOnce(new DemoApiError("Bearer secret traceback", 503, "provider_rate_limited", "request-rate"))
      .mockResolvedValueOnce(demoRun);
    render(<MatchingResultsScreen />);
    fireEvent.change(screen.getByLabelText("岗位描述文本"), { target: { value: "job source ".repeat(10) } });
    await user.click(screen.getByRole("button", { name: "开始推荐" }));
    const alert = screen.getByRole("alert");
    expect(alert.textContent).toContain("AI 服务请求过于频繁，请稍后重试。");
    expect(alert.textContent).not.toMatch(/bearer|secret|traceback/i);
    await user.click(screen.getByRole("button", { name: "重新尝试" }));
    expect(await screen.findByRole("heading", { name: "AI Matching Engineer" })).toBeTruthy();
    expect(apiMocks.runDemo).toHaveBeenCalledTimes(2);
  });

  it.each([
    ["provider_timeout", "AI 服务响应超时，请稍后重试。"],
    ["provider_output_invalid", "模型返回的结构化结果未通过校验，请重试。"],
  ])("renders %s as a safe recoverable error", async (code, expected) => {
    const user = userEvent.setup();
    apiMocks.runDemo.mockRejectedValue(new DemoApiError("private upstream detail", 503, code, "request-error"));
    render(<MatchingResultsScreen />);
    fireEvent.change(screen.getByLabelText("岗位描述文本"), { target: { value: "job source ".repeat(10) } });
    await user.click(screen.getByRole("button", { name: "开始推荐" }));
    expect(screen.getByRole("alert").textContent).toContain(expected);
    expect(screen.getByRole("alert").textContent).not.toContain("private upstream detail");
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
