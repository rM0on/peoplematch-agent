"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AppSidebar } from "@/features/matching-results/app-sidebar";
import { getMatchRun, listExplanationRuns } from "@/lib/phase10-api";
import type { MatchRunDetail, ExplanationRunSummary } from "@/types/phase10";
import shell from "@/features/matching-results/matching-results.module.css";
import styles from "./recruiter-view.module.css";

const labels: Record<string, string> = {
  resolve_inputs: "解析输入", retrieve_candidates: "Hybrid Retrieval", build_features: "Feature Engineering",
  rank_candidates: "LambdaMART", phase6_ltr_rank: "LambdaMART", rerank_candidates: "Cross Encoder（实验策略）",
  persist_results: "持久化 MatchRun",
};

export function AgentRunScreen() {
  const [runId, setRunId] = useState("");
  const [run, setRun] = useState<MatchRunDetail | null>(null);
  const [explanations, setExplanations] = useState<ExplanationRunSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const requested = new URLSearchParams(window.location.search).get("runId") ?? "";
    if (!requested) return;
    let cancelled = false;
    Promise.resolve().then(() => { if (!cancelled) { setRunId(requested); setBusy(true); } });
    Promise.all([getMatchRun(requested), listExplanationRuns(requested)]).then(([match, page]) => {
      if (!cancelled) { setRun(match.data); setExplanations(page.data.items); }
    }).catch(() => { if (!cancelled) setError("无法读取这条运行轨迹。"); })
      .finally(() => { if (!cancelled) setBusy(false); });
    return () => { cancelled = true; };
  }, []);
  async function inspect() {
    if (!runId.trim()) return;
    setBusy(true); setError(null); setRun(null);
    try {
      const [match, page] = await Promise.all([getMatchRun(runId.trim()), listExplanationRuns(runId.trim())]);
      setRun(match.data); setExplanations(page.data.items);
      window.history.replaceState(null, "", `/agent-run?runId=${encodeURIComponent(runId.trim())}`);
    } catch { setError("无法读取这条运行轨迹。"); }
    finally { setBusy(false); }
  }
  return <div className={shell.appShell}><AppSidebar active="agent-run" /><main className={shell.mainSurface}><div className={styles.frame}>
    <header className={styles.header}><div><p className={styles.eyebrow}>PERSISTED TRACE / AGENT RUN</p><h1>推荐是怎样形成的。</h1><p>展示真实持久化步骤与 ExplanationRun 状态。未记录的内部子步骤不会伪装成 AgentStep。</p></div></header>
    <section className={styles.runPicker}><div><strong>读取 MatchRun</strong><span>输入现有 ID，只读检查完整轨迹。</span></div><input aria-label="MatchRun ID" value={runId} onChange={(event) => setRunId(event.target.value)} /><button type="button" disabled={busy} onClick={inspect}>查看轨迹</button></section>
    {busy ? <div className={styles.state} role="status">正在读取持久化运行轨迹…</div> : null}{error ? <div className={styles.error} role="alert">{error}</div> : null}
    {run && <><section className={styles.jobHeader}><div><p className={styles.eyebrow}>MATCHRUN / {run.status}</p><h2>{run.run_id}</h2><p>{run.results.length} 名候选人 · {run.ranking_variant}</p></div><Link href={`/?runId=${encodeURIComponent(run.run_id)}`}>查看招聘筛查 →</Link></section>
      <div className={styles.traceGrid}><section><p className={styles.sectionKicker}>Persisted Trace</p><h2>已保存的排序阶段</h2><ol>{run.steps.map((step) => <li key={step.sequence}><b>{labels[step.step_name] ?? step.step_name}</b><span>{step.status}</span><small>{step.duration_ms === null ? "时长未记录" : `${step.duration_ms.toFixed(1)} ms`}</small></li>)}</ol></section><section><p className={styles.sectionKicker}>Derived Stage Metadata</p><h2>解释与结构化评估</h2><p>Evidence Build → Semantic Selection → Deterministic Binding → Grounding → RecruiterProposition 是 Explanation / API 阶段；当前没有逐步骤 persisted AgentStep。</p>{explanations.length ? <ul>{explanations.map((item) => <li key={item.explanation_run_id}><strong>ExplanationRun {item.explanation_run_id.slice(0, 8)}</strong> · {item.status} · {item.explanation_count} 份解释</li>)}</ul> : <p>此 MatchRun 暂无 ExplanationRun。</p>}<p>RecruiterProposition 是从已保存的 Explanation / Evidence 只读重建，不会改动 MatchRun。</p></section></div>
      <details className={styles.engineering}><summary>Engineering View · 运行身份与排序快照</summary><div><p>MatchRun：<code>{run.run_id}</code></p><p>Ranking fingerprint：<code>{run.result_fingerprint ?? "未返回"}</code></p><ol>{run.results.map((result) => <li key={result.match_result_id}>#{result.result_rank} {result.candidate_id} · LTR raw {result.ltr_score_raw.toFixed(6)}</li>)}</ol></div></details>
    </>}
  </div></main></div>;
}
