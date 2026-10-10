import { AppSidebar } from "@/features/matching-results/app-sidebar";
import { frozenEvaluation } from "./frozen-evaluation";
import styles from "./evaluation.module.css";
import shell from "@/features/matching-results/matching-results.module.css";

const f = (value: number) => value.toFixed(4);

export function EvaluationScreen() {
  const ltr = frozenEvaluation.ranking.find((item) => item.id === "ltr_ranker_v1")!;
  return <div className={shell.appShell}><a className={shell.skipLink} href="#evaluation">跳转到离线评估</a><AppSidebar active="evaluation" />
    <main className={shell.mainSurface} id="evaluation"><div className={styles.frame}>
      <header className={styles.header}><p className={styles.eyebrow}>FROZEN OFFLINE EVALUATION / TEST R2</p><h1>排序策略，放在同一把尺上比较。</h1><p>同一 synthetic 测试集上的描述性离线结果。模型排序与解释质量分开评估；这里没有线上招聘效果结论。</p></header>
      <div className={styles.context}><span>48 位 synthetic 候选 · 5 个 Test 岗位 · 288 条显式标注</span><strong>Post-exposure benchmark</strong><span>Judgment coverage 25% · 未标注 ≠ 负例</span></div>
      <section className={styles.hero} aria-label="LambdaMART 测试结果"><div><p className={styles.kicker}>DEFAULT RANKING OWNER / LAMBDAMART</p><h2>冻结 Test 中，LTR 优于当前 CE 实验。</h2><p>预先声明的 Dev leader 在相同测试协议下保持领先；CE 没有成为默认最终策略。</p></div><div className={styles.heroMetrics}><div><small>NDCG@5</small><strong>{f(ltr.ndcgAt5)}</strong></div><div><small>NDCG@10</small><strong>{f(ltr.ndcgAt10)}</strong></div><div><small>MRR@10</small><strong>{f(ltr.mrrAt10)}</strong></div><div><small>Pairwise</small><strong>{f(ltr.pairwise)}</strong></div></div></section>
      <div className={styles.grid}><section className={styles.panel}><div className={styles.panelHead}><div><p className={styles.kicker}>R2 / COMMON JUDGED POOL</p><h2>排序策略对照</h2></div><span>高值更好 · 0–1</span></div><table><thead><tr><th>策略</th><th>NDCG@5</th><th>NDCG@10</th><th>MRR@10</th><th>Pairwise</th></tr></thead><tbody>{frozenEvaluation.ranking.map((row) => <tr key={row.id} className={row.id === "ltr_ranker_v1" ? styles.highlight : undefined}><td><strong>{row.label}</strong><small>{row.role}</small></td><td>{f(row.ndcgAt5)}</td><td>{f(row.ndcgAt10)}</td><td>{f(row.mrrAt10)}</td><td>{f(row.pairwise)}</td></tr>)}</tbody></table><p className={styles.panelFoot}>Judged-condensed NDCG/MRR；Pairwise 只用显式偏好。不是“匹配准确率”。</p></section>
        <section className={styles.panel}><div className={styles.panelHead}><div><p className={styles.kicker}>R1 / FULL CORPUS</p><h2>召回不是最终排序</h2></div><span>Recall@10</span></div><div className={styles.retrieval}>{frozenEvaluation.retrieval.map((row) => <div key={row.id}><div><strong>{row.label}</strong><span>{f(row.recallAt10)}</span></div><span className={styles.bar}><i style={{ width: `${row.recallAt10 * 100}%` }} /></span></div>)}</div><p className={styles.panelFoot}>在该冻结 Test 上，Sparse Recall@10 领先；没有把 Hybrid 说成每个阶段都最好。</p></section></div>
      <aside className={styles.caveat}><strong>实验边界</strong><p>Synthetic sandbox · Test 曾在早期阶段暴露（post-exposure），不是 pristine held-out 或生产评估。标注矩阵不完整；未标注候选不能当负例。Cross-Encoder 未优于 LambdaMART，因此只保留为可选实验。</p><span>Source: Phase 11 / {frozenEvaluation.runId} · report SHA-256 {frozenEvaluation.sourceSha256.slice(0, 12)}…</span></aside>
    </div></main></div>;
}
