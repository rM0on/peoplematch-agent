import type { RequirementReview, RequirementReviewRow } from "@/types/requirement-review";
import type { RecruiterProposition } from "@/types/trusted-recruiter";

const policy = {
  project_observation: { subject: "project_material", predicates: ["lists_project_technologies"], modality: "fact", polarity: "affirmative", fields: ["technical_signal"] },
  listed_skill_observation: { subject: "candidate_material", predicates: ["lists_skill"], modality: "fact", polarity: "affirmative", fields: ["technical_signal"] },
  technical_alignment: { subject: "candidate_material", predicates: ["overlaps_job_requirement"], modality: "alignment", polarity: "affirmative", fields: ["why_consider", "technical_signal"] },
  interview_target: { subject: "interview_process", predicates: ["verify_project_scope", "verify_open_requirement"], modality: "hypothesis", polarity: "undetermined", fields: ["interview_focus"] },
  material_unknown: { subject: "selected_material", predicates: ["project_scope_not_established", "requirement_evidence_not_established"], modality: "unknown", polarity: "undetermined", fields: ["uncertainty"] },
  human_review_recommendation: { subject: "human_review", predicates: ["prioritize_technical_review", "consider_targeted_screen"], modality: "recommendation", polarity: "undetermined", fields: ["decision_summary", "why_consider"] },
} as const;

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function strings(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}
function fingerprint(value: unknown): value is string {
  return typeof value === "string" && /^[a-f0-9]{64}$/.test(value);
}
function canonicalCandidateRef(ref: string, rank: unknown): boolean {
  if (typeof rank !== "number" || !Number.isInteger(rank) || rank < 1) return false;
  const match = /^candidate:([1-9][0-9]*):(?:skill:[a-f0-9]{32,64}|(?:project|project_evidence):[A-Za-z0-9_.-]{1,100})$/.exec(ref);
  return match !== null && Number(match[1]) === rank;
}
function proposition(value: unknown): value is RecruiterProposition {
  if (!record(value) || typeof value.kind !== "string" || !(value.kind in policy)) return false;
  if (!strings(value.evidence_refs) || !strings(value.job_requirement_refs)) return false;
  const jobRefsInEvidence = value.evidence_refs.filter((ref) => ref.startsWith("job_requirement:"));
  if (new Set(value.evidence_refs).size !== value.evidence_refs.length
    || jobRefsInEvidence.join("|") !== value.job_requirement_refs.join("|")
    || value.evidence_refs.some((ref) => ref.startsWith("candidate:") && !canonicalCandidateRef(ref, value.result_rank))
    || value.evidence_refs.some((ref) => !ref.startsWith("candidate:") && !ref.startsWith("job_requirement:"))) return false;
  const expected = policy[value.kind as keyof typeof policy];
  const hasJob = value.kind === "technical_alignment" || value.kind === "human_review_recommendation"
    || value.predicate === "verify_open_requirement" || value.predicate === "requirement_evidence_not_established";
  return typeof value.proposition_id === "string" && value.proposition_id.length >= 8 && typeof value.candidate_id === "string"
    && Number.isInteger(value.result_rank) && typeof value.predicate === "string" && expected.predicates.some((item) => item === value.predicate)
    && value.subject === expected.subject && value.modality === expected.modality && value.polarity === expected.polarity
    && strings(value.topic_terms) && value.topic_terms.length > 0 && strings(value.job_requirement_terms)
    && strings(value.source_fact_ids) && value.source_fact_ids.length > 0 && strings(value.source_claim_ids)
    && strings(value.allowed_fields) && value.allowed_fields.join("|") === expected.fields.join("|")
    && strings(value.evidence_refs) && value.evidence_refs.length > 0 && strings(value.job_requirement_refs)
    && (!hasJob || (value.job_requirement_refs.length > 0 && value.job_requirement_terms.length > 0));
}
function row(value: unknown): value is RequirementReviewRow {
  if (!record(value) || !strings(value.source_refs) || value.source_refs.length !== 1) return false;
  const sourceRef = value.source_refs[0];
  return record(value) && typeof value.requirement_id === "string" && value.requirement_id.length > 0
    && (value.priority === "must_have" || value.priority === "nice_to_have")
    && typeof value.text === "string" && value.text.length > 0
    && ["matched", "partial", "missing", "not_assessed"].includes(String(value.diagnostic_status))
    && ["available", "claim_only", "absent", "not_assessed"].includes(String(value.evidence_status))
    && sourceRef === `job_requirement:${value.requirement_id}`
    && Array.isArray(value.propositions) && value.propositions.every((item) => proposition(item)
      && item.job_requirement_refs.length === 1 && item.job_requirement_refs[0] === sourceRef);
}
export function isRequirementReview(value: unknown): value is RequirementReview {
  if (!record(value) || !Array.isArray(value.source_descriptors)) return false;
  const descriptors = value.source_descriptors;
  const descriptorRefs = new Set<string>();
  for (const item of descriptors) {
    if (!record(item) || typeof item.evidence_ref !== "string" || typeof item.description !== "string" || !item.description.trim()
      || typeof item.source_kind !== "string" || descriptorRefs.has(item.evidence_ref)
      || !canonicalCandidateRef(item.evidence_ref, value.result_rank)) return false;
    const namespace = item.evidence_ref.split(":")[2];
    if ((namespace === "skill" && item.source_kind !== "historical_skill_claim")
      || (namespace === "project" && item.source_kind !== "historical_project")
      || (namespace === "project_evidence" && item.source_kind !== "historical_project_record")
      || !["skill", "project", "project_evidence"].includes(namespace)) return false;
    descriptorRefs.add(item.evidence_ref);
  }
  const cited = [...(Array.isArray(value.requirements) ? value.requirements.flatMap((item) => record(item) && Array.isArray(item.propositions) ? item.propositions : []) : []),
    ...(Array.isArray(value.cross_requirement_propositions) ? value.cross_requirement_propositions : [])]
    .flatMap((item) => record(item) && strings(item.evidence_refs) ? item.evidence_refs : [])
    .filter((ref) => ref.startsWith("candidate:"));
  if (cited.some((ref) => !descriptorRefs.has(ref)) || descriptors.some((item) => !cited.includes(item.evidence_ref))) return false;
  return value.contract_version === "requirement_review_v1"
    && typeof value.role_title === "string" && value.role_title.length > 0
    && typeof value.match_run_id === "string" && value.match_run_id.length > 0
    && typeof value.explanation_run_id === "string" && value.explanation_run_id.length > 0
    && Number.isInteger(value.source_explanation_id) && Number.isInteger(value.result_rank)
    && typeof value.candidate_id === "string" && fingerprint(value.ranking_fingerprint)
    && fingerprint(value.source_output_fingerprint) && fingerprint(value.source_bundle_fingerprint)
    && Array.isArray(value.requirements) && value.requirements.length > 0 && value.requirements.every(row)
    && Array.isArray(value.cross_requirement_propositions)
    && value.cross_requirement_propositions.every((item) => proposition(item) && item.job_requirement_refs.length > 1);
}
type Identity = {
  matchRun: { run_id: string; result_fingerprint: string; results: Array<{ candidate_id: string; result_rank: number }> };
  explanationRun: { explanation_run_id: string; explanations: Array<{ match_explanation_id: number; candidate_id: string; result_rank: number }> };
  briefs: Array<{ source_explanation_id: number; candidate_id: string; result_rank: number; source_output_fingerprint: string; source_bundle_fingerprint: string }>;
};
export function assertRequirementReviewOwnership(review: RequirementReview, run: Identity): RequirementReview {
  const source = run.explanationRun.explanations.find((item) => item.match_explanation_id === review.source_explanation_id);
  const brief = run.briefs.find((item) => item.source_explanation_id === review.source_explanation_id);
  const ranked = run.matchRun.results.find((item) => item.candidate_id === review.candidate_id && item.result_rank === review.result_rank);
  const ids = review.requirements.map((item) => item.requirement_id);
  if (!source || !brief || !ranked || review.match_run_id !== run.matchRun.run_id
    || review.explanation_run_id !== run.explanationRun.explanation_run_id
    || review.ranking_fingerprint !== run.matchRun.result_fingerprint
    || source.candidate_id !== review.candidate_id || source.result_rank !== review.result_rank
    || brief.candidate_id !== review.candidate_id || brief.result_rank !== review.result_rank
    || brief.source_bundle_fingerprint !== review.source_bundle_fingerprint
    || brief.source_output_fingerprint !== review.source_output_fingerprint
    || ids.length !== new Set(ids).size
    || review.requirements.some((item) => item.propositions.some((entry) =>
      entry.candidate_id !== review.candidate_id || entry.result_rank !== review.result_rank
      || !entry.job_requirement_refs.includes(`job_requirement:${item.requirement_id}`)
      || entry.evidence_refs.some((ref) => ref.startsWith("candidate:") && !ref.startsWith(`candidate:${review.result_rank}:`))
    )) || review.cross_requirement_propositions.some((entry) =>
      entry.candidate_id !== review.candidate_id || entry.result_rank !== review.result_rank
      || entry.job_requirement_refs.some((ref) => !ids.includes(ref.slice("job_requirement:".length)))
      || entry.evidence_refs.some((ref) => ref.startsWith("candidate:") && !ref.startsWith(`candidate:${review.result_rank}:`))
    )) throw new Error("requirement_review_source_mismatch");
  return review;
}
export async function loadRequirementReview(explanationId: number): Promise<RequirementReview> {
  if (!Number.isSafeInteger(explanationId) || explanationId <= 0) throw new Error("invalid_explanation_id");
  const base = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (!base) throw new Error("API base URL is not configured");
  const response = await fetch(`${base.replace(/\/$/, "")}/api/v1/match-explanations/${explanationId}/requirement-review`,
    { cache: "no-store", headers: { Accept: "application/json" } });
  const envelope: unknown = await response.json();
  if (!response.ok || !record(envelope) || envelope.success !== true || !isRequirementReview(envelope.data))
    throw new Error("requirement_review_response_invalid");
  if (envelope.data.source_explanation_id !== explanationId) throw new Error("requirement_review_source_mismatch");
  return envelope.data;
}
