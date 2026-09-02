"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";

import { listBadCases, Phase10ApiError } from "@/lib/phase10-api";
import type { BadCaseSummary } from "@/types/phase10";

import styles from "./phase10.module.css";


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
    <div className={styles.caseList}>{items.map((item) => <Link className={styles.caseRow} href={`/bad-cases/${encodeURIComponent(item.bad_case_id)}`} key={item.bad_case_id} aria-label={`${item.symptom_code.replaceAll("_", " ")} · ${item.status}`}>
      <span><strong>{item.symptom_code.replaceAll("_", " ")}</strong><small>MatchRun {item.primary_match_run_id}</small></span>
      <span><span className={styles.badge}>{item.status}</span><small>修订 {item.revision}</small></span>
      <span><span className={styles.severity}>{item.severity}</span><small>{item.symptom_family}</small></span>
      <span aria-hidden="true">→</span>
    </Link>)}</div>
    <div className={styles.formActions}><button className={styles.secondaryButton} type="button" disabled={offset === 0} onClick={() => { setItems(null); setError(null); setOffset(Math.max(0, offset - limit)); }}>上一页</button><button className={styles.secondaryButton} type="button" disabled={offset + limit >= total} onClick={() => { setItems(null); setError(null); setOffset(offset + limit); }}>下一页</button></div>
  </section>;
}
