import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CandidateParseData, CandidateRecord } from "@/types/demo";

import { CandidatePoolScreen } from "./candidate-pool-screen";


const apiMocks = vi.hoisted(() => ({
  addCandidateToPool: vi.fn(),
  fetchDemoSamples: vi.fn(),
  listCandidates: vi.fn(),
  previewCandidate: vi.fn(),
}));

vi.mock("@/lib/demo-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/demo-api")>()),
  ...apiMocks,
}));

const draft: CandidateParseData["draft"] = {
  name: "候选人演示",
  skills: [
    { name: "Python", category: "backend", self_reported_level: "advanced" },
    { name: "RAG", category: "llm_application", self_reported_level: "practiced" },
  ],
  projects: [{
    project_id: "prj_demo",
    name: "智能客服 RAG 系统",
    summary: "使用 Embedding、Qdrant 与 FastAPI 构建可追踪的检索增强生成系统。",
    role: "AI 应用工程师",
    technologies: ["Python", "FastAPI", "Qdrant"],
    outcomes: ["完成检索链路演示"],
    skills_demonstrated: ["Python", "RAG"],
  }],
  project_evidence: [{
    evidence_id: "ev_demo",
    project_id: "prj_demo",
    supports_skills: ["Python", "RAG"],
    evidence_type: "demo",
    statement: "演示项目提供可验证的检索链路和结构化输出。",
    artifact_ref: "sandbox://demo/candidate",
    verification_status: "available",
  }],
  github_url: null,
  ai_tools: ["FastAPI", "Qdrant"],
  target_roles: ["AI 应用工程师"],
  preferred_locations: { cities: ["上海"], remote_policy: "hybrid", relocation_open: false },
  seniority: "mid",
  work_style: { team_stage_preference: ["zero_to_one"], collaboration_style: "跨团队协作" },
  missing_fields: ["education"],
  overclaim_risk: { level: "low", reasons: [] },
};

const record: CandidateRecord = {
  ...draft,
  skills: [...draft.skills],
  projects: [...draft.projects],
  project_evidence: [...draft.project_evidence],
  ai_tools: [...draft.ai_tools],
  target_roles: [...draft.target_roles],
  preferred_locations: { ...draft.preferred_locations, cities: [...draft.preferred_locations.cities] },
  work_style: { ...draft.work_style, team_stage_preference: [...draft.work_style.team_stage_preference] },
  missing_fields: [...draft.missing_fields],
  overclaim_risk: { ...draft.overclaim_risk, reasons: [] },
  candidate_id: "cand_usr_demo",
  archetype: null,
  raw_text: "中文候选人简历内容包含 Python、FastAPI、RAG、Embedding 与 Qdrant 项目经验。",
  data_origin: "mock_parsed",
  schema_version: "1.0",
  dataset_version: null,
};

const preview: CandidateParseData = {
  draft: {
    ...draft,
    skills: [...draft.skills],
    projects: [...draft.projects],
    project_evidence: [...draft.project_evidence],
    ai_tools: [...draft.ai_tools],
    target_roles: [...draft.target_roles],
    preferred_locations: { ...draft.preferred_locations, cities: [...draft.preferred_locations.cities] },
    work_style: { ...draft.work_style, team_stage_preference: [...draft.work_style.team_stage_preference] },
    missing_fields: [...draft.missing_fields],
    overclaim_risk: { ...draft.overclaim_risk, reasons: [] },
  },
  record: null,
  extraction: {
    provider: "deterministic_mock", provider_kind: "mock",
    prompt_version: "candidate_extraction_prompt_v1", prompt_fingerprint: "d".repeat(64), attempts: 1,
    repaired: false, persisted: false, input_fingerprint: "a".repeat(64),
  },
};

afterEach(() => {
  cleanup();
  Object.values(apiMocks).forEach((mock) => mock.mockReset());
});

describe("CandidatePoolScreen", () => {
  it("shows a Chinese talent library with friendly identity before technical metadata", async () => {
    apiMocks.listCandidates.mockResolvedValue({ items: [record], total: 49, limit: 100, offset: 0 });
    render(<CandidatePoolScreen />);

    expect(await screen.findByRole("heading", { name: "人才库管理" })).toBeTruthy();
    expect(await screen.findByText("候选人演示")).toBeTruthy();
    expect(screen.getByText("AI 应用工程师方向")).toBeTruthy();
    expect(screen.getByText("技术 ID")).toBeTruthy();
    expect(screen.getByText("cand_usr_demo")).toBeTruthy();
    expect(screen.getByText("49 位候选人")).toBeTruthy();
    expect(screen.getByRole("link", { name: "推荐工作台" })).toBeTruthy();
  });

  it("loads the synthetic Resume, previews it, then confirms persistence and index refresh", async () => {
    const user = userEvent.setup();
    apiMocks.listCandidates
      .mockResolvedValueOnce({ items: [record], total: 48, limit: 100, offset: 0 })
      .mockResolvedValueOnce({ items: [record], total: 49, limit: 100, offset: 0 });
    apiMocks.fetchDemoSamples.mockResolvedValue({
      data_origin: "synthetic_sandbox",
      candidate_text: "中文简历：负责智能客服 RAG 系统，使用 Python、FastAPI、Qdrant 与 Embedding。",
      job_text: "unused",
    });
    apiMocks.previewCandidate.mockResolvedValue(preview);
    apiMocks.addCandidateToPool.mockResolvedValue({
      candidate: { ...preview, record, extraction: { ...preview.extraction, persisted: true } },
      index: { document_version: "retrieval_doc_v4", candidate_collection: "candidates", job_collection: "jobs", candidate_count: 49, job_count: 24 },
    });
    render(<CandidatePoolScreen />);
    await screen.findByText("候选人演示");

    await user.click(screen.getByRole("button", { name: "加载中文 Resume 示例" }));
    expect((screen.getByLabelText("候选人简历文本") as HTMLTextAreaElement).value).toContain("智能客服 RAG 系统");
    await user.click(screen.getByRole("button", { name: "解析候选人" }));
    expect(apiMocks.previewCandidate).toHaveBeenCalledWith(expect.stringContaining("Python"));
    expect(await screen.findByRole("heading", { name: "Structured Profile 预览" })).toBeTruthy();
    expect(screen.getByText("智能客服 RAG 系统")).toBeTruthy();
    expect(screen.getByText("待补充：education")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "确认加入人才库" }));
    expect(apiMocks.addCandidateToPool).toHaveBeenCalledWith(expect.stringContaining("Python"));
    expect(await screen.findByText("候选人已加入人才库，将参与后续岗位 Retrieval 与 Ranking。")).toBeTruthy();
    expect(screen.getByText("派生检索索引已刷新：49 位候选人")).toBeTruthy();
  });

  it("validates short input before calling extraction", async () => {
    const user = userEvent.setup();
    apiMocks.listCandidates.mockResolvedValue({ items: [], total: 0, limit: 100, offset: 0 });
    render(<CandidatePoolScreen />);
    await screen.findByText("人才库暂时为空");
    fireEvent.change(screen.getByLabelText("候选人简历文本"), { target: { value: "太短" } });
    await user.click(screen.getByRole("button", { name: "解析候选人" }));
    expect(screen.getByRole("alert").textContent).toContain("至少需要 40 个字符");
    expect(apiMocks.previewCandidate).not.toHaveBeenCalled();
  });
});
