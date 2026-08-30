"use client";

import { ClockIcon } from "@phosphor-icons/react/dist/csr/Clock";
import { SlidersHorizontalIcon } from "@phosphor-icons/react/dist/csr/SlidersHorizontal";
import { useCallback, useMemo, useState } from "react";

import { HistoricalFeedbackEntry } from "@/features/phase10/historical-feedback-entry";
import { useModalDialog } from "@/features/phase10/use-modal-dialog";

import { AppSidebar } from "./app-sidebar";
import { CandidateShortlist } from "./candidate-shortlist";
import { candidates, jobContext, pipelineStages } from "./design-mock-data";
import { PipelineStrip } from "./pipeline-strip";
import { RankingDetail } from "./ranking-detail";
import type { PipelineStage } from "./types";
import styles from "./matching-results.module.css";
import reviewStyles from "../phase10/phase10.module.css";


export function MatchingResultsScreen() {
  const [selectedCandidateId, setSelectedCandidateId] = useState(candidates[0].id);
  const [activeStageId, setActiveStageId] = useState<PipelineStage["id"]>("rerank");
  const [comparisonOpen, setComparisonOpen] = useState(false);
  const [reviewOpen, setReviewOpen] = useState(false);
  const closeReview = useCallback(() => setReviewOpen(false), []);
  const { dialogRef, onDialogKeyDown } = useModalDialog(reviewOpen, closeReview);

  const selectedCandidate = useMemo(
    () => candidates.find((candidate) => candidate.id === selectedCandidateId) ?? candidates[0],
    [selectedCandidateId],
  );
  const comparisonCandidate =
    candidates.find((candidate) => candidate.id === selectedCandidate.comparison.candidateId) ?? candidates[1];

  function selectCandidate(candidateId: string) {
    setSelectedCandidateId(candidateId);
    setComparisonOpen(false);
  }

  return (
    <div className={styles.appShell}>
      <a className={styles.skipLink} href="#matching-results">
        Skip to matching results
      </a>
      <AppSidebar />

      <main className={styles.mainSurface} id="matching-results">
        <header className={styles.jobBar}>
          <div>
            <span className={styles.jobBarLabel}>Matching against</span>
            <strong>{jobContext.title}</strong>
            <span>{jobContext.company}</span>
          </div>
          <div className={styles.jobMeta}>
            <span>{jobContext.location}</span>
            <span>{jobContext.seniority}</span>
            <span className={styles.jobContextLabel}>
              Job context
            </span>
          </div>
        </header>

        <div className={styles.contentFrame}>
          <header className={styles.pageHeader}>
            <div>
              <p className={styles.eyebrow}>Evidence-aware decision workspace</p>
              <h1>Matching Results</h1>
              <p>Compare rank, inspect project evidence, and trace the decision without losing job context.</p>
            </div>
            <div className={styles.runMeta} aria-label="Run metadata">
              <span>
                <SlidersHorizontalIcon size={15} />
                {jobContext.strategy}
              </span>
              <span className={styles.runId}>{jobContext.runId}</span>
              <span>
                <ClockIcon size={15} />
                Illustrative data · Design Mock
              </span>
            </div>
          </header>

          <PipelineStrip
            stages={pipelineStages}
            activeStageId={activeStageId}
            onStageSelect={setActiveStageId}
          />

          <div className={styles.matchWorkspace}>
            <CandidateShortlist
              candidates={candidates}
              selectedCandidateId={selectedCandidate.id}
              onSelect={selectCandidate}
            />
            <RankingDetail
              candidate={selectedCandidate}
              comparisonCandidate={comparisonCandidate}
              comparisonOpen={comparisonOpen}
              onComparisonToggle={() => setComparisonOpen((open) => !open)}
              onReview={() => setReviewOpen(true)}
            />
          </div>
        </div>
      </main>
      {reviewOpen ? (
        <div className={reviewStyles.dialogBackdrop} role="presentation">
          <section ref={dialogRef} onKeyDown={onDialogKeyDown} className={`${reviewStyles.dialog} ${reviewStyles.feedbackDialog}`} role="dialog" aria-modal="true" aria-labelledby="feedback-dialog-title">
            <div className={reviewStyles.dialogHeader}>
              <div><p className={reviewStyles.eyebrow}>Persisted review workflow</p><h2 id="feedback-dialog-title">Review persisted history</h2></div>
              <button type="button" onClick={closeReview}>Close</button>
            </div>
            <div className={reviewStyles.info}>The illustrative matching canvas is not the feedback target. This workflow loads the latest persisted synthetic MatchRun and resolves its historical owners on the server.</div>
            <HistoricalFeedbackEntry />
          </section>
        </div>
      ) : null}
    </div>
  );
}
