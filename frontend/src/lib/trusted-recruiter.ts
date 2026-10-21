import { getExplanationRun, getMatchRun, listExplanationRuns } from "@/lib/phase10-api";
import type { CandidateRecord, JobDraft } from "@/types/demo";
import type { StructuredRecruiterBrief, RecruiterProposition, TrustedRecruiterRun } from "@/types/trusted-recruiter";

type Ranked = { candidate_id: string; result_rank: number };
type RunIdentity = { run_id: string; result_fingerprint: string; results: Ranked[] };
type ExplanationIdentity = { explanation_run_id: string; match_run_id: string; status: string; explanations: Array<Ranked & { match_explanation_id: number }> };

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function stringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}
function isProposition(value: unknown): value is RecruiterProposition {
  return isRecord(value) && typeof value.proposition_id === "string" && typeof value.candidate_id === "string"
    && Number.isInteger(value.result_rank) && typeof value.kind === "string" && typeof value.predicate === "string"
    && typeof value.subject === "string" && typeof value.modality === "string" && typeof value.polarity === "string"
    && stringArray(value.topic_terms) && stringArray(value.job_requirement_terms)
    && stringArray(value.source_fact_ids) && stringArray(value.source_claim_ids)
    && stringArray(value.evidence_refs) && stringArray(value.job_requirement_refs) && stringArray(value.allowed_fields);
}
function isBrief(value: unknown): value is StructuredRecruiterBrief {
  return isRecord(value) && value.contract_version === "structured_recruiter_brief_v1"
    && value.review_status === "TRUSTED_STRUCTURED" && typeof value.match_run_id === "string"
    && typeof value.explanation_run_id === "string" && Number.isInteger(value.source_explanation_id)
    && typeof value.candidate_id === "string" && Number.isInteger(value.result_rank)
    && typeof value.ranking_fingerprint === "string" && typeof value.source_output_fingerprint === "string"
    && typeof value.source_bundle_fingerprint === "string" && [value.ranking_fingerprint, value.source_output_fingerprint, value.source_bundle_fingerprint].every((item) => /^[a-f0-9]{64}$/.test(String(item)))
    && (value.review_action === null || isProposition(value.review_action))
    && [value.why_review, value.technical_signals, value.unknowns, value.verification_targets]
      .every((items) => Array.isArray(items) && items.every(isProposition));
}

export function assertTrustedBriefs(run: RunIdentity, explanation: ExplanationIdentity, briefs: StructuredRecruiterBrief[]): StructuredRecruiterBrief[] {
  if (explanation.status !== "COMPLETED" || explanation.match_run_id !== run.run_id
    || briefs.length !== run.results.length || explanation.explanations.length !== run.results.length) {
    throw new Error("trusted_run_ownership_mismatch");
  }
  const seen = new Set<string>();
  for (const ranked of run.results) {
    const source = explanation.explanations.find((item) => item.candidate_id === ranked.candidate_id && item.result_rank === ranked.result_rank);
    const brief = briefs.find((item) => item.candidate_id === ranked.candidate_id && item.result_rank === ranked.result_rank);
    if (!source || !brief || seen.has(brief.candidate_id)
      || brief.match_run_id !== run.run_id || brief.explanation_run_id !== explanation.explanation_run_id
      || brief.source_explanation_id !== source.match_explanation_id || brief.ranking_fingerprint !== run.result_fingerprint) {
      throw new Error("trusted_brief_source_mismatch");
    }
    seen.add(brief.candidate_id);
    const propositions = [brief.review_action, ...brief.why_review, ...brief.technical_signals, ...brief.unknowns, ...brief.verification_targets].filter((item): item is RecruiterProposition => item !== null);
    if (propositions.some((item) => item.candidate_id !== brief.candidate_id || item.result_rank !== brief.result_rank
      || !item.source_fact_ids.length || !item.evidence_refs.length
      || item.evidence_refs.some((ref) => ref.startsWith("candidate:") && !ref.startsWith(`candidate:${brief.result_rank}:`)))) {
      throw new Error("trusted_brief_provenance_mismatch");
    }
  }
  return [...briefs].sort((left, right) => left.result_rank - right.result_rank);
}

export function reviewActionLabel(action: RecruiterProposition | null): string {
  if (action?.predicate === "prioritize_technical_review") return "优先人工技术复核";
  if (action?.predicate === "consider_targeted_screen") return "先做定向筛查";
  return "人工评估";
}

export function propositionLabel(item: RecruiterProposition): string {
  const topic = item.topic_terms.join(" · ");
  const requirement = item.job_requirement_terms.join(" · ");
  switch (item.predicate) {
    case "overlaps_job_requirement": return `岗位关联：${topic}${requirement ? ` ↔ ${requirement}` : ""}`;
    case "lists_project_technologies": return `项目材料列出：${topic}`;
    case "lists_skill": return `技能档案列出：${topic}`;
    case "requirement_evidence_not_established": return `尚待核实岗位要求：${requirement || topic}`;
    case "project_scope_not_established": return `尚待核实项目参与范围：${topic}`;
    case "verify_open_requirement": return `先核实岗位要求：${requirement || topic}`;
    case "verify_project_scope": return `先核实实际参与范围：${topic}`;
    default: return topic;
  }
}

export function primaryVerificationTarget(brief: StructuredRecruiterBrief, unknowns: RecruiterProposition[]): RecruiterProposition | null {
  const importantRefs = new Set(unknowns[0]?.job_requirement_refs ?? []);
  return brief.verification_targets.find((item) => item.predicate === "verify_open_requirement"
    && item.job_requirement_refs.some((ref) => importantRefs.has(ref)))
    ?? brief.verification_targets.find((item) => item.predicate === "verify_open_requirement")
    ?? brief.verification_targets[0] ?? null;
}

export function verificationPrompt(item: RecruiterProposition): string {
  if (item.predicate === "verify_open_requirement") {
    return `先确认是否有与「${item.topic_terms.join(" · ")}」相关、可说明的证据。`;
  }
  if (item.predicate === "verify_project_scope") return "先确认在相关项目中的实际参与范围。";
  return propositionLabel(item);
}

async function readApi<T>(path: string, valid: (data: unknown) => data is T): Promise<T> {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (!base) throw new Error("后端 API 未配置。");
  const response = await fetch(`${base.replace(/\/$/, "")}${path}`, { cache: "no-store", headers: { Accept: "application/json" } });
  const envelope: unknown = await response.json();
  if (!response.ok || !isRecord(envelope) || envelope.success !== true || !valid(envelope.data)) {
    throw new Error("可信记录读取失败或响应契约不一致。");
  }
  return envelope.data;
}

async function getBrief(explanationId: number): Promise<StructuredRecruiterBrief> {
  return readApi(`/api/v1/match-explanations/${explanationId}/recruiter-propositions`, isBrief);
}

export async function loadTrustedRecruiterRun(runId: string, explanationRunId?: string): Promise<TrustedRecruiterRun> {
  const matchRun = (await getMatchRun(runId)).data;
  if (matchRun.status !== "COMPLETED" || !matchRun.job_id || !/^[a-f0-9]{64}$/.test(String(matchRun.result_fingerprint))) {
    throw new Error("MatchRun 尚未完成或缺少排序指纹。");
  }
  let selectedId = explanationRunId;
  if (selectedId === undefined) {
    const histories = (await listExplanationRuns(runId)).data;
    const complete = histories.items.filter((item) => item.status === "COMPLETED")
      .sort((left, right) => (right.completed_at ?? "").localeCompare(left.completed_at ?? ""))[0];
    if (!complete) throw new Error("此 MatchRun 尚无完成的可信解释。");
    selectedId = complete.explanation_run_id;
  }
  if (!selectedId) throw new Error("ExplanationRun 身份缺失。");
  const explanationRun = (await getExplanationRun(selectedId)).data;
  const briefs = await Promise.all(explanationRun.explanations.map((item) => getBrief(item.match_explanation_id)));
  assertTrustedBriefs(matchRun as typeof matchRun & { result_fingerprint: string }, explanationRun, briefs);
  const job = await readApi(`/api/v1/jobs/${encodeURIComponent(matchRun.job_id)}`, (value): value is JobDraft => isRecord(value) && typeof value.role_title === "string" && Array.isArray(value.must_have) && Array.isArray(value.nice_to_have));
  const candidates: Record<string, CandidateRecord> = {};
  await Promise.all(matchRun.results.map(async (item) => {
    try {
      const candidate = await readApi(`/api/v1/candidates/${encodeURIComponent(item.candidate_id)}`, (value): value is CandidateRecord => isRecord(value) && value.candidate_id === item.candidate_id && typeof value.name === "string" && Array.isArray(value.projects) && Array.isArray(value.skills));
      candidates[item.candidate_id] = candidate;
    } catch { /* A missing display profile does not create a trusted claim. */ }
  }));
  return { matchRun: matchRun as typeof matchRun & { result_fingerprint: string }, explanationRun, briefs, job, candidates };
}
