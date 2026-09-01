"use client";

import { useCallback, useMemo, useState } from "react";
import { HistoricalFeedbackEntry } from "@/features/phase10/historical-feedback-entry";
import { useModalDialog } from "@/features/phase10/use-modal-dialog";
import { DemoApiError, fetchDemoSamples, runDemo } from "@/lib/demo-api";
import type { DemoRun, DemoStage } from "@/types/demo";
import { AppSidebar } from "./app-sidebar";
import styles from "./matching-results.module.css";
import reviewStyles from "../phase10/phase10.module.css";

const stageCopy: Record<DemoStage, string> = {
  candidate: "正在解析候选人简历", job: "正在解析岗位描述", index: "正在刷新派生检索索引",
  ranking: "正在执行 Hybrid Retrieval + LambdaMART", explanation: "正在生成证据约束解释", complete: "匹配已完成",
};
const featureLabels = { skill_fit_score: "技能匹配", project_evidence_score: "项目证据", role_direction_score: "方向匹配", location_score: "地点约束", seniority_score: "资历匹配" } as const;
const storySteps = ["结构化解析", "候选召回", "特征计算", "LTR 排序", "Evidence 解释", "MatchRun 复核"] as const;

function safeError(error: unknown): { message: string; requestId: string | null } {
  if (!(error instanceof DemoApiError)) return { message: "请求未完成，请检查本地服务后重试。", requestId: null };
  const messages: Record<string, string> = {
    provider_unavailable: "模型服务暂不可用，请确认 Provider 配置后重试。", provider_timeout: "模型服务响应超时，请稍后重试。",
    provider_output_invalid: "模型返回的结构化结果未通过校验，请重试。", network_error: "无法连接后端，请确认本地服务已启动。",
    api_unconfigured: "前端尚未配置后端 API 地址。",
  };
  return { message: messages[error.code] ?? "请求未完成，请检查输入与本地服务后重试。", requestId: error.requestId };
}

export function MatchingResultsScreen() {
  const [candidateText, setCandidateText] = useState("");
  const [jobText, setJobText] = useState("");
  const [sampleLoaded, setSampleLoaded] = useState(false);
  const [stage, setStage] = useState<DemoStage | null>(null);
  const [result, setResult] = useState<DemoRun | null>(null);
  const [selectedRank, setSelectedRank] = useState(1);
  const [error, setError] = useState<{ message: string; requestId: string | null } | null>(null);
  const [busy, setBusy] = useState(false);
  const [reviewOpen, setReviewOpen] = useState(false);
  const closeReview = useCallback(() => setReviewOpen(false), []);
  const { dialogRef, onDialogKeyDown } = useModalDialog(reviewOpen, closeReview);
  const selected = result?.matchRun.results.find((item) => item.result_rank === selectedRank) ?? null;
  const explanation = result?.explanationRun.explanations.find((item) => item.result_rank === selectedRank) ?? null;
  const inputCandidateId = result?.candidate.record?.candidate_id;
  const activeStoryStep = result ? 5 : stage === "candidate" || stage === "job" ? 0 : stage === "index" ? 1 : stage === "ranking" ? 3 : stage === "explanation" ? 4 : -1;
  const inputError = useMemo(() => {
    const candidateLength = candidateText.trim().length;
    const jobLength = jobText.trim().length;
    if (candidateLength > 0 && candidateLength < 40) return "候选人简历至少需要 40 个字符。";
    if (candidateLength > 5_000) return "候选人简历不能超过 5,000 个字符。";
    if (jobLength > 0 && jobLength < 60) return "岗位描述至少需要 60 个字符。";
    if (jobLength > 6_000) return "岗位描述不能超过 6,000 个字符。";
    return null;
  }, [candidateText, jobText]);

  async function loadSamples() {
    setBusy(true); setError(null);
    try { const samples = await fetchDemoSamples(); setCandidateText(samples.candidate_text); setJobText(samples.job_text); setSampleLoaded(true); }
    catch (caught) { setError(safeError(caught)); }
    finally { setBusy(false); }
  }
  async function executeDemo() {
    if (inputError || !candidateText.trim() || !jobText.trim()) { setError({ message: inputError ?? "请先填写候选人简历与岗位描述。", requestId: null }); return; }
    setBusy(true); setError(null); setResult(null); setSelectedRank(1);
    try { setResult(await runDemo({ candidateText, jobText, onStage: setStage })); }
    catch (caught) { setError(safeError(caught)); }
    finally { setBusy(false); }
  }

  return <div className={styles.appShell}>
    <a className={styles.skipLink} href="#matching-results">跳转到匹配工作区</a><AppSidebar />
    <main className={styles.mainSurface} id="matching-results"><div className={styles.contentFrame}>
      <header className={styles.hero}><div><p className={styles.eyebrow}>AI Talent Recommendation System</p><h1>岗位 Query 驱动的候选推荐</h1><p>岗位需求触发 Candidate Retrieval、显式特征计算与 LambdaMART 排序；LLM 负责结构化与解释，不直接决定排序。</p></div><button className={styles.historyButton} type="button" onClick={() => setReviewOpen(true)}>复核历史结果</button></header>
      <section className={styles.storyPanel} aria-labelledby="story-title">
        <div className={styles.storyHeader}><div><p className={styles.eyebrow}>3 分钟推荐系统体验</p><h2 id="story-title">从岗位 Query 到 Top-K 候选人</h2></div><p>同一条可审计流水线串联 Retrieval、Feature Engineering、LTR、Evidence 与 Bad Case Review。</p></div>
        <ol className={styles.storySteps}>{storySteps.map((label, index) => <li aria-current={index === activeStoryStep ? "step" : undefined} className={index === activeStoryStep ? styles.storyStepActive : index < activeStoryStep ? styles.storyStepComplete : styles.storyStep} key={label}><span>{String(index + 1).padStart(2, "0")}</span><strong>{label}</strong></li>)}</ol>
      </section>
      <section className={styles.inputPanel} aria-labelledby="demo-input-title">
        <div className={styles.sectionTitle}><div><p className={styles.eyebrow}>Interactive Recommendation Demo</p><h2 id="demo-input-title">输入 Resume 与岗位 Query</h2><p className={styles.inputNarrative}>Resume 会作为一个候选人加入本地候选池；JD 是检索 Query。系统随后从整个候选池召回、计算特征并返回 Top-K，而不是只给输入简历打一个匹配分。</p></div><button className={styles.secondaryButton} type="button" disabled={busy} onClick={loadSamples}>加载安全示例</button></div>
        <div className={styles.inputGrid}><label>候选人简历文本<textarea value={candidateText} maxLength={5_000} onChange={(event) => { setCandidateText(event.target.value); setSampleLoaded(false); }} placeholder="粘贴候选人简历，或加载 synthetic 示例" /></label><label>岗位描述文本<textarea value={jobText} maxLength={6_000} onChange={(event) => { setJobText(event.target.value); setSampleLoaded(false); }} placeholder="粘贴岗位描述，或加载 synthetic 示例" /></label></div>
        <div className={styles.inputFooter}><div>{sampleLoaded ? <p className={styles.safeNote}>示例数据为 synthetic sandbox，不包含真实个人信息。</p> : null}{inputError ? <p className={styles.validationNote}>{inputError}</p> : null}</div><button className={styles.primaryButton} type="button" disabled={busy} onClick={executeDemo}>{busy ? stage ? stageCopy[stage] : "正在准备" : "开始完整匹配"}</button></div>
      </section>
      {error ? <div className={styles.errorPanel} role="alert"><div><strong>{error.message}</strong>{error.requestId ? <span>Request ID: {error.requestId}</span> : null}</div><button type="button" onClick={executeDemo}>重新尝试</button></div> : null}
      {!result ? <section className={styles.emptyPanel} aria-live="polite"><span aria-hidden="true">01 → 02 → 03</span><h2>{busy && stage ? stageCopy[stage] : "尚未运行匹配"}</h2><p>结果区将展示候选池、raw LTR margin、证据约束解释和不可变 MatchRun 轨迹。</p></section> :
        <section className={styles.resultsPanel} aria-labelledby="results-title">
          <header className={styles.resultHeader}><div><p className={styles.eyebrow}>MatchRun 已完成 · 默认 LambdaMART</p><h2 id="results-title">{result.job.draft.role_title}</h2><p>{result.job.draft.company_name} · {result.job.draft.location.cities.join(" / ") || "地点未指定"}</p><p className={styles.poolMeta}>以岗位为 Query · 索引 {result.index.candidate_count} 名候选人 · 输出 Top {result.matchRun.result_count}</p></div><div className={styles.runIdentity}><span>Run ID</span><code>{result.matchRun.run_id}</code><span>fingerprint {result.matchRun.result_fingerprint.slice(0, 12)}…</span></div></header>
          <div className={styles.resultGrid}><div className={styles.shortlist}><h3>岗位候选池 Top-K</h3>{result.matchRun.results.map((item) => { const isInputCandidate = item.candidate_id === inputCandidateId; return <button key={item.match_result_id} type="button" aria-label={`查看第 ${item.result_rank} 名 ${item.candidate_id}`} aria-pressed={item.result_rank === selectedRank} className={item.result_rank === selectedRank ? styles.selectedResult : styles.resultRow} onClick={() => setSelectedRank(item.result_rank)}><span className={styles.rank}>#{item.result_rank}</span><span className={styles.candidateLabel}><strong>{isInputCandidate ? "本次输入候选人" : `候选人 #${item.result_rank}`}</strong><small className={styles.candidateDescriptor}>{isInputCandidate ? result.candidate.draft.name : "候选池候选人"}</small><small className={styles.candidateTechnicalId}>Candidate ID · {item.candidate_id}</small><small>Retrieval #{item.retrieval_rank} → LTR #{item.ltr_rank}</small></span><span className={styles.shortlistModelScore}><small>LTR Score</small><code>{item.ltr_score_raw.toFixed(6)}</code></span></button>; })}</div>
            {selected ? <article className={styles.detail} aria-live="polite"><div className={styles.scoreHeader}><div><p className={styles.eyebrow}>Ranking Evidence</p><h3>{selected.candidate_id === inputCandidateId ? result.candidate.draft.name : `候选人 #${selected.result_rank}`}</h3><p className={styles.candidateTechnicalId}>Candidate ID · {selected.candidate_id}</p></div><div className={styles.scoreMeta}><span>LTR Score</span><code>{selected.ltr_score_raw.toFixed(6)}</code><small>排序模型原始分值；不是概率、匹配百分比或录用概率。</small></div></div>
              <div className={styles.featureGrid}>{Object.entries(featureLabels).map(([key, label]) => { const value = selected[key as keyof typeof featureLabels]; return <div key={key}><span>{label}</span><strong>{typeof value === "number" ? value.toFixed(2) : "missing"}</strong><i style={{ width: `${typeof value === "number" ? Math.max(0, Math.min(100, value * 100)) : 0}%` }} /></div>; })}</div>
              <section className={styles.explanation}><p className={styles.eyebrow}>Evidence Grounding</p><h4>为什么推荐该候选人</h4><p>{explanation?.summary.text ?? "该结果没有对应的持久化解释。"}</p><div className={styles.refs}>{explanation?.summary.evidence_refs.map((ref) => <code key={ref}>{ref}</code>)}</div>{explanation?.missing_skills.length ? <p className={styles.risk}>待验证：{explanation.missing_skills.map((item) => item.requirement_text).join("、")}</p> : null}</section>
              <section className={styles.trace}><p className={styles.eyebrow}>MatchRun Audit</p><h4>不可变运行轨迹</h4><ol>{result.matchRun.steps.map((item) => <li key={item.sequence}><code>{item.step_name}</code><span>{item.status}</span></li>)}</ol></section>
            </article> : null}</div>
        </section>}
      <aside className={styles.integrityNote}><strong>边界：</strong>排序由冻结的 Hybrid Retrieval + LambdaMART 流水线生成；解释只读取对应 MatchRun 的 Evidence Facts，不能修改候选人顺序或分数。</aside>
    </div></main>
    {reviewOpen ? <div className={reviewStyles.dialogBackdrop} role="presentation"><section ref={dialogRef} onKeyDown={onDialogKeyDown} className={`${reviewStyles.dialog} ${reviewStyles.feedbackDialog}`} role="dialog" aria-modal="true" aria-labelledby="feedback-dialog-title"><div className={reviewStyles.dialogHeader}><div><p className={reviewStyles.eyebrow}>Persisted review workflow</p><h2 id="feedback-dialog-title">复核历史结果</h2></div><button type="button" onClick={closeReview}>关闭</button></div><div className={reviewStyles.info}>此流程只针对已持久化的历史 MatchRun；当前输入画布不会被当成 Feedback 目标，历史归属由服务端解析。</div><HistoricalFeedbackEntry /></section></div> : null}
  </div>;
}
