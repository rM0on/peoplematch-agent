import { afterEach, describe, expect, it, vi } from "vitest";

import { DemoApiError, fetchDemoSamples, runDemo } from "./demo-api";


const candidateDraft = {
  name: "Candidate Parse Demo",
  skills: [{ name: "Python", category: "backend", self_reported_level: "advanced" }],
  projects: [{
    project_id: "project-1",
    name: "Matching Console",
    summary: "Built a synthetic matching console.",
    role: "Developer",
    technologies: ["Python"],
    outcomes: ["Added deterministic tests"],
    skills_demonstrated: ["Python"],
  }],
  project_evidence: [{
    evidence_id: "evidence-1",
    project_id: "project-1",
    supports_skills: ["Python"],
    evidence_type: "tests",
    statement: "Tests demonstrate the matching workflow.",
    artifact_ref: "sandbox://demo/tests",
    verification_status: "available",
  }],
  github_url: null,
  ai_tools: ["FastAPI"],
  target_roles: ["AI Engineer"],
  preferred_locations: { cities: ["Shanghai"], remote_policy: "hybrid", relocation_open: false },
  seniority: "mid",
  work_style: { team_stage_preference: ["zero_to_one"], collaboration_style: "Collaborative" },
  missing_fields: ["years_of_experience"],
  overclaim_risk: { level: "low", reasons: [] },
};

const jobDraft = {
  company_name: "Northstar Sandbox Labs",
  role_title: "AI Matching Engineer",
  must_have: [{
    requirement_id: "requirement-1",
    text: "Build matching systems",
    category: "role_direction",
    evidence_expectation: "A working project",
  }],
  nice_to_have: [],
  role_direction: ["matching"],
  team_tags: ["zero_to_one"],
  location: { cities: ["Shanghai"], remote_policy: "hybrid", relocation_supported: true },
  seniority_requirement: ["mid"],
  product_stage: "zero_to_one",
  evaluation_focus: ["project evidence"],
};

function envelope(data: unknown, requestId: string, status = 200) {
  return new Response(JSON.stringify({ success: true, data, error: null, request_id: requestId }), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function parseData(kind: "candidate" | "job") {
  const draft = kind === "candidate" ? candidateDraft : jobDraft;
  return {
    draft,
    record: {
      ...(kind === "candidate" ? { candidate_id: "cand_parse_demo" } : { job_id: "job_parse_demo" }),
      ...draft,
      data_origin: "mock_parsed",
      schema_version: "1.0",
      dataset_version: null,
    },
    extraction: {
      provider: "deterministic_mock",
      provider_kind: "mock",
      attempts: 1,
      repaired: false,
      persisted: true,
      input_fingerprint: "a".repeat(64),
    },
  };
}

const matchRun = {
  run_id: "run-demo",
  requested_job_id: "job_parse_demo",
  job_id: "job_parse_demo",
  ranking_variant: "ltr",
  status: "COMPLETED",
  created_at: "2026-09-01T00:00:00Z",
  completed_at: "2026-09-01T00:00:01Z",
  result_count: 1,
  result_fingerprint: "b".repeat(64),
  results: [{
    match_result_id: 41,
    candidate_id: "cand_parse_demo",
    result_rank: 1,
    retrieval_rank: 2,
    ltr_rank: 1,
    ltr_score_raw: 1.25,
    cross_encoder_rank: null,
    cross_encoder_score_raw: null,
    skill_fit_score: 0.9,
    project_evidence_score: 0.8,
    role_direction_score: 0.7,
    location_score: 1,
    seniority_score: 0.5,
    feature_diagnostics: {},
  }],
  steps: [{ sequence: 1, step_name: "retrieve_candidates", status: "COMPLETED", duration_ms: 12.5 }],
};

const explanationRun = {
  explanation_run_id: "explanation-demo",
  match_run_id: "run-demo",
  status: "COMPLETED",
  explanation_count: 1,
  created_at: "2026-09-01T00:00:01Z",
  completed_at: "2026-09-01T00:00:02Z",
  explanations: [{
    match_explanation_id: 51,
    output_schema_version: "explanation_output_v1",
    candidate_id: "cand_parse_demo",
    result_rank: 1,
    summary: { text: "候选人的结构化项目证据支持该排名。", evidence_refs: ["candidate:1:project:1"] },
    match_reasons: [{ category: "skill_fit", text: "技能与岗位要求有记录内重合。", evidence_refs: ["candidate:1:skill:1"] }],
    risk_points: [],
    missing_skills: [{
      requirement_id: "requirement-2",
      requirement_text: "Provide incident response evidence",
      priority: "nice_to_have",
      status: "missing",
      evidence_status: "absent",
      evidence_refs: ["job_requirement:requirement-2"],
    }],
    interview_questions: [],
    why_not_top1: null,
  }],
};


describe("Phase 12 demo API", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("loads exact synthetic sample text without trimming", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000/");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(envelope({
      data_origin: "synthetic_sandbox",
      candidate_text: "Synthetic candidate\n",
      job_text: "Synthetic job\n",
    }, "samples")));

    await expect(fetchDemoSamples()).resolves.toEqual({
      data_origin: "synthetic_sandbox",
      candidate_text: "Synthetic candidate\n",
      job_text: "Synthetic job\n",
    });
  });

  it("runs the explicit extraction to grounded explanation pipeline and reports stages", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(envelope(parseData("candidate"), "candidate", 200))
      .mockResolvedValueOnce(envelope(parseData("job"), "job", 200))
      .mockResolvedValueOnce(envelope({
        document_version: "retrieval_doc_v4",
        candidate_collection: "candidates",
        job_collection: "jobs",
        candidate_count: 49,
        job_count: 25,
      }, "index"))
      .mockResolvedValueOnce(envelope(matchRun, "match", 201))
      .mockResolvedValueOnce(envelope(explanationRun, "explanation", 201));
    vi.stubGlobal("fetch", fetchMock);
    const stages: string[] = [];

    const result = await runDemo({
      candidateText: "candidate source ".repeat(8),
      jobText: "job source ".repeat(10),
      onStage: (stage) => stages.push(stage),
    });

    expect(stages).toEqual(["candidate", "job", "index", "ranking", "explanation", "complete"]);
    expect(result.candidate.record?.candidate_id).toBe("cand_parse_demo");
    expect(result.job.record?.job_id).toBe("job_parse_demo");
    expect(result.matchRun.result_fingerprint).toBe("b".repeat(64));
    expect(result.explanationRun.explanations[0].summary.text).toContain("结构化项目证据");
    expect(result.explanationRun.explanations[0].missing_skills[0].requirement_text).toBe("Provide incident response evidence");
    expect(fetchMock.mock.calls.map((call) => call[0])).toEqual([
      "http://localhost:8000/api/v1/candidates/parse",
      "http://localhost:8000/api/v1/jobs/parse",
      "http://localhost:8000/api/v1/demo/rebuild-retrieval-index",
      "http://localhost:8000/api/v1/match-runs",
      "http://localhost:8000/api/v1/match-runs/run-demo/explanations",
    ]);
    expect(fetchMock.mock.calls[0][1]).toEqual(expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ text: "candidate source ".repeat(8), persist: true }),
    }));
    expect(fetchMock.mock.calls[2][1]).toEqual(expect.objectContaining({
      body: JSON.stringify({ confirm: true }),
    }));
    expect(fetchMock.mock.calls[3][1]).toEqual(expect.objectContaining({
      body: JSON.stringify({ job_id: "job_parse_demo", ranking_variant: "ltr", candidate_pool_k: 20, top_k: 5 }),
    }));
  });

  it("fails closed on malformed success instead of showing fabricated results", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(envelope({ draft: {} }, "malformed")));

    await expect(runDemo({
      candidateText: "candidate source ".repeat(8),
      jobText: "job source ".repeat(10),
    })).rejects.toMatchObject({ code: "invalid_response", requestId: "malformed" });
  });

  it("rejects malformed candidate fields that are outside the ranking display projection", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    const candidate = parseData("candidate");
    const malformed = {
      ...candidate,
      draft: { ...candidate.draft, ai_tools: [42] },
      record: { ...candidate.record, ai_tools: [42] },
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(envelope(malformed, "malformed-candidate")));

    await expect(runDemo({
      candidateText: "candidate source ".repeat(8),
      jobText: "job source ".repeat(10),
    })).rejects.toMatchObject({ code: "invalid_response", requestId: "malformed-candidate" });
  });

  it("maps backend failures to a safe recoverable error without leaking details", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      success: false,
      data: null,
      error: { code: "provider_unavailable", message: "Extraction provider is unavailable", details: null },
      request_id: "provider-error",
    }), { status: 503, headers: { "Content-Type": "application/json" } })));

    const error = await runDemo({
      candidateText: "candidate source ".repeat(8),
      jobText: "job source ".repeat(10),
    }).catch((caught) => caught);

    expect(error).toBeInstanceOf(DemoApiError);
    expect(error).toMatchObject({ status: 503, code: "provider_unavailable", requestId: "provider-error" });
    expect(String(error)).not.toContain("Bearer");
  });
});
