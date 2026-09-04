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

const reviewLabels: Record<string, string> = {
  ranking: "排序结果",
  explanation: "推荐解释",
  profile_data: "候选人资料",
  candidate_result: "候选人结果",
  top1: "Top 1 候选人",
  pairwise: "候选人两两比较",
  overall_ranking: "整体排序",
  expected_candidate: "预期候选人未召回",
  correct: "正确",
  wrong: "存在问题",
  uncertain: "无法确定",
  insufficient_evidence: "证据不足",
  wrong_top1: "Top 1 不正确",
  false_positive: "误推荐",
  false_negative: "漏召回",
  ranking_inversion: "排序颠倒",
  constraint_conflict: "约束冲突",
  evidence_coverage_disagreement: "证据覆盖有分歧",
  summary: "解释摘要",
  match_reason: "推荐原因",
  risk: "风险项",
  missing_requirement: "缺失要求",
  interview_question: "面试问题",
  top1_comparison: "Top 1 对比",
  grounded: "证据充分",
  unsupported: "缺少证据支持",
  misleading: "可能误导",
  incomplete: "解释不完整",
  candidate_profile: "候选人历史快照",
  job_profile: "岗位历史快照",
  missing_skill: "缺少技能",
  incorrect_skill: "技能信息不正确",
  missing_project_evidence: "缺少项目证据",
  incorrect_project_evidence_status: "项目证据状态不正确",
  incorrect_seniority: "资历信息不正确",
  incorrect_location: "地点信息不正确",
  incorrect_role_direction: "岗位方向不正确",
  unclear_requirement: "岗位要求不清晰",
  incorrect_requirement_priority: "要求优先级不正确",
  incorrect_seniority_requirement: "资历要求不正确",
  incorrect_location_constraint: "地点约束不正确",
  missing_expectation: "缺少评估预期",
};

function label(value: string) {
  return reviewLabels[value] ?? value.replaceAll("_", " ");
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
        if (!explanationRun || !selectedExplanation) throw new Error("当前 MatchRun 没有可复核的持久化解释");
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
      setError(caught instanceof Phase10ApiError || caught instanceof Error ? caught.message : "反馈暂时无法保存");
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
      <p className={styles.eyebrow}>结构化历史复核 · Feedback Review</p>
      <h2 id="feedback-title">复核推荐结果</h2>
      <p className={styles.muted}>所有选择都绑定已持久化的 MatchRun；Candidate、排名和历史归属会由服务端再次核验。</p>
      <div className={styles.tabs} role="tablist" aria-label="反馈类型">
        {feedbackKinds.map((item) => (
          <button id={`feedback-tab-${item}`} aria-controls="feedback-tabpanel" key={item} type="button" role="tab" aria-selected={kind === item} tabIndex={kind === item ? 0 : -1} className={`${styles.tab} ${kind === item ? styles.tabActive : ""}`} onClick={() => setKind(item)} onKeyDown={(event) => handleTabKeyDown(event, item)}>
            {label(item)}
          </button>
        ))}
      </div>
      <form id="feedback-tabpanel" role="tabpanel" aria-labelledby={`feedback-tab-${kind}`} onSubmit={submit}>
        <div className={styles.formGrid}>
          {kind === "ranking" ? <>
            <label className={styles.field}>复核对象<select aria-label="复核对象" value={rankingTarget} onChange={(event) => { const target = event.target.value as RankingTargetType; setRankingTarget(target); setReason(rankingReasons[target][0]); if (target === "pairwise" && comparisonId === subjectId) setComparisonId(String(run.results.find((item) => String(item.match_result_id) !== subjectId)?.match_result_id ?? "")); }}>
              {Object.keys(rankingReasons).map((item) => <option key={item} value={item}>{label(item)}</option>)}
            </select></label>
            {!["overall_ranking", "expected_candidate", "top1"].includes(rankingTarget) ? <label className={styles.field}>历史排序结果<select value={subjectId} onChange={(event) => { const selected = event.target.value; setSubjectId(selected); if (rankingTarget === "pairwise" && comparisonId === selected) setComparisonId(String(run.results.find((item) => String(item.match_result_id) !== selected)?.match_result_id ?? "")); }}>{run.results.map((item) => <option key={item.match_result_id} value={item.match_result_id}>第 {item.result_rank} 名 · {item.candidate_id}</option>)}</select></label> : null}
            {rankingTarget === "pairwise" ? <label className={styles.field}>对比结果<select value={comparisonId} onChange={(event) => setComparisonId(event.target.value)} required>{comparisonOptions.map((item) => <option key={item.match_result_id} value={item.match_result_id}>第 {item.result_rank} 名 · {item.candidate_id}</option>)}</select></label> : null}
            {rankingTarget === "expected_candidate" ? <label className={styles.field}>复核参考<input value={expectedReference} onChange={(event) => setExpectedReference(event.target.value)} placeholder="受限参考标识" required /></label> : null}
            <label className={styles.field}>评价结果<select aria-label="评价结果" value={verdict} onChange={(event) => setVerdict(event.target.value)}>{["correct", "wrong", "uncertain", "insufficient_evidence"].map((item) => <option key={item} value={item}>{label(item)}</option>)}</select></label>
            {verdict === "wrong" ? <label className={styles.field}>问题原因<select aria-label="问题原因" value={reason} onChange={(event) => setReason(event.target.value as RankingReasonCode)}>{rankingReasons[rankingTarget].map((item) => <option value={item} key={item}>{label(item)}</option>)}</select></label> : null}
          </> : null}
          {kind === "explanation" ? explanationRun?.explanations.length ? <>
            <label className={styles.field}>历史推荐解释<select value={explanationId} onChange={(event) => { setExplanationId(event.target.value); setExplanationEvidence(""); }}>{explanationRun.explanations.map((item) => <option key={item.match_explanation_id} value={item.match_explanation_id}>第 {item.result_rank} 名 · {item.candidate_id}</option>)}</select></label>
            <label className={styles.field}>解释部分<select value={explanationTarget} onChange={(event) => setExplanationTarget(event.target.value)}>{["summary", "match_reason", "risk", "missing_requirement", "interview_question", "top1_comparison"].map((item) => <option key={item} value={item}>{label(item)}</option>)}</select></label>
            <label className={styles.field}>评价结果<select value={explanationVerdict} onChange={(event) => setExplanationVerdict(event.target.value)}>{["grounded", "unsupported", "misleading", "incomplete"].map((item) => <option key={item} value={item}>{label(item)}</option>)}</select></label>
            {explanationEvidenceOptions.length ? <label className={styles.fieldWide}>历史 Evidence 引用<select value={explanationEvidence} onChange={(event) => setExplanationEvidence(event.target.value)}><option value="">不关联 Evidence</option>{explanationEvidenceOptions.map((reference) => <option value={reference} key={reference}>{reference}</option>)}</select></label> : null}
          </> : <div className={styles.info}>该 MatchRun 暂无已完成的持久化解释。</div> : null}
          {kind === "profile_data" ? <>
            <label className={styles.field}>历史资料<select value={profileTarget} onChange={(event) => { const target = event.target.value as "candidate_profile" | "job_profile"; setProfileTarget(target); setProfileIssue((target === "candidate_profile" ? candidateIssues : jobIssues)[0][0]); }}><option value="candidate_profile">候选人快照</option><option value="job_profile">岗位快照</option></select></label>
            {profileTarget === "candidate_profile" ? <label className={styles.field}>历史排序结果<select value={subjectId} onChange={(event) => setSubjectId(event.target.value)}>{run.results.map((item) => <option key={item.match_result_id} value={item.match_result_id}>第 {item.result_rank} 名 · {item.candidate_id}</option>)}</select></label> : null}
            <label className={styles.field}>发现的问题<select value={profileIssue} onChange={(event) => setProfileIssue(event.target.value as ProfileDataIssue)}>{profileOptions.map(([issue]) => <option key={issue} value={issue}>{label(issue)}</option>)}</select></label>
          </> : null}
          <label className={styles.fieldWide}>备注<textarea aria-label="备注" maxLength={500} value={comment} onChange={(event) => setComment(event.target.value)} placeholder="仅填写必要复核信息；请勿粘贴完整简历或岗位描述。" /></label>
        </div>
        <div className={styles.formActions}><button className={styles.primaryButton} type="submit" disabled={pending || (kind === "explanation" && !selectedExplanation) || (kind === "ranking" && rankingTarget === "pairwise" && (!comparisonId || comparisonId === subjectId))}>{pending ? "正在保存…" : "提交反馈"}</button></div>
      </form>
      {error ? <div className={styles.error} role="alert">{error}</div> : null}
      {created ? <div className={styles.success} role="status"><strong>反馈已记录</strong><br />该观察记录不可变；创建 Bad Case 仍是独立的显式操作。</div> : null}
    </section>
  );
}
