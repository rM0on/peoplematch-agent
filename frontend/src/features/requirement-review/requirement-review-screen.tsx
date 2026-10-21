"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { AppSidebar } from "@/features/matching-results/app-sidebar";
import { loadTrustedRecruiterRun, propositionLabel } from "@/lib/trusted-recruiter";
import { assertRequirementReviewOwnership, loadRequirementReview } from "@/lib/requirement-review";
import type { RequirementReview, RequirementReviewRow } from "@/types/requirement-review";
import type { TrustedRecruiterRun } from "@/types/trusted-recruiter";
import shell from "@/features/matching-results/matching-results.module.css";
import styles from "./requirement-review.module.css";

function evidenceLabel(ref: string, review: RequirementReview): string {
  if (ref.startsWith("job_requirement:")) {
    const id = ref.slice("job_requirement:".length);
    const requirement = review.requirements.find((item) => item.requirement_id === id);
    return requirement ? `岗位原文 · ${requirement.text}` : `岗位要求 ID · ${id}`;
  }
  const parts = ref.split(":");
  if (parts[0] === "candidate" && parts[1] === String(review.result_rank))
    return review.source_descriptors.find((item) => item.evidence_ref === ref)?.description ?? `历史候选材料来源 · ${ref}`;
  return `来源标识 · ${ref}`;
}
const diagnosticLabel: Record<RequirementReviewRow["diagnostic_status"], string> = {
  matched: "已有特征关联", partial: "关联较弱", missing: "未建立关联", not_assessed: "尚未评估",
};
const evidenceStatusLabel: Record<RequirementReviewRow["evidence_status"], string> = {
  available: "已有材料线索", claim_only: "仅有档案声明", absent: "当前无材料关联", not_assessed: "来源待核实",
};

export function RequirementReviewScreen() {
  const params = useSearchParams();
  const runId = params.get("runId")?.trim() ?? "";
  const explanationId = Number(params.get("explanationId"));
  const valid = !!runId && Number.isSafeInteger(explanationId) && explanationId > 0;
  const requestKey = `${runId}:${explanationId}`;
  const [value, setValue] = useState<{ key: string; review: RequirementReview; run: TrustedRecruiterRun } | null>(null);
  const [failedKey, setFailedKey] = useState<string | null>(null);
  useEffect(() => {
    if (!valid) return;
    let cancelled = false;
    loadRequirementReview(explanationId)
      .then(async (review) => ({ review, run: await loadTrustedRecruiterRun(runId, review.explanation_run_id) }))
      .then(({ run, review }) => { if (!cancelled) { setValue({ key: requestKey, run, review: assertRequirementReviewOwnership(review, run) }); setFailedKey(null); } })
      .catch(() => { if (!cancelled) setFailedKey(requestKey); });
    return () => { cancelled = true; };
  }, [runId, explanationId, valid, requestKey]);
  const current = value?.key === requestKey ? value : null;
  const run = current?.run, review = current?.review;
  const state = !valid || failedKey === requestKey ? "error" : current ? "ready" : "loading";
  const candidateName = review && run ? run.candidates[review.candidate_id]?.name || `候选人 ${review.candidate_id}` : "";
  return <div className={shell.appShell}><a className={shell.skipLink} href="#requirements">跳转到核心要求</a><AppSidebar active="recruiter" />
    <main className={shell.mainSurface} id="requirements"><div className={styles.frame}>
      <header className={styles.hero}><div className={styles.heroTop}><Link href={review ? `/?runId=${encodeURIComponent(review.match_run_id)}` : "/"}>← 返回招聘筛查</Link><span>PEOPLEMATCH / REQUIREMENT REVIEW</span></div>
        <p className={styles.eyebrow}>SOURCE-BACKED HUMAN REVIEW</p><h1>逐项核实岗位核心要求。</h1><p className={styles.heroLead}>把岗位要求、候选材料关联与下一步核实放在同一张工作台。未知不等于缺少能力；这不是新的排名或录用判断。</p></header>
      {state === "loading" && <div className={styles.state} role="status">正在核对 MatchRun、解释来源与岗位要求…</div>}
      {state === "error" && <div className={styles.state} role="alert">无法建立可信的要求核实视图。请从已完成的招聘筛查记录重新进入。</div>}
      {state === "ready" && review && run && <>
        <section className={styles.summary}><div><span className={styles.eyebrow}>CURRENT PROFILE NAME / HISTORICAL RANK {String(review.result_rank).padStart(2,"0")}</span><h2>{candidateName}</h2><p>{review.role_title} · {review.requirements.length} 项岗位要求逐项查看</p></div><div className={styles.summaryNote}>要求与来源来自已保存的 Explanation / Evidence Bundle<br/><small>档案显示名可能更新 · 只读 · 不改变排序</small></div></section>
        <div className={styles.columns}><div className={styles.requirements}>
          {(["must_have", "nice_to_have"] as const).map((priority) => {
            const rows = review.requirements.filter((item) => item.priority === priority);
            return rows.length ? <section key={priority} aria-label={priority === "must_have" ? "核心要求" : "加分要求"}>
              <div className={styles.sectionHead}><span>{priority === "must_have" ? "01 / MUST-HAVE" : "02 / NICE-TO-HAVE"}</span><h2>{priority === "must_have" ? "核心要求" : "加分要求"}</h2><small>{rows.length} 项</small></div>
              <div className={styles.rowList}>{rows.map((item) => <article className={styles.row} key={item.requirement_id}>
                <div className={styles.rowTitle}><strong>{item.text}</strong><span>{evidenceStatusLabel[item.evidence_status]}</span></div>
                <div className={styles.rowMeta}><span>{diagnosticLabel[item.diagnostic_status]}</span><code>{item.requirement_id}</code></div>
                {item.propositions.length ? <div className={styles.propositions}>{item.propositions.map((proposition) => <div key={proposition.proposition_id} className={styles.proposition}>
                  <p>{propositionLabel(proposition)}</p><details><summary>查看来源元数据</summary><ul>{proposition.evidence_refs.map((ref) => <li key={ref}>{evidenceLabel(ref, review)}<br/><code>{ref}</code></li>)}</ul></details>
                </div>)}</div> : <p className={styles.noEvidence}>{item.evidence_status === "available" || item.evidence_status === "claim_only"
                  ? "诊断显示材料线索，但当前精选解释没有可下钻的单项命题；请核对原始材料。"
                  : "当前精选解释没有针对该要求的单项来源；请人工继续核实。"}</p>}
              </article>)}</div></section> : null;
          })}
        </div><aside className={styles.guide}><span>HOW TO READ</span><h2>有来源，才谈判断。</h2><p>诊断状态与精选解释是两条不同的线索：诊断可能发现材料关联，却未被选入本次解释。这里展示历史 Evidence Bundle 元数据，并非原始文档。任何线索都不等于技能已证实。</p><div><strong>跨要求线索</strong><p>以下命题同时指向多个要求，不作为任何单项要求的证明。</p>{review.cross_requirement_propositions.map((item) => <article key={item.proposition_id} className={styles.aggregate}><p>{propositionLabel(item)}</p><p>{item.job_requirement_refs.join(" · ")}</p><details><summary>查看跨要求来源元数据</summary><ul>{item.evidence_refs.map((ref) => <li key={ref}>{evidenceLabel(ref, review)}<br/><code>{ref}</code></li>)}</ul></details></article>)}</div><div><strong>人工复核路径</strong><ol><li>查看历史来源元数据，确认材料与要求的关联</li><li>对 Unknown 提出定向核实问题</li><li>保留未证实事项，不升级为招聘结论</li></ol></div><small>Source · Explanation #{review.source_explanation_id} / Ranking fingerprint {review.ranking_fingerprint.slice(0,12)}…</small></aside></div>
        <footer className={styles.footer}>Local synthetic prototype · Read-only projection of canonical persisted sources · Qwen 不负责排序，本页不调用 Provider。</footer>
      </>}
    </div></main>
  </div>;
}
