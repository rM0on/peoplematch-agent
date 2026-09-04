"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import {
  createBadCase,
  getExplanationRun,
  getMatchRun,
  listCompletedMatchRuns,
  listExplanationRuns,
  Phase10ApiError,
} from "@/lib/phase10-api";
import type {
  BadCaseDetail,
  BadCaseSeverity,
  BadCaseSymptomCode,
  ExplanationRunDetail,
  FeedbackRecord,
  MatchRunDetail,
} from "@/types/phase10";

import { FeedbackPanel } from "./feedback-panel";
import styles from "./phase10.module.css";


const symptomLabels: Record<string, string> = {
  wrong_top1: "Top 1 推荐不正确",
  ranking_inversion: "候选人排序颠倒",
  false_positive: "候选人误推荐",
  expected_candidate_not_recalled: "预期候选人未召回",
  constraint_conflict: "岗位约束冲突",
  requirement_coverage_disagreement: "岗位要求覆盖有分歧",
  uncertain_order: "排序结果无法确定",
  unsupported_explanation: "推荐解释缺少证据",
  misleading_explanation: "推荐解释可能误导",
  incomplete_explanation: "推荐解释不完整",
  candidate_snapshot_issue: "候选人快照问题",
  job_snapshot_issue: "岗位快照问题",
};

function defaultSymptom(feedback: FeedbackRecord): BadCaseSymptomCode | null {
  if (feedback.feedback_type === "ranking") {
    if (["uncertain", "insufficient_evidence"].includes(feedback.value)) return "uncertain_order";
    if (feedback.value !== "wrong" || !feedback.reason_code) return null;
    const rankingSymptoms: Partial<Record<NonNullable<typeof feedback.reason_code>, BadCaseSymptomCode>> = {
      wrong_top1: "wrong_top1",
      ranking_inversion: "ranking_inversion",
      false_positive: "false_positive",
      false_negative: "expected_candidate_not_recalled",
      constraint_conflict: "constraint_conflict",
      evidence_coverage_disagreement: "requirement_coverage_disagreement",
    };
    return rankingSymptoms[feedback.reason_code] ?? null;
  }
  if (feedback.feedback_type === "explanation") {
    return feedback.value === "unsupported"
      ? "unsupported_explanation"
      : feedback.value === "misleading"
        ? "misleading_explanation"
        : feedback.value === "incomplete"
          ? "incomplete_explanation"
          : null;
  }
  return feedback.target_type === "job_profile" ? "job_snapshot_issue" : "candidate_snapshot_issue";
}

export function HistoricalFeedbackEntry() {
  const [run, setRun] = useState<MatchRunDetail | null>(null);
  const [explanationRun, setExplanationRun] = useState<ExplanationRunDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<FeedbackRecord | null>(null);
  const [caseFormOpen, setCaseFormOpen] = useState(false);
  const [symptomCode, setSymptomCode] = useState<BadCaseSymptomCode | "">("");
  const [severity, setSeverity] = useState<BadCaseSeverity>("HIGH");
  const [createdCase, setCreatedCase] = useState<BadCaseDetail | null>(null);
  const [casePending, setCasePending] = useState(false);
  const [caseError, setCaseError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function loadHistoricalContext() {
      try {
        const runs = await listCompletedMatchRuns(20);
        const latest = runs.data.items[0];
        if (!latest) {
          if (active) setLoadError("暂无可供复核的已完成历史 MatchRun。");
          return;
        }
        const runResponse = await getMatchRun(latest.run_id);
        let explanation: ExplanationRunDetail | null = null;
        const explanationRuns = await listExplanationRuns(latest.run_id, 20);
        const completedExplanation = explanationRuns.data.items.find((item) => item.status === "COMPLETED");
        if (completedExplanation) {
          explanation = (await getExplanationRun(completedExplanation.explanation_run_id)).data;
        }
        if (active) {
          setRun(runResponse.data);
          setExplanationRun(explanation);
        }
      } catch (caught) {
        if (active) {
          setLoadError(caught instanceof Phase10ApiError || caught instanceof Error
            ? caught.message
            : "历史复核上下文暂不可用。");
        }
      }
    }
    void loadHistoricalContext();
    return () => { active = false; };
  }, []);

  const runLabel = useMemo(() => run ? `${run.ranking_variant.replaceAll("_", " ")} · ${run.result_count} 条持久化排序结果` : "", [run]);

  function handleFeedbackCreated(created: FeedbackRecord) {
    setFeedback(created);
    setSymptomCode(defaultSymptom(created) ?? "");
    setCaseFormOpen(false);
    setCreatedCase(null);
  }

  async function submitCase(event: FormEvent) {
    event.preventDefault();
    if (!feedback || !symptomCode) return;
    setCasePending(true);
    setCaseError(null);
    try {
      const response = await createBadCase({
        source_type: "feedback",
        feedback_id: feedback.feedback_id,
        symptom_code: symptomCode,
        severity,
      });
      setCreatedCase(response.data);
      setCaseFormOpen(false);
    } catch (caught) {
      setCaseError(caught instanceof Phase10ApiError || caught instanceof Error ? caught.message : "Bad Case 暂时无法创建");
    } finally {
      setCasePending(false);
    }
  }

  if (loadError) {
    return <section className={styles.error} role="alert"><strong>历史推荐复核暂不可用</strong><br />{loadError}</section>;
  }
  if (!run) {
    return <section className={styles.loading} aria-label="正在加载历史复核上下文"><div className={styles.skeleton} /></section>;
  }

  return (
    <div className={styles.feedbackWorkspace}>
      <div className={styles.contextStrip} aria-label="已持久化复核上下文">
        <span>已持久化的历史推荐</span>
        <strong>{runLabel}</strong>
        <small>历史归属由服务端再次核验。</small>
      </div>
      <FeedbackPanel run={run} explanationRun={explanationRun} onFeedbackCreated={handleFeedbackCreated} />
      {feedback ? (
        <section className={styles.followupPanel} aria-labelledby="feedback-followup-title">
          <div>
            <p className={styles.eyebrow}>观察已记录</p>
            <h3 id="feedback-followup-title">是否进一步调查此反馈？</h3>
            <p className={styles.muted}>Bad Case 是显式创建的调查记录，不会根据 Feedback 自动生成。</p>
          </div>
          {!createdCase && !caseFormOpen && symptomCode ? <button className={styles.secondaryButton} type="button" onClick={() => setCaseFormOpen(true)}>创建 Bad Case</button> : null}
          {!createdCase && !symptomCode ? <div className={styles.info}>该观察没有对应的 Bad Case 症状，仍会作为不可变 Feedback 保留。</div> : null}
          {caseFormOpen ? (
            <form className={styles.inlineForm} onSubmit={submitCase}>
              <div className={styles.field}><span>观察到的症状</span><strong>{symptomLabels[symptomCode]}</strong></div>
              <label className={styles.field}>严重程度<select value={severity} onChange={(event) => setSeverity(event.target.value as BadCaseSeverity)}><option value="LOW">低</option><option value="MEDIUM">中</option><option value="HIGH">高</option><option value="CRITICAL">严重</option></select></label>
              <button className={styles.primaryButton} disabled={casePending} type="submit">{casePending ? "正在创建…" : "确认创建 Bad Case"}</button>
            </form>
          ) : null}
          {caseError ? <div className={styles.error} role="alert">{caseError}</div> : null}
          {createdCase ? <Link className={styles.primaryButton} href={`/bad-cases/${encodeURIComponent(createdCase.bad_case_id)}`}>打开 Bad Case</Link> : null}
        </section>
      ) : null}
    </div>
  );
}
