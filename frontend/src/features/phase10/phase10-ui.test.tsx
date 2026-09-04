import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { readFileSync } from "node:fs";
import { StrictMode, useCallback, useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createBadCase,
  createFeedback,
  getBadCase,
  getExplanationRun,
  getMatchRun,
  listBadCases,
  listCompletedMatchRuns,
  listExplanationRuns,
  Phase10ApiError,
  reviewBadCase,
} from "@/lib/phase10-api";
import type { BadCaseDetail, ExplanationRunDetail, MatchRunDetail } from "@/types/phase10";

import { BadCaseDetailScreen } from "./bad-case-detail-screen";
import { BadCaseListScreen } from "./bad-case-list-screen";
import { FeedbackPanel } from "./feedback-panel";
import { HistoricalFeedbackEntry } from "./historical-feedback-entry";
import { ReviewShell } from "./review-shell";
import { useModalDialog } from "./use-modal-dialog";


vi.mock("@/lib/phase10-api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/phase10-api")>("@/lib/phase10-api");
  return {
    ...actual,
    createBadCase: vi.fn(),
    createFeedback: vi.fn(),
    getBadCase: vi.fn(),
    getExplanationRun: vi.fn(),
    getMatchRun: vi.fn(),
    listBadCases: vi.fn(),
    listCompletedMatchRuns: vi.fn(),
    listExplanationRuns: vi.fn(),
    reviewBadCase: vi.fn(),
  };
});

const run: MatchRunDetail = {
  run_id: "run-1",
  requested_job_id: "job-1",
  job_id: "job-1",
  ranking_variant: "ltr",
  status: "COMPLETED",
  created_at: "2026-08-28T10:00:00Z",
  completed_at: "2026-08-28T10:00:01Z",
  result_count: 2,
  results: [
    {
      match_result_id: 41,
      candidate_id: "candidate-1",
      result_rank: 1,
      retrieval_rank: 2,
      ltr_rank: 1,
      ltr_score_raw: 0.42,
      cross_encoder_rank: null,
      cross_encoder_score_raw: null,
      skill_fit_score: 0.8,
      project_evidence_score: 0.7,
      role_direction_score: 0.6,
      location_score: 1,
      seniority_score: 0.9,
      feature_diagnostics: {},
    },
    {
      match_result_id: 42,
      candidate_id: "candidate-2",
      result_rank: 2,
      retrieval_rank: 1,
      ltr_rank: 2,
      ltr_score_raw: 0.31,
      cross_encoder_rank: null,
      cross_encoder_score_raw: null,
      skill_fit_score: 0.7,
      project_evidence_score: 0.6,
      role_direction_score: 0.5,
      location_score: 1,
      seniority_score: 0.8,
      feature_diagnostics: {},
    },
  ],
  steps: [],
};

const explanation: ExplanationRunDetail = {
  explanation_run_id: "explanation-1",
  match_run_id: "run-1",
  status: "COMPLETED",
  explanation_count: 1,
  created_at: "2026-08-28T10:00:02Z",
  completed_at: "2026-08-28T10:00:03Z",
  explanations: [
    {
      match_explanation_id: 71,
      output_schema_version: "explanation_output_v1",
      candidate_id: "candidate-1",
      result_rank: 1,
      summary: { text: "Historical grounded explanation.", evidence_refs: ["candidate:1:skill:opaque"] },
      match_reasons: [],
      risk_points: [],
      missing_skills: [],
      interview_questions: [],
      why_not_top1: null,
    },
  ],
};

const detail: BadCaseDetail = {
  bad_case_id: "case-1",
  case_contract_version: "bad_case_v1",
  taxonomy_version: "bad_case_taxonomy_v1",
  primary_match_run_id: "run-1",
  primary_match_result_id: 41,
  historical_job_id: "job-1",
  historical_candidate_id: "candidate-1",
  result_rank: 1,
  primary_explanation_run_id: "explanation-1",
  primary_match_explanation_id: 71,
  symptom_code: "unsupported_explanation",
  symptom_family: "EXPLANATION",
  severity: "HIGH",
  status: "REVIEWED",
  revision: 1,
  duplicate_of_bad_case_id: null,
  related_case_id: null,
  created_at: "2026-08-28T10:00:04Z",
  updated_at: "2026-08-28T10:00:05Z",
  sources: [{ source_type: "feedback", feedback_id: "feedback-1", created_at: "2026-08-28T10:00:04Z" }],
  evidence_links: [{ evidence_link_id: 9, explanation_run_id: "explanation-1", evidence_reference: "candidate:1:skill:opaque", field_locator: null, purpose: "supports_analysis", evidence_kind: "skill", candidate_id: "candidate-1", result_rank: 1 }],
  analyses: [
    { analysis_id: 1, revision_number: 1, assessment: "supported", root_cause_type: "explanation", root_cause_code: "explanation_unsupported_claim", description: "Initially supported.", supporting_evidence_link_id: 9, created_at: "2026-08-28T10:01:00Z" },
    { analysis_id: 2, revision_number: 2, assessment: "rejected", root_cause_type: "explanation", root_cause_code: "explanation_unsupported_claim", description: "Later rejected.", supporting_evidence_link_id: null, created_at: "2026-08-28T10:02:00Z" },
  ],
  resolution_actions: [],
  transitions: [{ transition_id: 1, from_status: "CREATED", to_status: "REVIEWED", reason: "review_completed", origin: "manual_review", previous_revision: 0, new_revision: 1, verification_reference: null, created_at: "2026-08-28T10:00:05Z" }],
  child_limit: 100,
  truncated_collections: ["sources"],
};

function InitiallyOpenModal() {
  const [open, setOpen] = useState(true);
  const close = useCallback(() => setOpen(false), []);
  const { dialogRef, onDialogKeyDown } = useModalDialog(open, close);
  return open ? <section ref={dialogRef} role="dialog" aria-label="Initially open modal" onKeyDown={onDialogKeyDown}><button type="button" onClick={close}>Close initial modal</button></section> : null;
}


afterEach(cleanup);

beforeEach(() => {
  vi.clearAllMocks();
});

describe("useModalDialog", () => {
  it("does not restore background focus during a StrictMode effect replay", async () => {
    const backgroundTrigger = document.createElement("button");
    backgroundTrigger.textContent = "Background trigger";
    document.body.append(backgroundTrigger);
    backgroundTrigger.focus();

    render(<StrictMode><InitiallyOpenModal /></StrictMode>);

    const close = await screen.findByRole("button", { name: "Close initial modal" });
    await waitFor(() => expect(document.activeElement).toBe(close));
    backgroundTrigger.remove();
  });
});

describe("FeedbackPanel", () => {
  it("uses Chinese-first reviewer-facing controls without changing closed values", () => {
    render(<FeedbackPanel run={run} explanationRun={explanation} />);

    expect(screen.getByRole("heading", { name: "复核推荐结果" })).toBeTruthy();
    expect(screen.getByRole("tab", { name: "排序结果" })).toBeTruthy();
    expect(screen.getByRole("tab", { name: "推荐解释" })).toBeTruthy();
    expect(screen.getByRole("tab", { name: "候选人资料" })).toBeTruthy();
    expect(screen.getByLabelText("复核对象")).toBeTruthy();
    expect(screen.getByLabelText("评价结果")).toBeTruthy();
    expect(screen.getByRole("button", { name: "提交反馈" })).toBeTruthy();
    expect(screen.getByLabelText("备注")).toBeTruthy();
    expect(document.body.textContent).not.toContain("Review recommendation");
    expect(document.body.textContent).not.toContain("Optional reviewer note");
  });

  it("supports the keyboard tab pattern for feedback variants", async () => {
    const user = userEvent.setup();
    render(<FeedbackPanel run={run} explanationRun={explanation} />);
    const ranking = screen.getByRole("tab", { name: "排序结果" });
    const explanationTab = screen.getByRole("tab", { name: "推荐解释" });

    expect(ranking).toHaveProperty("tabIndex", 0);
    expect(explanationTab).toHaveProperty("tabIndex", -1);
    ranking.focus();
    await user.keyboard("{ArrowRight}");

    expect(document.activeElement).toBe(explanationTab);
    expect(explanationTab.getAttribute("aria-selected")).toBe("true");
    expect(screen.getByRole("tabpanel").getAttribute("aria-labelledby")).toBe(explanationTab.id);
  });

  it("uses persisted result locators and does not ask the reviewer for database ids", async () => {
    vi.mocked(createFeedback).mockResolvedValue({ success: true, data: { feedback_id: "feedback-1", feedback_type: "ranking" } as never, error: null, request_id: "request-1" });
    const user = userEvent.setup();
    render(<FeedbackPanel run={run} explanationRun={explanation} />);

    expect(screen.queryByLabelText(/match result id/i)).toBeNull();
    await user.selectOptions(screen.getByLabelText("复核对象"), "top1");
    await user.selectOptions(screen.getByLabelText("评价结果"), "wrong");
    await user.selectOptions(screen.getByLabelText("问题原因"), "wrong_top1");
    await user.click(screen.getByRole("button", { name: "提交反馈" }));

    await waitFor(() => expect(createFeedback).toHaveBeenCalledWith(expect.objectContaining({
      feedback_type: "ranking",
      match_run_id: "run-1",
      target_type: "top1",
      subject_match_result_id: 41,
      value: "wrong",
      reason_code: "wrong_top1",
    })));
  });

  it("switches to explanation feedback and submits the persisted explanation locator", async () => {
    vi.mocked(createFeedback).mockResolvedValue({ success: true, data: { feedback_id: "feedback-2", feedback_type: "explanation" } as never, error: null, request_id: "request-2" });
    const user = userEvent.setup();
    render(<FeedbackPanel run={run} explanationRun={explanation} />);

    await user.click(screen.getByRole("tab", { name: "推荐解释" }));
    await user.selectOptions(screen.getByLabelText("历史 Evidence 引用"), "candidate:1:skill:opaque");
    await user.click(screen.getByRole("button", { name: "提交反馈" }));

    await waitFor(() => expect(createFeedback).toHaveBeenCalledWith(expect.objectContaining({
      feedback_type: "explanation",
      explanation_run_id: "explanation-1",
      match_explanation_id: 71,
      evidence_reference: "candidate:1:skill:opaque",
    })));
  });

  it("does not expose the persisted feedback identifier as reviewer-facing content", async () => {
    const feedbackId = "11111111-2222-4333-8444-555555555555";
    vi.mocked(createFeedback).mockResolvedValue({
      success: true,
      data: { feedback_id: feedbackId, feedback_type: "ranking" } as never,
      error: null,
      request_id: "request-private-locator",
    });
    const user = userEvent.setup();
    render(<FeedbackPanel run={run} explanationRun={explanation} />);

    await user.click(screen.getByRole("button", { name: "提交反馈" }));

    expect(await screen.findByText("反馈已记录")).toBeTruthy();
    expect(screen.queryByText(new RegExp(feedbackId))).toBeNull();
  });

  it("does not offer run-scoped evidence as a candidate-scoped explanation reference", async () => {
    const mixedEvidence = {
      ...explanation,
      explanations: [{
        ...explanation.explanations[0],
        summary: {
          ...explanation.explanations[0].summary,
          evidence_refs: ["job_requirement:req_python", "ranking:1:result_rank"],
        },
      }],
    } satisfies ExplanationRunDetail;

    const user = userEvent.setup();
    render(<FeedbackPanel run={run} explanationRun={mixedEvidence} />);
    await user.click(screen.getByRole("tab", { name: "推荐解释" }));

    const evidence = screen.getByLabelText("历史 Evidence 引用");
    expect(within(evidence).queryByRole("option", { name: "job_requirement:req_python" })).toBeNull();
    expect(within(evidence).getByRole("option", { name: "ranking:1:result_rank" })).toBeTruthy();
  });

  it("limits wrong-reason choices to the selected ranking target", async () => {
    const user = userEvent.setup();
    render(<FeedbackPanel run={run} explanationRun={explanation} />);

    await user.selectOptions(screen.getByLabelText("复核对象"), "top1");
    await user.selectOptions(screen.getByLabelText("评价结果"), "wrong");
    let reason = screen.getByLabelText("问题原因");
    expect(within(reason).getAllByRole("option").map((option) => option.getAttribute("value"))).toEqual(["wrong_top1"]);

    await user.selectOptions(screen.getByLabelText("复核对象"), "pairwise");
    reason = screen.getByLabelText("问题原因");
    expect(within(reason).getAllByRole("option").map((option) => option.getAttribute("value"))).toEqual([
      "ranking_inversion",
      "constraint_conflict",
      "evidence_coverage_disagreement",
    ]);
  });

  it("never offers the selected pairwise result as its own comparison", async () => {
    const user = userEvent.setup();
    render(<FeedbackPanel run={run} explanationRun={explanation} />);

    await user.selectOptions(screen.getByLabelText("复核对象"), "pairwise");
    const subject = screen.getByLabelText("历史排序结果");
    let comparison = screen.getByLabelText("对比结果");
    expect(within(comparison).queryByRole("option", { name: /第 1 名/ })).toBeNull();

    await user.selectOptions(subject, "42");
    comparison = screen.getByLabelText("对比结果");
    expect(within(comparison).queryByRole("option", { name: /第 2 名/ })).toBeNull();
    expect(within(comparison).getByRole("option", { name: /第 1 名/ })).toBeTruthy();
  });

  it("clears an evidence reference when the historical explanation target changes", async () => {
    const twoExplanations: ExplanationRunDetail = {
      ...explanation,
      explanation_count: 2,
      explanations: [
        explanation.explanations[0],
        {
          ...explanation.explanations[0],
          match_explanation_id: 72,
          candidate_id: "candidate-2",
          result_rank: 2,
          summary: { text: "Second historical explanation.", evidence_refs: ["candidate:2:skill:second"] },
        },
      ],
    };
    vi.mocked(createFeedback).mockResolvedValue({ success: true, data: { feedback_id: "feedback-4", feedback_type: "explanation" } as never, error: null, request_id: "request-4" });
    const user = userEvent.setup();
    render(<FeedbackPanel run={run} explanationRun={twoExplanations} />);

    await user.click(screen.getByRole("tab", { name: "推荐解释" }));
    await user.selectOptions(screen.getByLabelText("历史 Evidence 引用"), "candidate:1:skill:opaque");
    await user.selectOptions(screen.getByLabelText("历史推荐解释"), "72");
    expect(screen.getByLabelText("历史 Evidence 引用")).toHaveProperty("value", "");
    await user.click(screen.getByRole("button", { name: "提交反馈" }));

    await waitFor(() => expect(createFeedback).toHaveBeenCalledWith(expect.not.objectContaining({
      evidence_reference: "candidate:1:skill:opaque",
    })));
  });
});

describe("HistoricalFeedbackEntry", () => {
  it("loads persisted context and keeps BadCase creation explicit", async () => {
    vi.mocked(listCompletedMatchRuns).mockResolvedValue({ success: true, data: { items: [run], total: 1, limit: 20, offset: 0 }, error: null, request_id: "runs-1" });
    vi.mocked(getMatchRun).mockResolvedValue({ success: true, data: run, error: null, request_id: "run-1" });
    vi.mocked(listExplanationRuns).mockResolvedValue({ success: true, data: { items: [explanation], total: 1, limit: 20, offset: 0 }, error: null, request_id: "explanations-1" });
    vi.mocked(getExplanationRun).mockResolvedValue({ success: true, data: explanation, error: null, request_id: "explanation-1" });
    vi.mocked(createFeedback).mockResolvedValue({ success: true, data: { feedback_id: "feedback-3", feedback_type: "ranking", value: "wrong", reason_code: "wrong_top1" } as never, error: null, request_id: "feedback-3" });
    vi.mocked(createBadCase).mockResolvedValue({ success: true, data: detail, error: null, request_id: "case-1" });
    const user = userEvent.setup();

    render(<HistoricalFeedbackEntry />);
    expect(await screen.findByText("复核推荐结果")).toBeTruthy();
    await user.selectOptions(screen.getByLabelText("复核对象"), "top1");
    await user.selectOptions(screen.getByLabelText("评价结果"), "wrong");
    await user.selectOptions(screen.getByLabelText("问题原因"), "wrong_top1");
    await user.click(screen.getByRole("button", { name: "提交反馈" }));

    expect(await screen.findByRole("button", { name: "创建 Bad Case" })).toBeTruthy();
    expect(createBadCase).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "创建 Bad Case" }));
    expect(screen.getByText("Top 1 推荐不正确")).toBeTruthy();
    expect(screen.queryByRole("option", { name: "推荐解释缺少证据" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "确认创建 Bad Case" }));
    await waitFor(() => expect(createBadCase).toHaveBeenCalledWith(expect.objectContaining({
      source_type: "feedback",
      feedback_id: "feedback-3",
      symptom_code: "wrong_top1",
    })));
    expect((await screen.findByRole("link", { name: "打开 Bad Case" })).getAttribute("href")).toBe("/bad-cases/case-1");
  });

  it("does not offer BadCase creation for feedback without an observed problem", async () => {
    vi.mocked(listCompletedMatchRuns).mockResolvedValue({ success: true, data: { items: [run], total: 1, limit: 20, offset: 0 }, error: null, request_id: "runs-1" });
    vi.mocked(getMatchRun).mockResolvedValue({ success: true, data: run, error: null, request_id: "run-1" });
    vi.mocked(listExplanationRuns).mockResolvedValue({ success: true, data: { items: [], total: 0, limit: 20, offset: 0 }, error: null, request_id: "explanations-1" });
    vi.mocked(createFeedback).mockResolvedValue({
      success: true,
      data: { feedback_id: "feedback-correct", feedback_type: "ranking", value: "correct", reason_code: null } as never,
      error: null,
      request_id: "feedback-correct",
    });
    const user = userEvent.setup();

    render(<HistoricalFeedbackEntry />);
    await screen.findByText("复核推荐结果");
    await user.click(screen.getByRole("button", { name: "提交反馈" }));

    expect(await screen.findByText(/没有对应的 Bad Case 症状/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "创建 Bad Case" })).toBeNull();
  });
});

describe("BadCase screens", () => {
  it("defines every CSS module class used by the review shell", () => {
    const css = readFileSync("src/features/matching-results/matching-results.module.css", "utf-8");

    for (const className of ["jobBar", "jobBarLabel", "jobMeta", "jobContextLabel"]) {
      expect(css).toMatch(new RegExp(`\\.${className}\\b`));
    }
  });

  it("renders a styled Chinese-first review shell", () => {
    const { container } = render(<ReviewShell><div>复核队列内容</div></ReviewShell>);
    const header = container.querySelector("header");

    expect(header?.className).toBeTruthy();
    expect(screen.getByText("质量复核")).toBeTruthy();
    expect(screen.getByText("历史匹配问题调查")).toBeTruthy();
    expect(screen.getByText("复核队列")).toBeTruthy();
    expect(screen.queryByText("Quality review")).toBeNull();
  });

  it("renders a lightweight evidence-first list and a helpful empty state", async () => {
    vi.mocked(listBadCases).mockResolvedValueOnce({ success: true, data: { items: [detail], total: 1, limit: 20, offset: 0 }, error: null, request_id: "list-1" });
    const { unmount } = render(<BadCaseListScreen />);
    expect(await screen.findByRole("link", { name: /推荐解释缺少证据/ })).toBeTruthy();
    expect(screen.getByText("已复核")).toBeTruthy();
    unmount();

    vi.mocked(listBadCases).mockResolvedValueOnce({ success: true, data: { items: [], total: 0, limit: 20, offset: 0 }, error: null, request_id: "list-2" });
    render(<BadCaseListScreen />);
    expect(await screen.findByText("暂无 Bad Case 记录")).toBeTruthy();
    expect(screen.queryByText("No bad cases need review")).toBeNull();
  });

  it("recovers the Bad Case queue after a transient API failure", async () => {
    vi.mocked(listBadCases)
      .mockRejectedValueOnce(new Phase10ApiError("Review service is temporarily unavailable", 503, "service_unavailable", "list-error"))
      .mockResolvedValueOnce({ success: true, data: { items: [detail], total: 1, limit: 20, offset: 0 }, error: null, request_id: "list-retry" });
    const user = userEvent.setup();
    render(<BadCaseListScreen />);

    expect(await screen.findByText("Bad Case 复核暂不可用")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "重新尝试" }));

    expect(await screen.findByRole("link", { name: /推荐解释缺少证据/ })).toBeTruthy();
    expect(listBadCases).toHaveBeenCalledTimes(2);
  });

  it("marks bounded history and treats the latest rejected analysis as current", async () => {
    vi.mocked(getBadCase).mockResolvedValue({ success: true, data: detail, error: null, request_id: "detail-1" });
    render(<BadCaseDetailScreen badCaseId="case-1" />);

    expect(await screen.findByText("部分历史记录")).toBeTruthy();
    expect(screen.getByText(/有界的 来源记录/)).toBeTruthy();
    expect(screen.getAllByText("已复核").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("高")).toBeTruthy();
    expect(screen.getByText("解释")).toBeTruthy();
    expect(screen.getByText("待复核 → 已复核")).toBeTruthy();
    expect(screen.getByText("复核已完成")).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/\b(REVIEWED|HIGH|EXPLANATION|review completed)\b/);
    const current = screen.getByLabelText("当前有效分析");
    expect(within(current).getByText(/^已否定 ·/)).toBeTruthy();
    expect(within(current).queryByText(/^有证据支持\b/)).toBeNull();
    expect(screen.getByRole("button", { name: "确认根因" })).toHaveProperty("disabled", true);
    expect(screen.getByText(/最新分析必须达到/)).toBeTruthy();
  });

  it("does not infer current analysis or actions from a truncated bounded projection", async () => {
    vi.mocked(getBadCase).mockResolvedValue({
      success: true,
      data: {
        ...detail,
        analyses: [detail.analyses[0]],
        resolution_actions: [{
          action_id: 4,
          action_type: "grounding_integrity_action",
          description: "Older bounded action.",
          status: "planned",
          supersedes_action_id: null,
          safe_change_reference: null,
          created_at: "2026-08-28T10:03:00Z",
          completed_at: null,
        }],
        truncated_collections: ["analyses", "resolution_actions"],
      },
      error: null,
      request_id: "detail-truncated",
    });

    render(<BadCaseDetailScreen badCaseId="case-1" />);

    expect(await screen.findByText(/未包含完整分析历史/)).toBeTruthy();
    expect(screen.queryByLabelText("当前有效分析")).toBeNull();
    expect(screen.getByText(/未包含完整处理历史/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "添加分析" })).toHaveProperty("disabled", true);
    expect(screen.getByRole("button", { name: "确认根因" })).toHaveProperty("disabled", true);
    expect(screen.getByRole("button", { name: "规划处理行动" })).toHaveProperty("disabled", true);
  });

  it("updates a non-terminal current action instead of superseding a completed sibling chain", async () => {
    const multipleCurrentActions: BadCaseDetail = {
      ...detail,
      status: "ACTION_PLANNED",
      revision: 3,
      truncated_collections: [],
      analyses: [detail.analyses[0]],
      resolution_actions: [
        {
          action_id: 4,
          action_type: "template_change_hypothesis",
          description: "Still active.",
          status: "planned",
          supersedes_action_id: null,
          safe_change_reference: null,
          created_at: "2026-08-28T10:03:00Z",
          completed_at: null,
        },
        {
          action_id: 5,
          action_type: "grounding_integrity_action",
          description: "Independent work already completed.",
          status: "completed",
          supersedes_action_id: null,
          safe_change_reference: "commit:completed-sibling",
          created_at: "2026-08-28T10:04:00Z",
          completed_at: "2026-08-28T10:05:00Z",
        },
      ],
    };
    vi.mocked(getBadCase).mockResolvedValue({ success: true, data: multipleCurrentActions, error: null, request_id: "detail-actions" });
    vi.mocked(reviewBadCase).mockResolvedValue({ success: true, data: multipleCurrentActions, error: null, request_id: "review-actions" });
    const user = userEvent.setup();
    render(<BadCaseDetailScreen badCaseId="case-1" />);

    await user.click(await screen.findByRole("button", { name: "更新处理行动" }));
    expect(screen.getByLabelText("行动类型")).toHaveProperty("value", "template_change_hypothesis");
    await user.selectOptions(screen.getByLabelText("行动状态"), "completed");
    await user.clear(screen.getByLabelText("行动说明"));
    await user.type(screen.getByLabelText("行动说明"), "Complete the remaining current action.");
    await user.type(screen.getByLabelText("安全变更引用"), "commit:remaining-action");
    await user.click(screen.getByRole("button", { name: "保存处理行动" }));

    await waitFor(() => expect(reviewBadCase).toHaveBeenCalledWith("case-1", expect.objectContaining({
      resolution: expect.objectContaining({ supersedes_action_id: 4 }),
    })));
  });

  it("uses closed review taxonomies instead of arbitrary mutation codes", async () => {
    vi.mocked(getBadCase).mockResolvedValue({ success: true, data: { ...detail, analyses: [detail.analyses[0]] }, error: null, request_id: "detail-1" });
    const user = userEvent.setup();
    render(<BadCaseDetailScreen badCaseId="case-1" />);
    await screen.findByLabelText("当前有效分析");

    await user.click(screen.getByRole("button", { name: "添加分析" }));
    expect(screen.getByLabelText("根因代码").tagName).toBe("SELECT");
    await user.click(screen.getByRole("button", { name: "关闭" }));
    await user.click(screen.getByRole("button", { name: "规划处理行动" }));
    expect(screen.getByLabelText("行动类型").tagName).toBe("SELECT");
    expect(screen.getByLabelText("行动状态").tagName).toBe("SELECT");
  });

  it("selects a compatible canonical case without asking for a raw case id", async () => {
    const canonical = { ...detail, bad_case_id: "case-2", revision: 3 };
    vi.mocked(getBadCase).mockResolvedValue({ success: true, data: detail, error: null, request_id: "detail-1" });
    vi.mocked(listBadCases).mockResolvedValue({
      success: true,
      data: { items: [detail, canonical], total: 2, limit: 100, offset: 0 },
      error: null,
      request_id: "list-canonical",
    });
    const user = userEvent.setup();
    render(<BadCaseDetailScreen badCaseId="case-1" />);

    await user.click(await screen.findByRole("button", { name: "标记为重复" }));

    expect(await screen.findByLabelText("主 Bad Case")).toHaveProperty("tagName", "SELECT");
    expect(screen.queryByLabelText(/canonical case reference/i)).toBeNull();
    expect(screen.getByRole("option", { name: /推荐解释缺少证据 · 已复核/ })).toBeTruthy();
    expect(screen.queryByRole("option", { name: /case-1/i })).toBeNull();
  });

  it("hides invalid duplicate actions and disables every workflow control while a mutation is pending", async () => {
    vi.mocked(getBadCase).mockResolvedValue({
      success: true,
      data: { ...detail, status: "RESOLVED", revision: 5 },
      error: null,
      request_id: "detail-resolved",
    });
    vi.mocked(reviewBadCase).mockImplementation(() => new Promise(() => {}));
    const user = userEvent.setup();
    render(<BadCaseDetailScreen badCaseId="case-1" />);

    const reopen = await screen.findByRole("button", { name: "重新打开复核" });
    expect(screen.queryByRole("button", { name: "标记为重复" })).toBeNull();
    await user.click(reopen);

    expect(screen.getByLabelText("Bad Case 复核工作区").getAttribute("aria-busy")).toBe("true");
    expect(screen.getByRole("button", { name: "核验 Bad Case" })).toHaveProperty("disabled", true);
    expect(reopen).toHaveProperty("disabled", true);
  });

  it("restores the review command trigger after dismissing its dialog", async () => {
    vi.mocked(getBadCase).mockResolvedValue({ success: true, data: detail, error: null, request_id: "detail-1" });
    const user = userEvent.setup();
    render(<BadCaseDetailScreen badCaseId="case-1" />);
    const trigger = await screen.findByRole("button", { name: "添加分析" });
    trigger.focus();

    await user.click(trigger);
    expect(screen.getByRole("dialog").contains(document.activeElement)).toBe(true);
    await user.keyboard("{Escape}");

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it("moves focus to the stable case heading when a successful command removes its trigger", async () => {
    const resolved = { ...detail, status: "RESOLVED" as const, revision: 4 };
    const verified = { ...resolved, status: "VERIFIED" as const, revision: 5 };
    vi.mocked(getBadCase).mockResolvedValue({ success: true, data: resolved, error: null, request_id: "detail-resolved" });
    vi.mocked(reviewBadCase).mockResolvedValue({ success: true, data: verified, error: null, request_id: "detail-verified" });
    const user = userEvent.setup();
    render(<BadCaseDetailScreen badCaseId="case-1" />);

    await user.click(await screen.findByRole("button", { name: "核验 Bad Case" }));
    await user.type(screen.getByLabelText("不可变核验引用"), "commit:case-verification");
    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "核验 Bad Case" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("heading", { name: "推荐解释缺少证据" })));
  });

  it("surfaces a stale revision without replaying the mutation and refreshes on demand", async () => {
    vi.mocked(getBadCase).mockResolvedValue({ success: true, data: detail, error: null, request_id: "detail-1" });
    vi.mocked(reviewBadCase).mockRejectedValue(new Phase10ApiError("This case changed", 409, "review_concurrency_conflict", "stale-1"));
    const user = userEvent.setup();
    render(<BadCaseDetailScreen badCaseId="case-1" />);

    await screen.findByLabelText("当前有效分析");
    await user.click(screen.getByRole("button", { name: "添加分析" }));
    await user.type(screen.getByLabelText("分析说明"), "New bounded assessment");
    await user.click(screen.getByRole("button", { name: "保存分析" }));

    expect(await screen.findByText("该 Bad Case 已在其他位置发生变化。")).toBeTruthy();
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(reviewBadCase).toHaveBeenCalledTimes(1);
    await user.click(screen.getByRole("button", { name: "刷新最新记录" }));
    await waitFor(() => expect(getBadCase).toHaveBeenCalledTimes(2));
    expect(reviewBadCase).toHaveBeenCalledTimes(1);
  });

  it("does not let an older overlapping refresh replace the latest case revision", async () => {
    let resolveOlder!: (value: Awaited<ReturnType<typeof getBadCase>>) => void;
    let resolveLatest!: (value: Awaited<ReturnType<typeof getBadCase>>) => void;
    const older = new Promise<Awaited<ReturnType<typeof getBadCase>>>((resolve) => { resolveOlder = resolve; });
    const latest = new Promise<Awaited<ReturnType<typeof getBadCase>>>((resolve) => { resolveLatest = resolve; });
    vi.mocked(getBadCase)
      .mockResolvedValueOnce({ success: true, data: detail, error: null, request_id: "detail-1" })
      .mockReturnValueOnce(older)
      .mockReturnValueOnce(latest);
    vi.mocked(reviewBadCase).mockRejectedValue(
      new Phase10ApiError("This case changed", 409, "review_concurrency_conflict", "stale-1"),
    );
    const user = userEvent.setup();
    render(<BadCaseDetailScreen badCaseId="case-1" />);

    await screen.findByLabelText("当前有效分析");
    await user.click(screen.getByRole("button", { name: "添加分析" }));
    await user.type(screen.getByLabelText("分析说明"), "New bounded assessment");
    await user.click(screen.getByRole("button", { name: "保存分析" }));
    const refresh = await screen.findByRole("button", { name: "刷新最新记录" });
    await user.click(refresh);
    await user.click(refresh);
    expect(getBadCase).toHaveBeenCalledTimes(3);

    resolveLatest({ success: true, data: { ...detail, revision: 3 }, error: null, request_id: "detail-latest" });
    await waitFor(() => expect(within(screen.getByText("修订版本").parentElement!).getByText("3")).toBeTruthy());
    await act(async () => {
      resolveOlder({ success: true, data: { ...detail, revision: 2 }, error: null, request_id: "detail-older" });
      await older;
    });
    expect(within(screen.getByText("修订版本").parentElement!).getByText("3")).toBeTruthy();
  });

  it("keeps a semantic 422 beside the active command without exposing raw data", async () => {
    vi.mocked(getBadCase).mockResolvedValue({ success: true, data: detail, error: null, request_id: "detail-1" });
    vi.mocked(reviewBadCase).mockRejectedValue(new Phase10ApiError("Historical evidence kind is incompatible", 422, "review_eligibility", "semantic-1"));
    const user = userEvent.setup();
    render(<BadCaseDetailScreen badCaseId="case-1" />);

    await screen.findByLabelText("当前有效分析");
    await user.click(screen.getByRole("button", { name: "添加分析" }));
    await user.type(screen.getByLabelText("分析说明"), "Bounded semantic test");
    await user.click(screen.getByRole("button", { name: "保存分析" }));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByRole("alert").textContent).toContain("Historical evidence kind is incompatible");
    expect(within(dialog).queryByText(/sql|traceback/i)).toBeNull();
  });
});
