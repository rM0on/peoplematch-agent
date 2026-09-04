"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";

import { listBadCases, Phase10ApiError } from "@/lib/phase10-api";
import type { BadCaseSummary } from "@/types/phase10";

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
const statusLabels: Record<string, string> = {
  CREATED: "待复核", REVIEWED: "已复核", ROOT_CAUSE_IDENTIFIED: "已识别根因",
  ACTION_PLANNED: "已规划行动", RESOLVED: "已处理", VERIFIED: "已核验",
  DISMISSED: "已驳回", DUPLICATE: "重复记录",
};
const severityLabels: Record<string, string> = { LOW: "低", MEDIUM: "中", HIGH: "高", CRITICAL: "严重" };
const familyLabels: Record<string, string> = {
  RANKING: "排序", RETRIEVAL: "召回", FEATURE: "特征", EXPLANATION: "解释",
  PROFILE_DATA: "资料数据", INTEGRITY: "完整性",
};

export function BadCaseListScreen() {
  const [items, setItems] = useState<BadCaseSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const requestSequence = useRef(0);
  const limit = 20;

  async function retry() {
    const sequence = ++requestSequence.current;
    setItems(null);
    setError(null);
    try {
      const response = await listBadCases({ limit, offset });
      if (requestSequence.current === sequence) {
        setItems(response.data.items);
        setTotal(response.data.total);
      }
    } catch (caught) {
      if (requestSequence.current === sequence) {
      setError(caught instanceof Phase10ApiError ? caught.message : "Bad Case 列表暂不可用");
      }
    }
  }

  useEffect(() => {
    let active = true;
    listBadCases({ limit, offset }).then((response) => {
      if (active) { setItems(response.data.items); setTotal(response.data.total); }
    }).catch((caught) => {
      if (active) setError(caught instanceof Phase10ApiError ? caught.message : "Bad Case 列表暂不可用");
    });
    return () => { active = false; requestSequence.current += 1; };
  }, [offset]);

  if (error) return <section className={styles.error} role="alert"><strong>Bad Case 复核暂不可用</strong><br />{error}<div className={styles.formActions}><button className={styles.secondaryButton} type="button" onClick={() => void retry()}>重新尝试</button></div></section>;
  if (items === null) return <section className={styles.loading} aria-label="正在加载 Bad Case"><div className={styles.skeleton} /></section>;
  if (items.length === 0) return <section className={styles.empty}><div><h2>暂无 Bad Case 记录</h2><p>结构化反馈与 Bad Case 保持分离，只有复核人员显式创建后才会进入调查队列。</p></div></section>;

  return <section aria-labelledby="bad-case-list-title">
    <div className={styles.listHeader}><div><p className={styles.eyebrow}>AI 匹配质量调查</p><h1 id="bad-case-list-title">Bad Case 复核</h1><p className={styles.muted}>检查不可变观察、历史 Evidence 与可审计复核进度。</p></div><span className={styles.badge}>{total} 条记录</span></div>
    <div className={styles.caseList}>{items.map((item) => { const symptom = symptomLabels[item.symptom_code] ?? "待分类匹配问题"; return <Link className={styles.caseRow} href={`/bad-cases/${encodeURIComponent(item.bad_case_id)}`} key={item.bad_case_id} aria-label={`${symptom} · ${statusLabels[item.status] ?? item.status}`}>
      <span><strong>{symptom}</strong><small>MatchRun {item.primary_match_run_id}</small></span>
      <span><span className={styles.badge}>{statusLabels[item.status] ?? item.status}</span><small>修订 {item.revision}</small></span>
      <span><span className={styles.severity}>{severityLabels[item.severity] ?? item.severity}</span><small>{familyLabels[item.symptom_family] ?? item.symptom_family}</small></span>
      <span aria-hidden="true">→</span>
    </Link>; })}</div>
    <div className={styles.formActions}><button className={styles.secondaryButton} type="button" disabled={offset === 0} onClick={() => { setItems(null); setError(null); setOffset(Math.max(0, offset - limit)); }}>上一页</button><button className={styles.secondaryButton} type="button" disabled={offset + limit >= total} onClick={() => { setItems(null); setError(null); setOffset(offset + limit); }}>下一页</button></div>
  </section>;
}
