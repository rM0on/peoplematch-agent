"use client";

import { FormEvent, useCallback, useMemo, useRef, useState, useEffect } from "react";
import Link from "next/link";

import { getBadCase, listBadCases, Phase10ApiError, reviewBadCase } from "@/lib/phase10-api";
import type {
  BadCaseDetail,
  BadCaseReviewCommand,
  BadCaseStatus,
  BadCaseSummary,
  ResolutionActionType,
  RootCauseCode,
  RootCauseType,
  TransitionReason,
} from "@/types/phase10";

import styles from "./phase10.module.css";
import { optionLabel, resolutionActionOptions, rootCauseOptions } from "./review-options";
import { useModalDialog } from "./use-modal-dialog";


function words(value: string) { return value.replaceAll("_", " "); }
function short(value: string) { return value.length > 24 ? `${value.slice(0, 10)}…${value.slice(-8)}` : value; }

const lifecycle: Partial<Record<BadCaseStatus, { status: BadCaseStatus; reason: TransitionReason; label: string }>> = {
  CREATED: { status: "REVIEWED", reason: "review_completed", label: "Mark reviewed" },
  REVIEWED: { status: "ROOT_CAUSE_IDENTIFIED", reason: "root_cause_supported", label: "Identify root cause" },
  ROOT_CAUSE_IDENTIFIED: { status: "ACTION_PLANNED", reason: "action_created", label: "Confirm action planned" },
  ACTION_PLANNED: { status: "RESOLVED", reason: "actions_completed", label: "Resolve case" },
};

export function BadCaseDetailScreen({ badCaseId }: { badCaseId: string }) {
  const [detail, setDetail] = useState<BadCaseDetail | null>(null);
  const [loadError, setLoadError] = useState<Phase10ApiError | Error | null>(null);
  const [mutationError, setMutationError] = useState<Phase10ApiError | Error | null>(null);
  const [pending, setPending] = useState(false);
  const [dialog, setDialog] = useState<"analysis" | "resolution" | "verify" | "duplicate" | null>(null);
  const [description, setDescription] = useState("");
  const [assessment, setAssessment] = useState<"suspected" | "supported" | "confirmed" | "rejected">("suspected");
  const [rootType, setRootType] = useState<RootCauseType>("explanation");
  const [rootCode, setRootCode] = useState<RootCauseCode>("explanation_unsupported_claim");
  const [evidenceId, setEvidenceId] = useState("");
  const [actionType, setActionType] = useState<ResolutionActionType>("grounding_integrity_action");
  const [actionStatus, setActionStatus] = useState<"planned" | "in_progress" | "completed" | "cancelled">("planned");
  const [safeChangeReference, setSafeChangeReference] = useState("");
  const [verificationReference, setVerificationReference] = useState("");
  const [canonicalCase, setCanonicalCase] = useState("");
  const [canonicalOptions, setCanonicalOptions] = useState<BadCaseSummary[]>([]);
  const [canonicalLoading, setCanonicalLoading] = useState(false);
  const [canonicalError, setCanonicalError] = useState<string | null>(null);
  const mutationInFlight = useRef(false);
  const loadRequestSequence = useRef(0);
  const closeDialog = useCallback(() => setDialog(null), []);
  const { dialogRef, onDialogKeyDown } = useModalDialog(Boolean(dialog), closeDialog);

  const load = useCallback(async () => {
    const requestSequence = ++loadRequestSequence.current;
    try {
      const response = await getBadCase(badCaseId, 100);
      if (requestSequence !== loadRequestSequence.current) return;
      setLoadError(null); setDetail(response.data); setMutationError(null);
    }
    catch (caught) {
      if (requestSequence !== loadRequestSequence.current) return;
      setLoadError(caught instanceof Phase10ApiError || caught instanceof Error ? caught : new Error("Case unavailable"));
    }
  }, [badCaseId]);

  useEffect(() => {
    let active = true;
    const requestSequence = ++loadRequestSequence.current;
    getBadCase(badCaseId, 100).then((response) => {
      if (active && requestSequence === loadRequestSequence.current) {
        setDetail(response.data);
        setLoadError(null);
        setMutationError(null);
      }
    }).catch((caught) => {
      if (active && requestSequence === loadRequestSequence.current) {
        setLoadError(caught instanceof Phase10ApiError || caught instanceof Error ? caught : new Error("Case unavailable"));
      }
    });
    return () => { active = false; };
  }, [badCaseId]);
  const analysesComplete = Boolean(detail && !detail.truncated_collections.includes("analyses"));
  const actionsComplete = Boolean(detail && !detail.truncated_collections.includes("resolution_actions"));
  const currentAnalysis = useMemo(
    () => analysesComplete ? detail?.analyses.toSorted((a, b) => b.revision_number - a.revision_number)[0] : undefined,
    [analysesComplete, detail],
  );
  const currentActions = useMemo(() => {
    if (!actionsComplete || !detail) return [];
    return detail.resolution_actions.filter((candidate) => (
      !detail.resolution_actions.some((item) => item.supersedes_action_id === candidate.action_id)
    ));
  }, [actionsComplete, detail]);
  const currentAction = useMemo(
    () => currentActions.toSorted((a, b) => {
      const aActive = ["planned", "in_progress"].includes(a.status);
      const bActive = ["planned", "in_progress"].includes(b.status);
      return Number(bActive) - Number(aActive) || b.action_id - a.action_id;
    })[0],
    [currentActions],
  );
  const rootCodes = useMemo(() => rootCauseOptions.filter(([type]) => type === rootType), [rootType]);

  async function mutate(payload: BadCaseReviewCommand) {
    if (mutationInFlight.current) return;
    mutationInFlight.current = true;
    setPending(true); setMutationError(null);
    try { const response = await reviewBadCase(badCaseId, payload); setDetail(response.data); setDialog(null); setDescription(""); }
    catch (caught) {
      const normalized = caught instanceof Phase10ApiError || caught instanceof Error ? caught : new Error("Review could not be saved");
      setMutationError(normalized);
      if (normalized instanceof Phase10ApiError && normalized.status === 409) setDialog(null);
    }
    finally { mutationInFlight.current = false; setPending(false); }
  }

  async function openDuplicateDialog() {
    if (!detail) return;
    setDialog("duplicate");
    setCanonicalLoading(true);
    setCanonicalError(null);
    setCanonicalCase("");
    try {
      const response = await listBadCases({ limit: 100, offset: 0 });
      const compatible = response.data.items.filter((item) => (
        item.bad_case_id !== detail.bad_case_id
        && item.primary_match_run_id === detail.primary_match_run_id
        && item.symptom_code === detail.symptom_code
      ));
      setCanonicalOptions(compatible);
      setCanonicalCase(compatible[0]?.bad_case_id ?? "");
    } catch (caught) {
      setCanonicalOptions([]);
      setCanonicalError(caught instanceof Phase10ApiError || caught instanceof Error
        ? caught.message
        : "Compatible cases are unavailable");
    } finally {
      setCanonicalLoading(false);
    }
  }

  async function saveAnalysis(event: FormEvent) {
    event.preventDefault(); if (!detail) return;
    await mutate({ command: "analysis", expected_status: detail.status, expected_revision: detail.revision, analysis: { assessment, root_cause_type: rootType, root_cause_code: rootCode, description: description.trim(), ...(["supported", "confirmed"].includes(assessment) && evidenceId ? { supporting_evidence_link_id: Number(evidenceId) } : {}) } });
  }

  async function saveResolution(event: FormEvent) {
    event.preventDefault(); if (!detail) return;
    await mutate({ command: "resolution", expected_status: detail.status, expected_revision: detail.revision, resolution: { action_type: actionType, description: description.trim(), status: actionStatus, ...(currentAction ? { supersedes_action_id: currentAction.action_id } : {}), ...(safeChangeReference.trim() ? { safe_change_reference: safeChangeReference.trim() } : {}) } });
  }

  if (loadError instanceof Phase10ApiError && loadError.status === 404) return <section className={styles.empty}><div><h1>Bad case not found</h1><p>This historical review record is unavailable.</p><Link href="/bad-cases">Return to Bad Cases</Link></div></section>;
  if (loadError) return <section className={styles.error} role="alert"><strong>Case unavailable</strong><br />{loadError.message}<div className={styles.formActions}><button className={styles.secondaryButton} onClick={() => void load()} type="button">Retry</button></div></section>;
  if (!detail) return <section className={styles.loading} aria-label="Loading bad case detail"><div className={styles.skeleton} /></section>;

  const stale = mutationError instanceof Phase10ApiError && mutationError.status === 409;
  const next = lifecycle[detail.status];
  const hasCurrentRootCause = currentAnalysis?.assessment === "supported" || currentAnalysis?.assessment === "confirmed";
  const lifecycleBlock = detail.status === "REVIEWED" && !analysesComplete
    ? "Identify root cause is unavailable while analysis history is a bounded partial projection."
    : detail.status === "REVIEWED" && !hasCurrentRootCause
    ? "Identify root cause requires the latest analysis to be supported or confirmed."
    : detail.status === "ROOT_CAUSE_IDENTIFIED" && !actionsComplete
      ? "Action planning is unavailable while resolution history is a bounded partial projection."
      : detail.status === "ROOT_CAUSE_IDENTIFIED" && !currentActions.some((item) => ["planned", "in_progress"].includes(item.status))
      ? "Action planning requires a compatible active resolution action."
      : detail.status === "ACTION_PLANNED" && !actionsComplete
        ? "Case resolution is unavailable while resolution history is a bounded partial projection."
        : detail.status === "ACTION_PLANNED" && currentActions.some((item) => !["completed", "cancelled", "superseded"].includes(item.status))
        ? "Resolve case requires every current action to have a terminal disposition."
        : null;
  return <>
    <div className={styles.detailGrid} aria-label="Bad case review workspace" aria-busy={pending}>
      <div className={styles.detailMain}>
        <section className={styles.caseSurface}>
          <div className={styles.detailHeader}><div><p className={styles.eyebrow}>Case overview</p><h1 data-modal-focus-fallback tabIndex={-1}>{words(detail.symptom_code)}</h1><p className={styles.muted}>Historical observation under review — not a generic ticket or model-quality claim.</p></div><div><span className={styles.badge}>{detail.status}</span> <span className={styles.severity}>{detail.severity}</span></div></div>
          <div className={styles.summaryGrid}><div><span>Revision</span><strong>{detail.revision}</strong></div><div><span>Symptom family</span><strong>{detail.symptom_family}</strong></div><div><span>MatchRun</span><strong className={styles.technical}>{short(detail.primary_match_run_id)}</strong></div><div><span>Historical rank</span><strong>{detail.result_rank ? `#${detail.result_rank}` : "Run scoped"}</strong></div></div>
          {detail.truncated_collections.length ? <div className={styles.warning}><strong>Partial history</strong><br />{detail.truncated_collections.join(", ")} are bounded by this projection. Refreshing does not make truncated history complete.</div> : null}
        </section>

        <section className={styles.caseSurface}><div className={styles.sectionHeader}><div><p className={styles.eyebrow}>Why this case exists</p><h2>Historical sources</h2></div><span className={styles.badge}>{detail.sources.length} observations</span></div><div className={styles.historyList}>{detail.sources.map((source, index) => <article className={styles.historyItem} key={`${source.source_type}-${source.feedback_id ?? source.system_signal_id}-${index}`}><strong>{source.source_type === "feedback" ? "Human feedback" : "Deterministic system signal"}</strong><p className={styles.technical}>{short(source.feedback_id ?? source.system_signal_id ?? "unavailable")}</p></article>)}</div></section>

        <section className={styles.caseSurface}><div className={styles.sectionHeader}><div><p className={styles.eyebrow}>Frozen historical references</p><h2>Evidence</h2></div><span className={styles.badge}>{detail.evidence_links.length} links</span></div>{detail.evidence_links.length ? <div className={styles.historyList}>{detail.evidence_links.map((item) => <article className={styles.historyItem} key={item.evidence_link_id}><strong>{words(item.evidence_kind ?? "field locator")}</strong><p>{words(item.purpose)}</p><p className={styles.technical}>{item.evidence_reference ?? item.field_locator ?? "Scoped historical locator"}</p></article>)}</div> : <div className={styles.info}>No compatible evidence links are available yet. Supported or confirmed analysis cannot proceed without one.</div>}</section>

        <section className={styles.caseSurface}><div className={styles.sectionHeader}><div><p className={styles.eyebrow}>Append-only assessment</p><h2>Analysis</h2></div><button className={styles.secondaryButton} disabled={pending || !analysesComplete} type="button" onClick={() => setDialog("analysis")}>Add analysis</button></div>{!analysesComplete ? <div className={styles.warning}>Current analysis is unavailable in this bounded projection. Returned entries remain visible as partial history only.</div> : currentAnalysis ? <article className={styles.currentAnalysis} aria-label="Current effective analysis"><span className={styles.historyMeta}>Current effective analysis · revision {currentAnalysis.revision_number}</span><strong>{currentAnalysis.assessment} · {words(currentAnalysis.root_cause_code)}</strong><p>{currentAnalysis.description}</p></article> : <div className={styles.info}>No analysis yet. Begin with a suspected assessment; stronger assessments require compatible historical evidence.</div>}<div className={styles.historyList}>{detail.analyses.toSorted((a, b) => b.revision_number - a.revision_number).map((item) => <article className={styles.historyItem} key={item.analysis_id}><span className={styles.historyMeta}>Revision {item.revision_number}</span><strong>{item.assessment} · {words(item.root_cause_code)}</strong><p>{item.description}</p></article>)}</div></section>

        <section className={styles.caseSurface}><div className={styles.sectionHeader}><div><p className={styles.eyebrow}>Bounded review work</p><h2>Resolution actions</h2></div><button className={styles.secondaryButton} disabled={pending || !hasCurrentRootCause || !actionsComplete} type="button" onClick={() => { setActionType(currentAction?.action_type ?? "grounding_integrity_action"); setActionStatus(currentAction ? "completed" : "planned"); setSafeChangeReference(""); setDialog("resolution"); }}>{currentAction ? "Update resolution" : "Plan resolution"}</button></div>{!actionsComplete ? <div className={styles.warning}>Current resolution state is unavailable in this bounded projection. Returned entries remain visible as partial history only.</div> : currentAction ? <div className={styles.historyList}>{detail.resolution_actions.toSorted((a, b) => b.action_id - a.action_id).map((item) => <article className={styles.historyItem} key={item.action_id}><span className={styles.historyMeta}>{item.status}</span><strong>{words(item.action_type)}</strong><p>{item.description}</p>{item.status === "completed" ? <p><strong>Work performed; case verification remains separate.</strong></p> : null}</article>)}</div> : <div className={styles.info}>No resolution action planned. Actions require a current supported or confirmed root cause.</div>}{!actionsComplete ? <div className={styles.historyList}>{detail.resolution_actions.toSorted((a, b) => b.action_id - a.action_id).map((item) => <article className={styles.historyItem} key={item.action_id}><span className={styles.historyMeta}>{item.status}</span><strong>{words(item.action_type)}</strong><p>{item.description}</p></article>)}</div> : null}</section>
      </div>

      <aside className={styles.detailAside}>
        {stale ? <section className={styles.warning} role="alert"><strong>This case changed since you opened it.</strong><br />Refresh the latest revision and review the new history before trying again.<div className={styles.formActions}><button className={styles.secondaryButton} type="button" onClick={() => void load()}>Refresh latest case</button></div></section> : mutationError ? <section className={styles.error} role="alert"><strong>Review action rejected</strong><br />{mutationError.message}</section> : null}
        <section className={styles.caseSurface}><p className={styles.eyebrow}>Audited workflow</p><h2>Lifecycle</h2><p className={styles.muted}>Commands advance one allowed step at a time. Completed work does not imply verification or model improvement.</p><div className={styles.commandRow}>{next ? <button className={styles.commandButton} disabled={pending || Boolean(lifecycleBlock)} type="button" onClick={() => void mutate({ command: "transition", expected_status: detail.status, expected_revision: detail.revision, status: next.status, transition_reason: next.reason })}>{next.label}</button> : null}{detail.status === "RESOLVED" ? <button className={styles.commandButton} disabled={pending} type="button" onClick={() => setDialog("verify")}>Verify case</button> : null}{!["DISMISSED", "DUPLICATE", "VERIFIED", "RESOLVED"].includes(detail.status) ? <button className={styles.quietButton} disabled={pending} type="button" onClick={() => void mutate({ command: "transition", expected_status: detail.status, expected_revision: detail.revision, status: "DISMISSED", transition_reason: "case_dismissed" })}>Dismiss</button> : null}{["CREATED", "REVIEWED"].includes(detail.status) ? <button className={styles.quietButton} disabled={pending} type="button" onClick={() => void openDuplicateDialog()}>Mark duplicate</button> : null}{["RESOLVED", "DISMISSED", "DUPLICATE", "VERIFIED"].includes(detail.status) ? <button className={styles.quietButton} disabled={pending} type="button" onClick={() => void mutate({ command: "transition", expected_status: detail.status, expected_revision: detail.revision, status: "REVIEWED", transition_reason: "case_reopened" })}>Reopen review</button> : null}</div>{lifecycleBlock ? <p className={styles.blockedReason}>{lifecycleBlock}</p> : null}<div className={styles.timeline}>{detail.transitions.toSorted((a, b) => b.new_revision - a.new_revision).map((item) => <article className={styles.timelineItem} key={item.transition_id}><span className={styles.historyMeta}>Revision {item.previous_revision} → {item.new_revision}</span><strong>{item.from_status} → {item.to_status}</strong><p>{words(item.reason)}</p>{item.verification_reference ? <p className={styles.technical}>Verification: {item.verification_reference}</p> : null}</article>)}</div></section>
        <section className={styles.caseSurface}><p className={styles.eyebrow}>Audit context</p><h2>Historical ownership</h2><div className={styles.historyList}><div className={styles.historyItem}><span className={styles.historyMeta}>Job</span><p className={styles.technical}>{short(detail.historical_job_id)}</p></div><div className={styles.historyItem}><span className={styles.historyMeta}>Candidate</span><p className={styles.technical}>{detail.historical_candidate_id ? short(detail.historical_candidate_id) : "Run scoped"}</p></div></div></section>
      </aside>
    </div>

    {dialog ? <div className={styles.dialogBackdrop} role="presentation"><section ref={dialogRef} className={styles.dialog} role="dialog" aria-modal="true" aria-labelledby="review-dialog-title" onKeyDown={onDialogKeyDown}><div className={styles.dialogHeader}><div><p className={styles.eyebrow}>Append-only review command</p><h2 id="review-dialog-title">{dialog === "analysis" ? "Add analysis" : dialog === "resolution" ? "Plan resolution action" : dialog === "verify" ? "Verify case" : "Mark duplicate"}</h2></div><button disabled={pending} type="button" onClick={closeDialog}>Close</button></div>
      {mutationError && !(mutationError instanceof Phase10ApiError && mutationError.status === 409) ? <div className={styles.error} role="alert"><strong>Review action rejected</strong><br />{mutationError.message}</div> : null}
      {dialog === "analysis" ? <form onSubmit={saveAnalysis}><div className={styles.formGrid}><label className={styles.field}>Assessment<select aria-label="Assessment" value={assessment} onChange={(event) => setAssessment(event.target.value as typeof assessment)}><option value="suspected">Suspected</option><option value="supported">Supported</option><option value="confirmed">Confirmed</option><option value="rejected">Rejected</option></select></label><label className={styles.field}>Root-cause type<select value={rootType} onChange={(event) => { const type = event.target.value as RootCauseType; setRootType(type); setRootCode(rootCauseOptions.find(([candidate]) => candidate === type)?.[1] ?? "explanation_unsupported_claim"); }}><option value="ranking">Ranking</option><option value="retrieval">Retrieval</option><option value="feature">Feature</option><option value="evidence">Evidence</option><option value="explanation">Explanation</option><option value="data_quality">Data quality</option><option value="integrity">Integrity</option></select></label><label className={styles.fieldWide}>Root-cause code<select value={rootCode} onChange={(event) => setRootCode(event.target.value as RootCauseCode)} required>{rootCodes.map(([, code]) => <option value={code} key={code}>{optionLabel(code)}</option>)}</select></label>{["supported", "confirmed"].includes(assessment) ? <label className={styles.fieldWide}>Supporting historical evidence<select value={evidenceId} onChange={(event) => setEvidenceId(event.target.value)} required><option value="">Select evidence</option>{detail.evidence_links.map((item) => <option key={item.evidence_link_id} value={item.evidence_link_id}>{item.evidence_kind ?? "field locator"} · link {item.evidence_link_id}</option>)}</select></label> : null}<label className={styles.fieldWide}>Assessment description<textarea aria-label="Assessment description" maxLength={1000} value={description} onChange={(event) => setDescription(event.target.value)} required /></label></div><div className={styles.formActions}><button className={styles.primaryButton} disabled={pending} type="submit">Save analysis</button></div></form> : null}
      {dialog === "resolution" ? <form onSubmit={saveResolution}><div className={styles.formGrid}><label className={styles.field}>Action type<select value={actionType} onChange={(event) => setActionType(event.target.value as ResolutionActionType)} required>{resolutionActionOptions.map((item) => <option key={item} value={item}>{optionLabel(item)}</option>)}</select></label><label className={styles.field}>Action status<select value={actionStatus} onChange={(event) => setActionStatus(event.target.value as typeof actionStatus)}><option value="planned">Planned</option><option value="in_progress">In progress</option><option value="completed">Completed</option><option value="cancelled">Cancelled</option></select></label><label className={styles.fieldWide}>Action description<textarea maxLength={1000} value={description} onChange={(event) => setDescription(event.target.value)} required /></label>{["completed", "cancelled"].includes(actionStatus) ? <label className={styles.fieldWide}>Safe change reference<input value={safeChangeReference} onChange={(event) => setSafeChangeReference(event.target.value)} placeholder="commit:case-specific-change" /></label> : null}</div><p className={styles.muted}>A new action entry supersedes the prior entry; history is never overwritten. Completed means work performed, not verified.</p><div className={styles.formActions}><button className={styles.primaryButton} disabled={pending} type="submit">Save resolution action</button></div></form> : null}
      {dialog === "verify" ? <form onSubmit={(event) => { event.preventDefault(); void mutate({ command: "transition", expected_status: detail.status, expected_revision: detail.revision, status: "VERIFIED", transition_reason: "verification_linked", verification_reference: verificationReference }); }}><label className={styles.fieldWide}>Immutable verification reference<input value={verificationReference} onChange={(event) => setVerificationReference(event.target.value)} placeholder="commit:case-verification" required /></label><p className={styles.muted}>Verification is case-specific provenance, not a Phase 11 quality metric.</p><div className={styles.formActions}><button className={styles.primaryButton} disabled={pending} type="submit">Verify case</button></div></form> : null}
      {dialog === "duplicate" ? <form onSubmit={(event) => { event.preventDefault(); void mutate({ command: "transition", expected_status: detail.status, expected_revision: detail.revision, status: "DUPLICATE", transition_reason: "duplicate_linked", duplicate_of_bad_case_id: canonicalCase }); }}><label className={styles.fieldWide}>Canonical case<select aria-label="Canonical case" value={canonicalCase} onChange={(event) => setCanonicalCase(event.target.value)} required disabled={canonicalLoading || pending}><option value="">{canonicalLoading ? "Loading compatible cases…" : "Select a compatible case"}</option>{canonicalOptions.map((item) => <option key={item.bad_case_id} value={item.bad_case_id}>{words(item.symptom_code)} · {item.status} · revision {item.revision}</option>)}</select></label>{canonicalError ? <div className={styles.error} role="alert">{canonicalError}</div> : !canonicalLoading && canonicalOptions.length === 0 ? <div className={styles.info}>No compatible canonical case is available in the bounded review queue.</div> : null}<div className={styles.formActions}><button className={styles.primaryButton} disabled={pending || canonicalLoading || !canonicalCase} type="submit">Confirm duplicate</button></div></form> : null}
    </section></div> : null}
  </>;
}
