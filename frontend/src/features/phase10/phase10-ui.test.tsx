import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
  it("supports the keyboard tab pattern for feedback variants", async () => {
    const user = userEvent.setup();
    render(<FeedbackPanel run={run} explanationRun={explanation} />);
    const ranking = screen.getByRole("tab", { name: "Ranking" });
    const explanationTab = screen.getByRole("tab", { name: "Explanation" });

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
    await user.selectOptions(screen.getByLabelText("Ranking target"), "top1");
    await user.selectOptions(screen.getByLabelText("Verdict"), "wrong");
    await user.selectOptions(screen.getByLabelText("Reason"), "wrong_top1");
    await user.click(screen.getByRole("button", { name: "Submit feedback" }));

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

    await user.click(screen.getByRole("tab", { name: "Explanation" }));
    await user.selectOptions(screen.getByLabelText("Historical evidence reference"), "candidate:1:skill:opaque");
    await user.click(screen.getByRole("button", { name: "Submit feedback" }));

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

    await user.click(screen.getByRole("button", { name: "Submit feedback" }));

    expect(await screen.findByText("Feedback recorded")).toBeTruthy();
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
    await user.click(screen.getByRole("tab", { name: "Explanation" }));

    const evidence = screen.getByLabelText("Historical evidence reference");
    expect(within(evidence).queryByRole("option", { name: "job_requirement:req_python" })).toBeNull();
    expect(within(evidence).getByRole("option", { name: "ranking:1:result_rank" })).toBeTruthy();
  });

  it("limits wrong-reason choices to the selected ranking target", async () => {
    const user = userEvent.setup();
    render(<FeedbackPanel run={run} explanationRun={explanation} />);

    await user.selectOptions(screen.getByLabelText("Ranking target"), "top1");
    await user.selectOptions(screen.getByLabelText("Verdict"), "wrong");
    let reason = screen.getByLabelText("Reason");
    expect(within(reason).getAllByRole("option").map((option) => option.getAttribute("value"))).toEqual(["wrong_top1"]);

    await user.selectOptions(screen.getByLabelText("Ranking target"), "pairwise");
    reason = screen.getByLabelText("Reason");
    expect(within(reason).getAllByRole("option").map((option) => option.getAttribute("value"))).toEqual([
      "ranking_inversion",
      "constraint_conflict",
      "evidence_coverage_disagreement",
    ]);
  });

  it("never offers the selected pairwise result as its own comparison", async () => {
    const user = userEvent.setup();
    render(<FeedbackPanel run={run} explanationRun={explanation} />);

    await user.selectOptions(screen.getByLabelText("Ranking target"), "pairwise");
    const subject = screen.getByLabelText("Historical result");
    let comparison = screen.getByLabelText("Compared result");
    expect(within(comparison).queryByRole("option", { name: /rank 1/i })).toBeNull();

    await user.selectOptions(subject, "42");
    comparison = screen.getByLabelText("Compared result");
    expect(within(comparison).queryByRole("option", { name: /rank 2/i })).toBeNull();
    expect(within(comparison).getByRole("option", { name: /rank 1/i })).toBeTruthy();
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

    await user.click(screen.getByRole("tab", { name: "Explanation" }));
    await user.selectOptions(screen.getByLabelText("Historical evidence reference"), "candidate:1:skill:opaque");
    await user.selectOptions(screen.getByLabelText("Historical explanation"), "72");
    expect(screen.getByLabelText("Historical evidence reference")).toHaveProperty("value", "");
    await user.click(screen.getByRole("button", { name: "Submit feedback" }));

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
    expect(await screen.findByText("Review recommendation")).toBeTruthy();
    await user.selectOptions(screen.getByLabelText("Ranking target"), "top1");
    await user.selectOptions(screen.getByLabelText("Verdict"), "wrong");
    await user.selectOptions(screen.getByLabelText("Reason"), "wrong_top1");
    await user.click(screen.getByRole("button", { name: "Submit feedback" }));

    expect(await screen.findByRole("button", { name: "Create bad case" })).toBeTruthy();
    expect(createBadCase).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Create bad case" }));
    expect(screen.getByText("Wrong top 1")).toBeTruthy();
    expect(screen.queryByRole("option", { name: "Unsupported explanation" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "Confirm case creation" }));
    await waitFor(() => expect(createBadCase).toHaveBeenCalledWith(expect.objectContaining({
      source_type: "feedback",
      feedback_id: "feedback-3",
      symptom_code: "wrong_top1",
    })));
    expect((await screen.findByRole("link", { name: "Open bad case" })).getAttribute("href")).toBe("/bad-cases/case-1");
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
    await screen.findByText("Review recommendation");
    await user.click(screen.getByRole("button", { name: "Submit feedback" }));

    expect(await screen.findByText(/does not map to a BadCase symptom/i)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Create bad case" })).toBeNull();
  });
});

describe("BadCase screens", () => {
  it("renders a lightweight evidence-first list and a helpful empty state", async () => {
    vi.mocked(listBadCases).mockResolvedValueOnce({ success: true, data: { items: [detail], total: 1, limit: 20, offset: 0 }, error: null, request_id: "list-1" });
    const { unmount } = render(<BadCaseListScreen />);
    expect(await screen.findByRole("link", { name: /unsupported explanation/i })).toBeTruthy();
    expect(screen.getByText("REVIEWED")).toBeTruthy();
    unmount();

    vi.mocked(listBadCases).mockResolvedValueOnce({ success: true, data: { items: [], total: 0, limit: 20, offset: 0 }, error: null, request_id: "list-2" });
    render(<BadCaseListScreen />);
    expect(await screen.findByText("No bad cases need review")).toBeTruthy();
  });

  it("recovers the Bad Case queue after a transient API failure", async () => {
    vi.mocked(listBadCases)
      .mockRejectedValueOnce(new Phase10ApiError("Review service is temporarily unavailable", 503, "service_unavailable", "list-error"))
      .mockResolvedValueOnce({ success: true, data: { items: [detail], total: 1, limit: 20, offset: 0 }, error: null, request_id: "list-retry" });
    const user = userEvent.setup();
    render(<BadCaseListScreen />);

    expect(await screen.findByText("Review workspace unavailable")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Retry" }));

    expect(await screen.findByRole("link", { name: /unsupported explanation/i })).toBeTruthy();
    expect(listBadCases).toHaveBeenCalledTimes(2);
  });

  it("marks bounded history and treats the latest rejected analysis as current", async () => {
    vi.mocked(getBadCase).mockResolvedValue({ success: true, data: detail, error: null, request_id: "detail-1" });
    render(<BadCaseDetailScreen badCaseId="case-1" />);

    expect(await screen.findByText("Partial history")).toBeTruthy();
    expect(screen.getByText(/sources are bounded/i)).toBeTruthy();
    const current = screen.getByLabelText("Current effective analysis");
    expect(within(current).getByText(/^rejected ·/i)).toBeTruthy();
    expect(within(current).queryByText(/^supported\b/i)).toBeNull();
    expect(screen.getByRole("button", { name: "Identify root cause" })).toHaveProperty("disabled", true);
    expect(screen.getByText(/requires the latest analysis to be supported or confirmed/i)).toBeTruthy();
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

    expect(await screen.findByText(/current analysis is unavailable in this bounded projection/i)).toBeTruthy();
    expect(screen.queryByLabelText("Current effective analysis")).toBeNull();
    expect(screen.getByText(/current resolution state is unavailable in this bounded projection/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Add analysis" })).toHaveProperty("disabled", true);
    expect(screen.getByRole("button", { name: "Identify root cause" })).toHaveProperty("disabled", true);
    expect(screen.getByRole("button", { name: "Plan resolution" })).toHaveProperty("disabled", true);
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

    await user.click(await screen.findByRole("button", { name: "Update resolution" }));
    expect(screen.getByLabelText("Action type")).toHaveProperty("value", "template_change_hypothesis");
    await user.selectOptions(screen.getByLabelText("Action status"), "completed");
    await user.clear(screen.getByLabelText("Action description"));
    await user.type(screen.getByLabelText("Action description"), "Complete the remaining current action.");
    await user.type(screen.getByLabelText("Safe change reference"), "commit:remaining-action");
    await user.click(screen.getByRole("button", { name: "Save resolution action" }));

    await waitFor(() => expect(reviewBadCase).toHaveBeenCalledWith("case-1", expect.objectContaining({
      resolution: expect.objectContaining({ supersedes_action_id: 4 }),
    })));
  });

  it("uses closed review taxonomies instead of arbitrary mutation codes", async () => {
    vi.mocked(getBadCase).mockResolvedValue({ success: true, data: { ...detail, analyses: [detail.analyses[0]] }, error: null, request_id: "detail-1" });
    const user = userEvent.setup();
    render(<BadCaseDetailScreen badCaseId="case-1" />);
    await screen.findByLabelText("Current effective analysis");

    await user.click(screen.getByRole("button", { name: "Add analysis" }));
    expect(screen.getByLabelText("Root-cause code").tagName).toBe("SELECT");
    await user.click(screen.getByRole("button", { name: "Close" }));
    await user.click(screen.getByRole("button", { name: "Plan resolution" }));
    expect(screen.getByLabelText("Action type").tagName).toBe("SELECT");
    expect(screen.getByLabelText("Action status").tagName).toBe("SELECT");
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

    await user.click(await screen.findByRole("button", { name: "Mark duplicate" }));

    expect(await screen.findByLabelText("Canonical case")).toHaveProperty("tagName", "SELECT");
    expect(screen.queryByLabelText(/canonical case reference/i)).toBeNull();
    expect(screen.getByRole("option", { name: /unsupported explanation · reviewed/i })).toBeTruthy();
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

    const reopen = await screen.findByRole("button", { name: "Reopen review" });
    expect(screen.queryByRole("button", { name: "Mark duplicate" })).toBeNull();
    await user.click(reopen);

    expect(screen.getByLabelText("Bad case review workspace").getAttribute("aria-busy")).toBe("true");
    expect(screen.getByRole("button", { name: "Verify case" })).toHaveProperty("disabled", true);
    expect(reopen).toHaveProperty("disabled", true);
  });

  it("restores the review command trigger after dismissing its dialog", async () => {
    vi.mocked(getBadCase).mockResolvedValue({ success: true, data: detail, error: null, request_id: "detail-1" });
    const user = userEvent.setup();
    render(<BadCaseDetailScreen badCaseId="case-1" />);
    const trigger = await screen.findByRole("button", { name: "Add analysis" });
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

    await user.click(await screen.findByRole("button", { name: "Verify case" }));
    await user.type(screen.getByLabelText("Immutable verification reference"), "commit:case-verification");
    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Verify case" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("heading", { name: "unsupported explanation" })));
  });

  it("surfaces a stale revision without replaying the mutation and refreshes on demand", async () => {
    vi.mocked(getBadCase).mockResolvedValue({ success: true, data: detail, error: null, request_id: "detail-1" });
    vi.mocked(reviewBadCase).mockRejectedValue(new Phase10ApiError("This case changed", 409, "review_concurrency_conflict", "stale-1"));
    const user = userEvent.setup();
    render(<BadCaseDetailScreen badCaseId="case-1" />);

    await screen.findByLabelText("Current effective analysis");
    await user.click(screen.getByRole("button", { name: "Add analysis" }));
    await user.type(screen.getByLabelText("Assessment description"), "New bounded assessment");
    await user.click(screen.getByRole("button", { name: "Save analysis" }));

    expect(await screen.findByText("This case changed since you opened it.")).toBeTruthy();
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(reviewBadCase).toHaveBeenCalledTimes(1);
    await user.click(screen.getByRole("button", { name: "Refresh latest case" }));
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

    await screen.findByLabelText("Current effective analysis");
    await user.click(screen.getByRole("button", { name: "Add analysis" }));
    await user.type(screen.getByLabelText("Assessment description"), "New bounded assessment");
    await user.click(screen.getByRole("button", { name: "Save analysis" }));
    const refresh = await screen.findByRole("button", { name: "Refresh latest case" });
    await user.click(refresh);
    await user.click(refresh);
    expect(getBadCase).toHaveBeenCalledTimes(3);

    resolveLatest({ success: true, data: { ...detail, revision: 3 }, error: null, request_id: "detail-latest" });
    await waitFor(() => expect(within(screen.getByText("Revision").parentElement!).getByText("3")).toBeTruthy());
    await act(async () => {
      resolveOlder({ success: true, data: { ...detail, revision: 2 }, error: null, request_id: "detail-older" });
      await older;
    });
    expect(within(screen.getByText("Revision").parentElement!).getByText("3")).toBeTruthy();
  });

  it("keeps a semantic 422 beside the active command without exposing raw data", async () => {
    vi.mocked(getBadCase).mockResolvedValue({ success: true, data: detail, error: null, request_id: "detail-1" });
    vi.mocked(reviewBadCase).mockRejectedValue(new Phase10ApiError("Historical evidence kind is incompatible", 422, "review_eligibility", "semantic-1"));
    const user = userEvent.setup();
    render(<BadCaseDetailScreen badCaseId="case-1" />);

    await screen.findByLabelText("Current effective analysis");
    await user.click(screen.getByRole("button", { name: "Add analysis" }));
    await user.type(screen.getByLabelText("Assessment description"), "Bounded semantic test");
    await user.click(screen.getByRole("button", { name: "Save analysis" }));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByRole("alert").textContent).toContain("Historical evidence kind is incompatible");
    expect(within(dialog).queryByText(/sql|traceback/i)).toBeNull();
  });
});
