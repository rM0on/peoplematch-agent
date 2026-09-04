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


function short(value: string) { return value.length > 24 ? `${value.slice(0, 10)}…${value.slice(-8)}` : value; }

const lifecycle: Partial<Record<BadCaseStatus, { status: BadCaseStatus; reason: TransitionReason; label: string }>> = {
  CREATED: { status: "REVIEWED", reason: "review_completed", label: "标记为已复核" },
  REVIEWED: { status: "ROOT_CAUSE_IDENTIFIED", reason: "root_cause_supported", label: "确认根因" },
  ROOT_CAUSE_IDENTIFIED: { status: "ACTION_PLANNED", reason: "action_created", label: "确认行动计划" },
  ACTION_PLANNED: { status: "RESOLVED", reason: "actions_completed", label: "标记为已处理" },
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
      setLoadError(caught instanceof Phase10ApiError || caught instanceof Error ? caught : new Error("Bad Case 暂不可用"));
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
        setLoadError(caught instanceof Phase10ApiError || caught instanceof Error ? caught : new Error("Bad Case 暂不可用"));
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
      const normalized = caught instanceof Phase10ApiError || caught instanceof Error ? caught : new Error("复核操作暂时无法保存");
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
        : "兼容的 Bad Case 暂不可用");
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

  if (loadError instanceof Phase10ApiError && loadError.status === 404) return <section className={styles.empty}><div><h1>未找到 Bad Case</h1><p>该历史复核记录不可用。</p><Link href="/bad-cases">返回 Bad Case 列表</Link></div></section>;
  if (loadError) return <section className={styles.error} role="alert"><strong>Bad Case 暂不可用</strong><br />{loadError.message}<div className={styles.formActions}><button className={styles.secondaryButton} onClick={() => void load()} type="button">重新尝试</button></div></section>;
  if (!detail) return <section className={styles.loading} aria-label="正在加载 Bad Case 详情"><div className={styles.skeleton} /></section>;

  const stale = mutationError instanceof Phase10ApiError && mutationError.status === 409;
  const next = lifecycle[detail.status];
  const hasCurrentRootCause = currentAnalysis?.assessment === "supported" || currentAnalysis?.assessment === "confirmed";
  const lifecycleBlock = detail.status === "REVIEWED" && !analysesComplete
    ? "分析历史是有界的部分投影，暂时不能确认根因。"
    : detail.status === "REVIEWED" && !hasCurrentRootCause
    ? "确认根因前，最新分析必须达到‘有证据支持’或‘已确认’。"
    : detail.status === "ROOT_CAUSE_IDENTIFIED" && !actionsComplete
      ? "处理历史是有界的部分投影，暂时不能规划行动。"
      : detail.status === "ROOT_CAUSE_IDENTIFIED" && !currentActions.some((item) => ["planned", "in_progress"].includes(item.status))
      ? "行动计划需要一条兼容且有效的处理记录。"
      : detail.status === "ACTION_PLANNED" && !actionsComplete
        ? "处理历史是有界的部分投影，暂时不能完成此 Bad Case。"
        : detail.status === "ACTION_PLANNED" && currentActions.some((item) => !["completed", "cancelled", "superseded"].includes(item.status))
        ? "完成 Bad Case 前，所有当前行动都必须进入终态。"
        : null;
  return <>
    <div className={styles.detailGrid} aria-label="Bad Case 复核工作区" aria-busy={pending}>
      <div className={styles.detailMain}>
        <section className={styles.caseSurface}>
          <div className={styles.detailHeader}><div><p className={styles.eyebrow}>Bad Case 概览</p><h1 data-modal-focus-fallback tabIndex={-1}>{optionLabel(detail.symptom_code)}</h1><p className={styles.muted}>这是正在复核的历史观察，不是通用工单，也不代表模型质量结论。</p></div><div><span className={styles.badge}>{optionLabel(detail.status)}</span> <span className={styles.severity}>{optionLabel(detail.severity)}</span></div></div>
          <div className={styles.summaryGrid}><div><span>修订版本</span><strong>{detail.revision}</strong></div><div><span>问题类型</span><strong>{optionLabel(detail.symptom_family)}</strong></div><div><span>MatchRun</span><strong className={styles.technical}>{short(detail.primary_match_run_id)}</strong></div><div><span>历史排名</span><strong>{detail.result_rank ? `#${detail.result_rank}` : "Run 级问题"}</strong></div></div>
          {detail.truncated_collections.length ? <div className={styles.warning}><strong>部分历史记录</strong><br />当前投影只包含有界的 {detail.truncated_collections.map(optionLabel).join("、")}；刷新不会让被截断历史自动变完整。</div> : null}
        </section>

        <section className={styles.caseSurface}><div className={styles.sectionHeader}><div><p className={styles.eyebrow}>问题来源</p><h2>历史观察来源</h2></div><span className={styles.badge}>{detail.sources.length} 条观察</span></div><div className={styles.historyList}>{detail.sources.map((source, index) => <article className={styles.historyItem} key={`${source.source_type}-${source.feedback_id ?? source.system_signal_id}-${index}`}><strong>{source.source_type === "feedback" ? "人工 Feedback" : "确定性系统信号"}</strong><p className={styles.technical}>{short(source.feedback_id ?? source.system_signal_id ?? "不可用")}</p></article>)}</div></section>

        <section className={styles.caseSurface}><div className={styles.sectionHeader}><div><p className={styles.eyebrow}>冻结的历史引用</p><h2>Evidence 证据</h2></div><span className={styles.badge}>{detail.evidence_links.length} 条引用</span></div>{detail.evidence_links.length ? <div className={styles.historyList}>{detail.evidence_links.map((item) => <article className={styles.historyItem} key={item.evidence_link_id}><strong>{optionLabel(item.evidence_kind ?? "字段定位")}</strong><p>{optionLabel(item.purpose)}</p><p className={styles.technical}>{item.evidence_reference ?? item.field_locator ?? "受限历史定位"}</p></article>)}</div> : <div className={styles.info}>暂无兼容的 Evidence 引用；缺少证据时不能提交“有证据支持”或“已确认”的分析。</div>}</section>

        <section className={styles.caseSurface}><div className={styles.sectionHeader}><div><p className={styles.eyebrow}>追加式原因分析</p><h2>根因分析</h2></div><button className={styles.secondaryButton} disabled={pending || !analysesComplete} type="button" onClick={() => setDialog("analysis")}>添加分析</button></div>{!analysesComplete ? <div className={styles.warning}>当前投影未包含完整分析历史；已返回条目只能作为部分历史查看。</div> : currentAnalysis ? <article className={styles.currentAnalysis} aria-label="当前有效分析"><span className={styles.historyMeta}>当前有效分析 · 修订 {currentAnalysis.revision_number}</span><strong>{optionLabel(currentAnalysis.assessment)} · {optionLabel(currentAnalysis.root_cause_code)}</strong><p>{currentAnalysis.description}</p></article> : <div className={styles.info}>暂无根因分析。可先记录“疑似”判断；更强结论需要兼容的历史 Evidence。</div>}<div className={styles.historyList}>{detail.analyses.toSorted((a, b) => b.revision_number - a.revision_number).map((item) => <article className={styles.historyItem} key={item.analysis_id}><span className={styles.historyMeta}>修订 {item.revision_number}</span><strong>{optionLabel(item.assessment)} · {optionLabel(item.root_cause_code)}</strong><p>{item.description}</p></article>)}</div></section>

        <section className={styles.caseSurface}><div className={styles.sectionHeader}><div><p className={styles.eyebrow}>有界复核行动</p><h2>处理行动</h2></div><button className={styles.secondaryButton} disabled={pending || !hasCurrentRootCause || !actionsComplete} type="button" onClick={() => { setActionType(currentAction?.action_type ?? "grounding_integrity_action"); setActionStatus(currentAction ? "completed" : "planned"); setSafeChangeReference(""); setDialog("resolution"); }}>{currentAction ? "更新处理行动" : "规划处理行动"}</button></div>{!actionsComplete ? <div className={styles.warning}>当前投影未包含完整处理历史；已返回条目只能作为部分历史查看。</div> : currentAction ? <div className={styles.historyList}>{detail.resolution_actions.toSorted((a, b) => b.action_id - a.action_id).map((item) => <article className={styles.historyItem} key={item.action_id}><span className={styles.historyMeta}>{optionLabel(item.status)}</span><strong>{optionLabel(item.action_type)}</strong><p>{item.description}</p>{item.status === "completed" ? <p><strong>工作已完成；Bad Case 核验仍是独立步骤。</strong></p> : null}</article>)}</div> : <div className={styles.info}>暂无处理行动。只有当前根因达到“有证据支持”或“已确认”后才能规划行动。</div>}{!actionsComplete ? <div className={styles.historyList}>{detail.resolution_actions.toSorted((a, b) => b.action_id - a.action_id).map((item) => <article className={styles.historyItem} key={item.action_id}><span className={styles.historyMeta}>{optionLabel(item.status)}</span><strong>{optionLabel(item.action_type)}</strong><p>{item.description}</p></article>)}</div> : null}</section>
      </div>

      <aside className={styles.detailAside}>
        {stale ? <section className={styles.warning} role="alert"><strong>该 Bad Case 已在其他位置发生变化。</strong><br />请刷新最新修订并复核新增历史后再重试。<div className={styles.formActions}><button className={styles.secondaryButton} type="button" onClick={() => void load()}>刷新最新记录</button></div></section> : mutationError ? <section className={styles.error} role="alert"><strong>复核操作被拒绝</strong><br />{mutationError.message}</section> : null}
        <section className={styles.caseSurface}><p className={styles.eyebrow}>可审计工作流</p><h2>生命周期</h2><p className={styles.muted}>命令每次只推进一个允许状态；行动完成不代表已核验，也不证明模型改进。</p><div className={styles.commandRow}>{next ? <button className={styles.commandButton} disabled={pending || Boolean(lifecycleBlock)} type="button" onClick={() => void mutate({ command: "transition", expected_status: detail.status, expected_revision: detail.revision, status: next.status, transition_reason: next.reason })}>{next.label}</button> : null}{detail.status === "RESOLVED" ? <button className={styles.commandButton} disabled={pending} type="button" onClick={() => setDialog("verify")}>核验 Bad Case</button> : null}{!["DISMISSED", "DUPLICATE", "VERIFIED", "RESOLVED"].includes(detail.status) ? <button className={styles.quietButton} disabled={pending} type="button" onClick={() => void mutate({ command: "transition", expected_status: detail.status, expected_revision: detail.revision, status: "DISMISSED", transition_reason: "case_dismissed" })}>驳回</button> : null}{["CREATED", "REVIEWED"].includes(detail.status) ? <button className={styles.quietButton} disabled={pending} type="button" onClick={() => void openDuplicateDialog()}>标记为重复</button> : null}{["RESOLVED", "DISMISSED", "DUPLICATE", "VERIFIED"].includes(detail.status) ? <button className={styles.quietButton} disabled={pending} type="button" onClick={() => void mutate({ command: "transition", expected_status: detail.status, expected_revision: detail.revision, status: "REVIEWED", transition_reason: "case_reopened" })}>重新打开复核</button> : null}</div>{lifecycleBlock ? <p className={styles.blockedReason}>{lifecycleBlock}</p> : null}<div className={styles.timeline}>{detail.transitions.toSorted((a, b) => b.new_revision - a.new_revision).map((item) => <article className={styles.timelineItem} key={item.transition_id}><span className={styles.historyMeta}>修订 {item.previous_revision} → {item.new_revision}</span><strong>{optionLabel(item.from_status)} → {optionLabel(item.to_status)}</strong><p>{optionLabel(item.reason)}</p>{item.verification_reference ? <p className={styles.technical}>核验引用：{item.verification_reference}</p> : null}</article>)}</div></section>
        <section className={styles.caseSurface}><p className={styles.eyebrow}>审计上下文</p><h2>历史归属</h2><div className={styles.historyList}><div className={styles.historyItem}><span className={styles.historyMeta}>岗位</span><p className={styles.technical}>{short(detail.historical_job_id)}</p></div><div className={styles.historyItem}><span className={styles.historyMeta}>候选人</span><p className={styles.technical}>{detail.historical_candidate_id ? short(detail.historical_candidate_id) : "Run 级问题"}</p></div></div></section>
      </aside>
    </div>

    {dialog ? <div className={styles.dialogBackdrop} role="presentation"><section ref={dialogRef} className={styles.dialog} role="dialog" aria-modal="true" aria-labelledby="review-dialog-title" onKeyDown={onDialogKeyDown}><div className={styles.dialogHeader}><div><p className={styles.eyebrow}>追加式复核命令</p><h2 id="review-dialog-title">{dialog === "analysis" ? "添加根因分析" : dialog === "resolution" ? "规划处理行动" : dialog === "verify" ? "核验 Bad Case" : "标记为重复记录"}</h2></div><button disabled={pending} type="button" onClick={closeDialog}>关闭</button></div>
      {mutationError && !(mutationError instanceof Phase10ApiError && mutationError.status === 409) ? <div className={styles.error} role="alert"><strong>复核操作被拒绝</strong><br />{mutationError.message}</div> : null}
      {dialog === "analysis" ? <form onSubmit={saveAnalysis}><div className={styles.formGrid}><label className={styles.field}>分析结论<select aria-label="分析结论" value={assessment} onChange={(event) => setAssessment(event.target.value as typeof assessment)}><option value="suspected">疑似</option><option value="supported">有证据支持</option><option value="confirmed">已确认</option><option value="rejected">已否定</option></select></label><label className={styles.field}>根因类型<select value={rootType} onChange={(event) => { const type = event.target.value as RootCauseType; setRootType(type); setRootCode(rootCauseOptions.find(([candidate]) => candidate === type)?.[1] ?? "explanation_unsupported_claim"); }}><option value="ranking">排序</option><option value="retrieval">召回</option><option value="feature">特征</option><option value="evidence">Evidence</option><option value="explanation">解释</option><option value="data_quality">数据质量</option><option value="integrity">完整性</option></select></label><label className={styles.fieldWide}>根因代码<select value={rootCode} onChange={(event) => setRootCode(event.target.value as RootCauseCode)} required>{rootCodes.map(([, code]) => <option value={code} key={code}>{optionLabel(code)}</option>)}</select></label>{["supported", "confirmed"].includes(assessment) ? <label className={styles.fieldWide}>支持此结论的历史 Evidence<select value={evidenceId} onChange={(event) => setEvidenceId(event.target.value)} required><option value="">选择 Evidence</option>{detail.evidence_links.map((item) => <option key={item.evidence_link_id} value={item.evidence_link_id}>{item.evidence_kind ?? "字段定位"} · 引用 {item.evidence_link_id}</option>)}</select></label> : null}<label className={styles.fieldWide}>分析说明<textarea aria-label="分析说明" maxLength={1000} value={description} onChange={(event) => setDescription(event.target.value)} required /></label></div><div className={styles.formActions}><button className={styles.primaryButton} disabled={pending} type="submit">保存分析</button></div></form> : null}
      {dialog === "resolution" ? <form onSubmit={saveResolution}><div className={styles.formGrid}><label className={styles.field}>行动类型<select value={actionType} onChange={(event) => setActionType(event.target.value as ResolutionActionType)} required>{resolutionActionOptions.map((item) => <option key={item} value={item}>{optionLabel(item)}</option>)}</select></label><label className={styles.field}>行动状态<select value={actionStatus} onChange={(event) => setActionStatus(event.target.value as typeof actionStatus)}><option value="planned">已规划</option><option value="in_progress">进行中</option><option value="completed">已完成</option><option value="cancelled">已取消</option></select></label><label className={styles.fieldWide}>行动说明<textarea maxLength={1000} value={description} onChange={(event) => setDescription(event.target.value)} required /></label>{["completed", "cancelled"].includes(actionStatus) ? <label className={styles.fieldWide}>安全变更引用<input value={safeChangeReference} onChange={(event) => setSafeChangeReference(event.target.value)} placeholder="commit:case-specific-change" /></label> : null}</div><p className={styles.muted}>新行动条目会替代上一条当前记录，但历史永不覆盖；“已完成”表示工作已执行，不表示已核验。</p><div className={styles.formActions}><button className={styles.primaryButton} disabled={pending} type="submit">保存处理行动</button></div></form> : null}
      {dialog === "verify" ? <form onSubmit={(event) => { event.preventDefault(); void mutate({ command: "transition", expected_status: detail.status, expected_revision: detail.revision, status: "VERIFIED", transition_reason: "verification_linked", verification_reference: verificationReference }); }}><label className={styles.fieldWide}>不可变核验引用<input value={verificationReference} onChange={(event) => setVerificationReference(event.target.value)} placeholder="commit:case-verification" required /></label><p className={styles.muted}>核验是 Case 级来源证明，不是 Phase 11 模型质量指标。</p><div className={styles.formActions}><button className={styles.primaryButton} disabled={pending} type="submit">核验 Bad Case</button></div></form> : null}
      {dialog === "duplicate" ? <form onSubmit={(event) => { event.preventDefault(); void mutate({ command: "transition", expected_status: detail.status, expected_revision: detail.revision, status: "DUPLICATE", transition_reason: "duplicate_linked", duplicate_of_bad_case_id: canonicalCase }); }}><label className={styles.fieldWide}>主 Bad Case<select aria-label="主 Bad Case" value={canonicalCase} onChange={(event) => setCanonicalCase(event.target.value)} required disabled={canonicalLoading || pending}><option value="">{canonicalLoading ? "正在加载兼容记录…" : "选择兼容的 Bad Case"}</option>{canonicalOptions.map((item) => <option key={item.bad_case_id} value={item.bad_case_id}>{optionLabel(item.symptom_code)} · {optionLabel(item.status)} · 修订 {item.revision}</option>)}</select></label>{canonicalError ? <div className={styles.error} role="alert">{canonicalError}</div> : !canonicalLoading && canonicalOptions.length === 0 ? <div className={styles.info}>当前有界复核队列中没有兼容的主 Bad Case。</div> : null}<div className={styles.formActions}><button className={styles.primaryButton} disabled={pending || canonicalLoading || !canonicalCase} type="submit">确认标记为重复</button></div></form> : null}
    </section></div> : null}
  </>;
}
