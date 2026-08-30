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
  wrong_top1: "Wrong top 1",
  ranking_inversion: "Ranking inversion",
  false_positive: "False positive",
  expected_candidate_not_recalled: "Expected candidate not recalled",
  constraint_conflict: "Constraint conflict",
  requirement_coverage_disagreement: "Requirement coverage disagreement",
  uncertain_order: "Uncertain order",
  unsupported_explanation: "Unsupported explanation",
  misleading_explanation: "Misleading explanation",
  incomplete_explanation: "Incomplete explanation",
  candidate_snapshot_issue: "Candidate snapshot issue",
  job_snapshot_issue: "Job snapshot issue",
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
          if (active) setLoadError("No completed historical MatchRun is available for review.");
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
            : "Historical review context is unavailable.");
        }
      }
    }
    void loadHistoricalContext();
    return () => { active = false; };
  }, []);

  const runLabel = useMemo(() => run ? `${run.ranking_variant.replaceAll("_", " ")} · ${run.result_count} persisted results` : "", [run]);

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
      setCaseError(caught instanceof Phase10ApiError || caught instanceof Error ? caught.message : "Bad case could not be created");
    } finally {
      setCasePending(false);
    }
  }

  if (loadError) {
    return <section className={styles.error} role="alert"><strong>Historical review unavailable</strong><br />{loadError}</section>;
  }
  if (!run) {
    return <section className={styles.loading} aria-label="Loading historical review context"><div className={styles.skeleton} /></section>;
  }

  return (
    <div className={styles.feedbackWorkspace}>
      <div className={styles.contextStrip} aria-label="Persisted review context">
        <span>Persisted historical context</span>
        <strong>{runLabel}</strong>
        <small>Ownership is resolved again by the server.</small>
      </div>
      <FeedbackPanel run={run} explanationRun={explanationRun} onFeedbackCreated={handleFeedbackCreated} />
      {feedback ? (
        <section className={styles.followupPanel} aria-labelledby="feedback-followup-title">
          <div>
            <p className={styles.eyebrow}>Observation recorded</p>
            <h3 id="feedback-followup-title">Investigate this feedback?</h3>
            <p className={styles.muted}>A BadCase is an explicit investigation aggregate. It is never created automatically.</p>
          </div>
          {!createdCase && !caseFormOpen && symptomCode ? <button className={styles.secondaryButton} type="button" onClick={() => setCaseFormOpen(true)}>Create bad case</button> : null}
          {!createdCase && !symptomCode ? <div className={styles.info}>This observation does not map to a BadCase symptom. It remains available as immutable feedback.</div> : null}
          {caseFormOpen ? (
            <form className={styles.inlineForm} onSubmit={submitCase}>
              <div className={styles.field}><span>Observed symptom</span><strong>{symptomLabels[symptomCode]}</strong></div>
              <label className={styles.field}>Severity<select value={severity} onChange={(event) => setSeverity(event.target.value as BadCaseSeverity)}><option value="LOW">Low</option><option value="MEDIUM">Medium</option><option value="HIGH">High</option><option value="CRITICAL">Critical</option></select></label>
              <button className={styles.primaryButton} disabled={casePending} type="submit">{casePending ? "Creating…" : "Confirm case creation"}</button>
            </form>
          ) : null}
          {caseError ? <div className={styles.error} role="alert">{caseError}</div> : null}
          {createdCase ? <Link className={styles.primaryButton} href={`/bad-cases/${encodeURIComponent(createdCase.bad_case_id)}`}>Open bad case</Link> : null}
        </section>
      ) : null}
    </div>
  );
}
