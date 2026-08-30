import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createFeedback,
  getBadCase,
  listExplanationRuns,
  listBadCases,
  reviewBadCase,
} from "./phase10-api";
import type { FeedbackRecord } from "@/types/phase10";


describe("Phase 10 API client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("submits an opaque persisted MatchResult locator without duplicated identity", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000/");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          success: true,
          data: {
            feedback_id: "feedback-1",
            contract_version: "feedback_record_v1",
            origin: "human",
            job_id: "job-1",
            created_at: "2026-08-29T00:00:00Z",
            feedback_type: "ranking",
            match_run_id: "run-1",
            target_type: "candidate_result",
            subject_match_result_id: 41,
            comparison_match_result_id: null,
            expected_candidate_reference: null,
            value: "correct",
            reason_code: null,
          },
          error: null,
          request_id: "request-feedback",
        }),
        { status: 201, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await createFeedback({
      feedback_type: "ranking",
      match_run_id: "run-1",
      target_type: "candidate_result",
      subject_match_result_id: 41,
      value: "correct",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/feedback",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          feedback_type: "ranking",
          match_run_id: "run-1",
          target_type: "candidate_result",
          subject_match_result_id: 41,
          value: "correct",
        }),
      }),
    );
  });

  it("maps a stale review to a typed 409 error with a safe request id", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            success: false,
            data: null,
            error: {
              code: "review_concurrency_conflict",
              message: "BadCase review is stale",
              details: null,
            },
            request_id: "request-stale",
          }),
          { status: 409, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    await expect(
      reviewBadCase("case-1", {
        command: "transition",
        expected_status: "CREATED",
        expected_revision: 0,
        status: "REVIEWED",
        transition_reason: "review_completed",
      }),
    ).rejects.toMatchObject({
      status: 409,
      code: "review_concurrency_conflict",
      requestId: "request-stale",
      message: "BadCase review is stale",
    });
  });

  it("uses bounded list and detail queries", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            success: true,
            data: { items: [], total: 0, limit: 20, offset: 0 },
            error: null,
            request_id: "request-list",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ success: false, data: null, error: { code: "not_found", message: "Not found", details: null }, request_id: "request-detail" }),
          { status: 404, headers: { "Content-Type": "application/json" } },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    await listBadCases({ limit: 20, offset: 0 });
    await expect(getBadCase("case-1", 100)).rejects.toMatchObject({ status: 404 });

    expect(fetchMock.mock.calls[0][0]).toBe(
      "http://localhost:8000/api/v1/bad-cases?limit=20&offset=0",
    );
    expect(fetchMock.mock.calls[1][0]).toBe(
      "http://localhost:8000/api/v1/bad-cases/case-1?child_limit=100",
    );
  });

  it("rejects a malformed successful review response instead of treating it as historical truth", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            success: true,
            data: { bad_case_id: "case-1" },
            error: null,
            request_id: "request-malformed",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    await expect(getBadCase("case-1")).rejects.toMatchObject({
      status: 200,
      code: "invalid_response",
      requestId: "request-malformed",
    });
  });

  it("rejects a successful response envelope that also carries an error", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            success: true,
            data: { items: [], total: 0, limit: 20, offset: 0 },
            error: { code: "contradictory_envelope", message: "must not be accepted", details: null },
            request_id: "request-contradictory-envelope",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    await expect(listBadCases({ limit: 20, offset: 0 })).rejects.toMatchObject({
      status: 200,
      code: "invalid_response",
      requestId: "request-contradictory-envelope",
    });
  });

  it("rejects unknown values in a successful discriminated Feedback response", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            success: true,
            data: {
              feedback_id: "feedback-closed-contract",
              contract_version: "feedback_record_v1",
              origin: "human",
              job_id: "job-1",
              created_at: "2026-08-29T00:00:00Z",
              feedback_type: "ranking",
              match_run_id: "run-1",
              target_type: "candidate_result",
              value: "model_fixed",
            },
            error: null,
            request_id: "request-unknown-feedback-value",
          }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    await expect(createFeedback({
      feedback_type: "ranking",
      match_run_id: "run-1",
      target_type: "candidate_result",
      subject_match_result_id: 41,
      value: "correct",
    })).rejects.toMatchObject({
      status: 201,
      code: "invalid_response",
      requestId: "request-unknown-feedback-value",
    });
  });

  it.each([
    ["unknown target", { feedback_type: "ranking", target_type: "global_model", value: "correct" }],
    ["unknown discriminator", { feedback_type: "model_evaluation", target_type: "candidate_result", value: "correct" }],
    ["invalid nested selector", { feedback_type: "ranking", target_type: "pairwise", value: "wrong", reason_code: "ranking_inversion", subject_match_result_id: 41, comparison_match_result_id: 41 }],
  ])("rejects an %s in a successful Feedback response", async (_label, variant) => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            success: true,
            data: {
              feedback_id: "feedback-invalid-discriminator",
              contract_version: "feedback_record_v1",
              origin: "human",
              job_id: "job-1",
              created_at: "2026-08-29T00:00:00Z",
              match_run_id: "run-1",
              ...variant,
            },
            error: null,
            request_id: "request-invalid-discriminator",
          }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    await expect(createFeedback({
      feedback_type: "ranking",
      match_run_id: "run-1",
      target_type: "candidate_result",
      subject_match_result_id: 41,
      value: "correct",
    })).rejects.toMatchObject({
      status: 201,
      code: "invalid_response",
      requestId: "request-invalid-discriminator",
    });
  });

  it("rejects an unknown ExplanationRun status from historical context", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            success: true,
            data: {
              items: [{
                explanation_run_id: "explanation-run-1",
                match_run_id: "run-1",
                status: "PARTIALLY_GROUNDED",
                explanation_count: 1,
                created_at: "2026-08-29T00:00:00Z",
                completed_at: null,
              }],
              total: 1,
              limit: 20,
              offset: 0,
            },
            error: null,
            request_id: "request-unknown-explanation-status",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    await expect(listExplanationRuns("run-1")).rejects.toMatchObject({
      status: 200,
      code: "invalid_response",
      requestId: "request-unknown-explanation-status",
    });
  });

  it("represents nullable server-owned feedback fields without request-shape casts", () => {
    const record: FeedbackRecord = {
      feedback_id: "feedback-run",
      contract_version: "feedback_record_v1",
      origin: "human",
      job_id: "job-1",
      candidate_id: null,
      result_rank: null,
      comparison_candidate_id: null,
      comparison_result_rank: null,
      created_at: "2026-08-29T00:00:00Z",
      match_run_id: "run-1",
      comment: null,
      supersedes_feedback_id: null,
      feedback_type: "ranking",
      target_type: "overall_ranking",
      subject_match_result_id: null,
      comparison_match_result_id: null,
      expected_candidate_reference: null,
      value: "uncertain",
      reason_code: null,
    };

    expect(record.candidate_id).toBeNull();
  });
});
