"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AppSidebar } from "@/features/matching-results/app-sidebar";
import { listCompletedMatchRuns } from "@/lib/phase10-api";
import { loadTrustedRecruiterRun, primaryVerificationTarget, propositionLabel, reviewActionLabel, verificationPrompt } from "@/lib/trusted-recruiter";
import type { RecruiterProposition, StructuredRecruiterBrief, TrustedRecruiterRun } from "@/types/trusted-recruiter";
import styles from "./recruiter-view.module.css";
import shell from "@/features/matching-results/matching-results.module.css";

function sourceLabels(item: RecruiterProposition, run: TrustedRecruiterRun): string[] {
  const candidate = run.candidates[item.candidate_id];
  const requirements = [...run.job.must_have, ...run.job.nice_to_have];
  const labels: string[] = [];
  for (const ref of item.evidence_refs) {
    const parts = ref.split(":");
    if (parts[0] === "job_requirement") {
      const found = requirements.find((requirement) => requirement.requirement_id === parts.slice(1).join(":"));
      labels.push(found ? `岗位要求 · ${found.text}` : "岗位要求 · 来源已校验");
    } else if (parts[0] === "candidate") {
      const id = parts.slice(3).join(":");
      if (parts[2] === "project") {
        const project = candidate?.projects.find((entry) => entry.project_id === id);
        labels.push(project ? `候选项目 · ${project.name}` : "候选项目 · 来源已校验");
      } else if (parts[2] === "project_evidence") {
        const evidence = candidate?.project_evidence.find((entry) => entry.evidence_id === id);
        labels.push(evidence ? `项目证据 · ${evidence.statement}` : "项目证据 · 来源已校验");
      } else if (parts[2] === "skill") {
        labels.push(`技能档案 · ${item.topic_terms.join(" · ")}`);
      } else labels.push("候选档案 · 来源已校验");
    }
  }
  return [...new Set(labels)];
}

function EvidenceItem({ item, run }: { item: RecruiterProposition; run: TrustedRecruiterRun }) {
  const sources = sourceLabels(item, run);
  return <li className={styles.evidenceItem}>
    <span>{propositionLabel(item)}</span>
    <details><summary>查看依据</summary><ul>{sources.map((source) => <li key={source}>{source}</li>)}
      {item.job_requirement_refs.length > 0 && !sources.some((source) => source.startsWith("岗位要求"))
        ? item.job_requirement_refs.map((ref) => { const requirement = [...run.job.must_have, ...run.job.nice_to_have].find((entry) => ref.endsWith(`:${entry.requirement_id}`)); return <li key={ref}>{requirement ? `岗位要求 · ${requirement.text}` : "岗位要求 · 来源已校验"}</li>; }) : null}
    </ul></details>
  </li>;
}

function uniqueItems(items: RecruiterProposition[], limit: number): RecruiterProposition[] {
  const seen = new Set<string>();
  return items.filter((item) => { const label = propositionLabel(item); if (seen.has(label)) return false; seen.add(label); return true; })
    .sort((left, right) => left.topic_terms.length - right.topic_terms.length).slice(0, limit);
}

function importantUnknowns(brief: StructuredRecruiterBrief, run: TrustedRecruiterRun): RecruiterProposition[] {
  const mustHave = new Set(run.job.must_have.map((item) => item.requirement_id));
  return [...brief.unknowns].sort((left, right) => {
    const priority = (item: RecruiterProposition) => item.job_requirement_refs.some((ref) => [...mustHave].some((id) => ref.endsWith(`:${id}`))) ? 0 : 1;
    return priority(left) - priority(right);
  });
}

export function RecruiterViewScreen() {
  const [run, setRun] = useState<TrustedRecruiterRun | null>(null);
  const [recent, setRecent] = useState<Array<{ run_id: string; created_at: string }>>([]);
  const [selectedRank, setSelectedRank] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [runId, setRunId] = useState("");
  useEffect(() => {
    const requested = new URLSearchParams(window.location.search).get("runId") ?? "";
    let cancelled = false;
    Promise.resolve().then(() => { if (!cancelled) { setRunId(requested); if (requested) setBusy(true); } });
    listCompletedMatchRuns(20).then((page) => { if (!cancelled) setRecent(page.data.items); })
      .catch(() => { if (!cancelled && !requested) setError("无法读取推荐记录，请检查本地服务后重试。"); });
    if (requested) {
      loadTrustedRecruiterRun(requested).then((value) => { if (!cancelled) { setRun(value); setSelectedRank(1); } })
        .catch(() => { if (!cancelled) setError("此记录缺少完整的可信结构化结果，无法展示招聘判断。请检查运行记录或选择另一条 MatchRun。"); })
        .finally(() => { if (!cancelled) setBusy(false); });
    }
    return () => { cancelled = true; };
  }, []);

  async function openRun() {
    if (!runId.trim()) { setError("请选择一条已完成 MatchRun。"); return; }
    setBusy(true); setError(null); setRun(null);
    try {
      const loaded = await loadTrustedRecruiterRun(runId.trim());
      setRun(loaded); setSelectedRank(1);
      window.history.replaceState(null, "", `/?runId=${encodeURIComponent(runId.trim())}`);
    } catch { setError("此记录缺少完整的可信结构化结果，无法展示招聘判断。请检查运行记录或选择另一条 MatchRun。"); }
    finally { setBusy(false); }
  }

  const selected = run?.matchRun.results.find((item) => item.result_rank === selectedRank);
  const brief = run?.briefs.find((item) => item.result_rank === selectedRank);
  const unknowns = useMemo(() => brief && run ? importantUnknowns(brief, run) : [], [brief, run]);
  const primaryTarget = brief ? primaryVerificationTarget(brief, unknowns) : null;
  return <div className={shell.appShell}>
    <a className={shell.skipLink} href="#recruiter-view">跳转到候选评估</a><AppSidebar active="recruiter" />
    <main className={shell.mainSurface} id="recruiter-view"><div className={styles.frame}>
      <header className={styles.header}><div><p className={styles.eyebrow}>PEOPLEMATCH / RECRUITER VIEW</p><h1>值得继续看谁，先核实什么。</h1><p>基于已保存的排序与证据，快速筛查候选人。这里呈现的是结构化人工复核建议，不是录用决定。</p></div><span className={styles.trustBadge}>可信结构化结果</span></header>
      <section className={styles.runPicker} aria-label="选择推荐记录"><div><strong>打开已完成推荐</strong><span>只读查看；不会重新运行排序或调用模型。</span></div><select aria-label="MatchRun" value={runId} onChange={(event) => setRunId(event.target.value)}><option value="">选择 MatchRun</option>{recent.map((item) => <option key={item.run_id} value={item.run_id}>{new Date(item.created_at).toLocaleString("zh-CN")} · {item.run_id.slice(0, 8)}</option>)}</select><button type="button" disabled={busy} onClick={openRun}>查看结果</button></section>
      {busy ? <div className={styles.state} role="status">正在读取 MatchRun、证据和结构化评估…</div> : null}
      {error ? <div className={styles.error} role="alert">{error}</div> : null}
      {!run && !busy && !error ? <div className={styles.state}><strong>选择一条推荐记录</strong><p>系统会展示候选人排序、可追溯的技术信号、当前未知与下一步核实目标。</p><Link href="/workbench">或打开岗位推荐工作台</Link></div> : null}
      {run && <><section className={styles.jobHeader}><div><p className={styles.eyebrow}>TOP {run.matchRun.results.length} / 已完成 MatchRun</p><h2>{run.job.role_title}</h2><p>{run.job.company_name} · {run.job.location.cities.join(" / ") || "地点待确认"}</p></div><div className={styles.jobMeta}><span>排序来自 Hybrid Retrieval + LambdaMART</span><code>{run.matchRun.run_id.slice(0, 8)}</code></div></section>
        <div className={styles.layout}><nav className={styles.shortlist} aria-label="Top 候选人">{run.matchRun.results.map((item) => { const candidateBrief = run.briefs.find((entry) => entry.result_rank === item.result_rank); const candidate = run.candidates[item.candidate_id]; const coreUnknown = candidateBrief ? importantUnknowns(candidateBrief, run)[0] : null; return <button type="button" key={item.match_result_id} aria-pressed={selectedRank === item.result_rank} className={selectedRank === item.result_rank ? styles.activeCandidate : styles.candidate} onClick={() => setSelectedRank(item.result_rank)}><span className={styles.rank}>0{item.result_rank}</span><span className={styles.candidateMain}><strong>{candidate?.name || `候选人 ${item.candidate_id.replace("cand_", "")}`}</strong><small>{candidate?.target_roles[0] || "候选档案"}</small><span className={styles.action}>{reviewActionLabel(candidateBrief?.review_action ?? null)}</span>{coreUnknown ? <span className={styles.cardUnknown}>核心待确认 · {coreUnknown.topic_terms[0] || coreUnknown.job_requirement_terms[0]}</span> : null}</span></button>; })}</nav>
          {selected && brief ? <article className={styles.detail} aria-live="polite"><div className={styles.detailHead}><div><p className={styles.eyebrow}>#{selected.result_rank} / 人工筛查简报</p><h2>{run.candidates[selected.candidate_id]?.name || `候选人 ${selected.candidate_id.replace("cand_", "")}`}</h2><p>{run.candidates[selected.candidate_id]?.target_roles.join(" · ") || "候选方向待核实"}</p></div><span className={styles.actionLarge}>{reviewActionLabel(brief.review_action)}</span></div>
            {unknowns[0] || primaryTarget ? <div className={styles.priorityUnknown}>{unknowns[0] ? <><span>核心待确认</span><strong>{propositionLabel(unknowns[0])}</strong><small>“未知”表示当前证据不足，并不表示候选人缺少该能力。</small></> : null}{primaryTarget ? <p>下一步 · {verificationPrompt(primaryTarget)}</p> : null}</div> : null}
            <div className={styles.briefGrid}><section><p className={styles.sectionKicker}>01 / 为什么值得继续看</p><h3>岗位关联</h3><ul>{uniqueItems(brief.why_review, 2).map((item) => <EvidenceItem key={item.proposition_id} item={item} run={run} />)}{brief.why_review.length === 0 ? <li className={styles.muted}>暂无足够来源支持明确岗位关联；建议先人工筛查。</li> : null}</ul></section><section><p className={styles.sectionKicker}>02 / 真实技术信号</p><h3>材料中能看到什么</h3><ul>{uniqueItems(brief.technical_signals, 3).map((item) => <EvidenceItem key={item.proposition_id} item={item} run={run} />)}{brief.technical_signals.length === 0 ? <li className={styles.muted}>暂无可展示的结构化技术信号。</li> : null}</ul></section><section><p className={styles.sectionKicker}>03 / 风险与未知</p><h3>哪些还不能确定</h3><ul>{uniqueItems(unknowns, 3).map((item) => <EvidenceItem key={item.proposition_id} item={item} run={run} />)}{unknowns.length === 0 ? <li className={styles.muted}>此视图未记录额外未知项，仍需人工核实。</li> : null}</ul></section><section><p className={styles.sectionKicker}>04 / 补充核实目标</p><h3>后续可以追什么</h3><ul>{brief.verification_targets.filter((item) => item.proposition_id !== primaryTarget?.proposition_id).slice(0, 2).map((item) => <EvidenceItem key={item.proposition_id} item={item} run={run} />)}{brief.verification_targets.length <= (primaryTarget ? 1 : 0) ? <li className={styles.muted}>暂无额外有来源的核实目标。</li> : null}</ul></section></div>
            <details className={styles.engineering}><summary>Engineering View · 排序与来源轨迹</summary><div className={styles.engineeringBody}>
              <div className={styles.engineeringLead}><div><span>Ranking Model Raw Score：</span><strong>{selected.ltr_score_raw.toFixed(6)}</strong><small>仅用于候选相对排序；不是概率、匹配百分比或录用建议。</small></div><div><span>排序变化</span><strong>召回 #{selected.retrieval_rank} → 最终 #{selected.result_rank}</strong><small>LambdaMART 是默认最终排序责任方</small></div></div>
              <div className={styles.featureSection}><span className={styles.sectionKicker}>冻结特征 · 当前候选</span><ul>{([['技能匹配',selected.skill_fit_score],['项目证据',selected.project_evidence_score],['角色方向',selected.role_direction_score],['地点关系',selected.location_score],['资历关系',selected.seniority_score]] as const).map(([label,value]) => <li key={label}><span>{label}</span><strong>{typeof value === 'number' ? value.toFixed(3) : '未记录'}</strong></li>)}</ul></div>
              <div className={styles.engineeringTrace}><p>MatchRun <code>{run.matchRun.run_id}</code></p><p>Ranking fingerprint <code>{run.matchRun.result_fingerprint}</code></p><p>ExplanationRun <code>{run.explanationRun.explanation_run_id}</code> · Explanation #{brief.source_explanation_id}</p><p>来源下钻：结构化条目可查看项目/技能材料及岗位要求；后端执行 canonical rebuild。</p></div>
            </div></details>
          </article> : null}</div><footer className={styles.footer}>Local prototype · synthetic sandbox · 排序独立于解释。自由 Narrative 仅为需人工复核的实验性草稿，本页不依赖它。</footer></>}
    </div></main>
  </div>;
}
