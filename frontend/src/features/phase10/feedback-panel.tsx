"use client";

import { FormEvent, KeyboardEvent, useMemo, useState } from "react";

import { createFeedback, Phase10ApiError } from "@/lib/phase10-api";
import type {
  ExplanationRunDetail,
  FeedbackCreateRequest,
  FeedbackRecord,
  MatchRunDetail,
  ProfileDataIssue,
  ProfileFieldLocator,
  RankingReasonCode,
  RankingTargetType,
} from "@/types/phase10";

import styles from "./phase10.module.css";


type FeedbackKind = "ranking" | "explanation" | "profile_data";
const feedbackKinds: readonly FeedbackKind[] = ["ranking", "explanation", "profile_data"];

const rankingReasons: Record<RankingTargetType, readonly RankingReasonCode[]> = {
  overall_ranking: ["constraint_conflict", "evidence_coverage_disagreement"],
  top1: ["wrong_top1"],
  candidate_result: ["false_positive", "constraint_conflict", "evidence_coverage_disagreement"],
  pairwise: ["ranking_inversion", "constraint_conflict", "evidence_coverage_disagreement"],
  expected_candidate: ["false_negative"],
};

const candidateIssues = [
  ["missing_skill", "candidate.skills"],
  ["incorrect_skill", "candidate.skills"],
  ["missing_project_evidence", "candidate.project_evidence"],
  ["incorrect_project_evidence_status", "candidate.project_evidence"],
  ["incorrect_seniority", "candidate.seniority"],
  ["incorrect_location", "candidate.location"],
  ["incorrect_role_direction", "candidate.role_direction"],
] as const satisfies ReadonlyArray<readonly [ProfileDataIssue, ProfileFieldLocator]>;
const jobIssues = [
  ["unclear_requirement", "job.requirements"],
  ["missing_requirement", "job.requirements"],
  ["incorrect_requirement_priority", "job.requirement_priority"],
  ["incorrect_seniority_requirement", "job.seniority"],
  ["incorrect_location_constraint", "job.location"],
  ["missing_expectation", "job.expectations"],
] as const satisfies ReadonlyArray<readonly [ProfileDataIssue, ProfileFieldLocator]>;

function label(value: string) {
  return value.replaceAll("_", " ").replace(/^\w/, (value) => value.toUpperCase());
}

function isCandidateScopedEvidence(reference: string, resultRank: number) {
  return ["candidate", "retrieval", "ranking", "feature", "diagnostic", "comparison"]
    .some((namespace) => reference.startsWith(`${namespace}:${resultRank}:`));
}

export function FeedbackPanel({
  run,
  explanationRun,
  onFeedbackCreated,
}: {
  run: MatchRunDetail;
  explanationRun?: ExplanationRunDetail | null;
  onFeedbackCreated?: (feedback: FeedbackRecord) => void;
}) {
  const [kind, setKind] = useState<FeedbackKind>("ranking");
  const [rankingTarget, setRankingTarget] = useState<RankingTargetType>("candidate_result");
  const [verdict, setVerdict] = useState("correct");
  const [reason, setReason] = useState<RankingReasonCode>("false_positive");
  const [subjectId, setSubjectId] = useState(String(run.results[0]?.match_result_id ?? ""));
  const [comparisonId, setComparisonId] = useState(String(run.results[1]?.match_result_id ?? ""));
  const [expectedReference, setExpectedReference] = useState("");
  const [explanationId, setExplanationId] = useState(String(explanationRun?.explanations[0]?.match_explanation_id ?? ""));
  const [explanationTarget, setExplanationTarget] = useState("summary");
  const [explanationVerdict, setExplanationVerdict] = useState("grounded");
  const [explanationEvidence, setExplanationEvidence] = useState("");
  const [profileTarget, setProfileTarget] = useState<"candidate_profile" | "job_profile">("candidate_profile");
  const [profileIssue, setProfileIssue] = useState<ProfileDataIssue>("missing_skill");
  const [comment, setComment] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<FeedbackRecord | null>(null);
  const profileOptions = profileTarget === "candidate_profile" ? candidateIssues : jobIssues;
  const comparisonOptions = run.results.filter((item) => String(item.match_result_id) !== subjectId);

  const selectedExplanation = useMemo(
    () => explanationRun?.explanations.find((item) => item.match_explanation_id === Number(explanationId)),
    [explanationId, explanationRun],
  );
  const explanationEvidenceOptions = useMemo(() => {
    if (!selectedExplanation) return [];
    const refs = [
      ...selectedExplanation.summary.evidence_refs,
      ...selectedExplanation.match_reasons.flatMap((item) => item.evidence_refs),
      ...selectedExplanation.risk_points.flatMap((item) => item.evidence_refs),
      ...selectedExplanation.missing_skills.flatMap((item) => item.evidence_refs),
      ...selectedExplanation.interview_questions.flatMap((item) => item.evidence_refs),
    ];
    return [...new Set(refs)].filter((reference) => (
      isCandidateScopedEvidence(reference, selectedExplanation.result_rank)
    ));
  }, [selectedExplanation]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      let payload: FeedbackCreateRequest;
      const base = { match_run_id: run.run_id, ...(comment.trim() ? { comment: comment.trim() } : {}) };
      if (kind === "ranking") {
        const selectors = rankingTarget === "overall_ranking"
          ? {}
          : rankingTarget === "expected_candidate"
            ? { expected_candidate_reference: `expected_candidate:${expectedReference.trim()}` }
            : rankingTarget === "pairwise"
              ? { subject_match_result_id: Number(subjectId), comparison_match_result_id: Number(comparisonId) }
              : { subject_match_result_id: rankingTarget === "top1" ? run.results.find((item) => item.result_rank === 1)?.match_result_id : Number(subjectId) };
        payload = {
          ...base,
          feedback_type: "ranking",
          target_type: rankingTarget as never,
          value: verdict as never,
          ...(verdict === "wrong" ? { reason_code: reason as never } : {}),
          ...selectors,
        };
      } else if (kind === "explanation") {
        if (!explanationRun || !selectedExplanation) throw new Error("No persisted explanation is available for this run");
        payload = {
          ...base,
          feedback_type: "explanation",
          explanation_run_id: explanationRun.explanation_run_id,
          match_explanation_id: selectedExplanation.match_explanation_id,
          target_type: explanationTarget as never,
          value: explanationVerdict as never,
          ...(explanationEvidence ? { evidence_reference: explanationEvidence } : {}),
        };
      } else {
        if (profileTarget === "candidate_profile") {
          const option = candidateIssues.find(([issue]) => issue === profileIssue) ?? candidateIssues[0];
          payload = { ...base, feedback_type: "profile_data", target_type: "candidate_profile", subject_match_result_id: Number(subjectId), value: option[0], field_locator: option[1] };
        } else {
          const option = jobIssues.find(([issue]) => issue === profileIssue) ?? jobIssues[0];
          payload = { ...base, feedback_type: "profile_data", target_type: "job_profile", value: option[0], field_locator: option[1] };
        }
      }
      const response = await createFeedback(payload);
      setCreated(response.data);
      onFeedbackCreated?.(response.data);
    } catch (caught) {
      setError(caught instanceof Phase10ApiError || caught instanceof Error ? caught.message : "Feedback could not be saved");
    } finally {
      setPending(false);
    }
  }

  function handleTabKeyDown(event: KeyboardEvent<HTMLButtonElement>, item: FeedbackKind) {
    const currentIndex = feedbackKinds.indexOf(item);
    const nextIndex = event.key === "ArrowRight"
      ? (currentIndex + 1) % feedbackKinds.length
      : event.key === "ArrowLeft"
        ? (currentIndex - 1 + feedbackKinds.length) % feedbackKinds.length
        : event.key === "Home"
          ? 0
          : event.key === "End"
            ? feedbackKinds.length - 1
            : null;
    if (nextIndex === null) return;
    event.preventDefault();
    const nextKind = feedbackKinds[nextIndex];
    setKind(nextKind);
    document.getElementById(`feedback-tab-${nextKind}`)?.focus();
  }

  return (
    <section className={styles.panel} aria-labelledby="feedback-title">
      <p className={styles.eyebrow}>Structured historical review</p>
      <h2 id="feedback-title">Review recommendation</h2>
      <p className={styles.muted}>Your choices refer to persisted run history. Candidate, rank, and ownership are resolved again by the server.</p>
      <div className={styles.tabs} role="tablist" aria-label="Feedback type">
        {feedbackKinds.map((item) => (
          <button id={`feedback-tab-${item}`} aria-controls="feedback-tabpanel" key={item} type="button" role="tab" aria-selected={kind === item} tabIndex={kind === item ? 0 : -1} className={`${styles.tab} ${kind === item ? styles.tabActive : ""}`} onClick={() => setKind(item)} onKeyDown={(event) => handleTabKeyDown(event, item)}>
            {item === "profile_data" ? "Profile / data" : label(item)}
          </button>
        ))}
      </div>
      <form id="feedback-tabpanel" role="tabpanel" aria-labelledby={`feedback-tab-${kind}`} onSubmit={submit}>
        <div className={styles.formGrid}>
          {kind === "ranking" ? <>
            <label className={styles.field}>Ranking target<select aria-label="Ranking target" value={rankingTarget} onChange={(event) => { const target = event.target.value as RankingTargetType; setRankingTarget(target); setReason(rankingReasons[target][0]); if (target === "pairwise" && comparisonId === subjectId) setComparisonId(String(run.results.find((item) => String(item.match_result_id) !== subjectId)?.match_result_id ?? "")); }}>
              <option value="candidate_result">Candidate result</option><option value="top1">Top 1</option><option value="pairwise">Pairwise</option><option value="overall_ranking">Overall ranking</option><option value="expected_candidate">Expected candidate absent</option>
            </select></label>
            {!["overall_ranking", "expected_candidate", "top1"].includes(rankingTarget) ? <label className={styles.field}>Historical result<select value={subjectId} onChange={(event) => { const selected = event.target.value; setSubjectId(selected); if (rankingTarget === "pairwise" && comparisonId === selected) setComparisonId(String(run.results.find((item) => String(item.match_result_id) !== selected)?.match_result_id ?? "")); }}>{run.results.map((item) => <option key={item.match_result_id} value={item.match_result_id}>Rank {item.result_rank} · {item.candidate_id}</option>)}</select></label> : null}
            {rankingTarget === "pairwise" ? <label className={styles.field}>Compared result<select value={comparisonId} onChange={(event) => setComparisonId(event.target.value)} required>{comparisonOptions.map((item) => <option key={item.match_result_id} value={item.match_result_id}>Rank {item.result_rank} · {item.candidate_id}</option>)}</select></label> : null}
            {rankingTarget === "expected_candidate" ? <label className={styles.field}>Reviewer reference<input value={expectedReference} onChange={(event) => setExpectedReference(event.target.value)} placeholder="bounded-reference" required /></label> : null}
            <label className={styles.field}>Verdict<select aria-label="Verdict" value={verdict} onChange={(event) => setVerdict(event.target.value)}><option value="correct">Correct</option><option value="wrong">Wrong</option><option value="uncertain">Uncertain</option><option value="insufficient_evidence">Insufficient evidence</option></select></label>
            {verdict === "wrong" ? <label className={styles.field}>Reason<select aria-label="Reason" value={reason} onChange={(event) => setReason(event.target.value as RankingReasonCode)}>{rankingReasons[rankingTarget].map((item) => <option value={item} key={item}>{label(item)}</option>)}</select></label> : null}
          </> : null}
          {kind === "explanation" ? explanationRun?.explanations.length ? <>
            <label className={styles.field}>Historical explanation<select value={explanationId} onChange={(event) => { setExplanationId(event.target.value); setExplanationEvidence(""); }}>{explanationRun.explanations.map((item) => <option key={item.match_explanation_id} value={item.match_explanation_id}>Rank {item.result_rank} · {item.candidate_id}</option>)}</select></label>
            <label className={styles.field}>Explanation section<select value={explanationTarget} onChange={(event) => setExplanationTarget(event.target.value)}><option value="summary">Summary</option><option value="match_reason">Match reason</option><option value="risk">Risk</option><option value="missing_requirement">Missing requirement</option><option value="interview_question">Interview question</option><option value="top1_comparison">Top 1 comparison</option></select></label>
            <label className={styles.field}>Verdict<select value={explanationVerdict} onChange={(event) => setExplanationVerdict(event.target.value)}><option value="grounded">Grounded</option><option value="unsupported">Unsupported</option><option value="misleading">Misleading</option><option value="incomplete">Incomplete</option></select></label>
            {explanationEvidenceOptions.length ? <label className={styles.fieldWide}>Historical evidence reference<select value={explanationEvidence} onChange={(event) => setExplanationEvidence(event.target.value)}><option value="">No evidence link</option>{explanationEvidenceOptions.map((reference) => <option value={reference} key={reference}>{reference}</option>)}</select></label> : null}
          </> : <div className={styles.info}>No completed persisted explanation is available for this run.</div> : null}
          {kind === "profile_data" ? <>
            <label className={styles.field}>Historical profile<select value={profileTarget} onChange={(event) => { const target = event.target.value as "candidate_profile" | "job_profile"; setProfileTarget(target); setProfileIssue((target === "candidate_profile" ? candidateIssues : jobIssues)[0][0]); }}><option value="candidate_profile">Candidate snapshot</option><option value="job_profile">Job snapshot</option></select></label>
            {profileTarget === "candidate_profile" ? <label className={styles.field}>Historical result<select value={subjectId} onChange={(event) => setSubjectId(event.target.value)}>{run.results.map((item) => <option key={item.match_result_id} value={item.match_result_id}>Rank {item.result_rank} · {item.candidate_id}</option>)}</select></label> : null}
            <label className={styles.field}>Observed issue<select value={profileIssue} onChange={(event) => setProfileIssue(event.target.value as ProfileDataIssue)}>{profileOptions.map(([issue]) => <option key={issue} value={issue}>{label(issue)}</option>)}</select></label>
          </> : null}
          <label className={styles.fieldWide}>Optional reviewer note<textarea maxLength={500} value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Bounded context only; do not paste resumes or job descriptions." /></label>
        </div>
        <div className={styles.formActions}><button className={styles.primaryButton} type="submit" disabled={pending || (kind === "explanation" && !selectedExplanation) || (kind === "ranking" && rankingTarget === "pairwise" && (!comparisonId || comparisonId === subjectId))}>{pending ? "Saving…" : "Submit feedback"}</button></div>
      </form>
      {error ? <div className={styles.error} role="alert">{error}</div> : null}
      {created ? <div className={styles.success} role="status"><strong>Feedback recorded</strong><br />The persisted observation is immutable. Creating a BadCase remains a separate action.</div> : null}
    </section>
  );
}
