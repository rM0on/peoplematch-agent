"use client";

import { AppSidebar } from "@/features/matching-results/app-sidebar";
import { HistoricalFeedbackEntry } from "@/features/phase10/historical-feedback-entry";

import styles from "@/features/matching-results/matching-results.module.css";


export function RecommendationHistoryScreen() {
  return (
    <div className={styles.appShell}>
      <a className={styles.skipLink} href="#recommendation-history">跳转到推荐记录</a>
      <AppSidebar active="runs" />
      <main className={styles.mainSurface} id="recommendation-history">
        <header className={styles.jobBar}>
          <div>
            <span className={styles.jobBarLabel}>推荐历史</span>
            <strong>已完成 MatchRun</strong>
            <span>基于不可变快照复核排序与 Evidence</span>
          </div>
          <div className={styles.jobMeta}>
            <span>Historical trace</span>
            <span className={styles.jobContextLabel}>推荐记录</span>
          </div>
        </header>
        <div className={styles.contentFrame}>
          <section className={styles.hero}>
            <div>
              <p className={styles.eyebrow}>HISTORICAL MATCHRUN REVIEW</p>
              <h1>推荐记录</h1>
              <p>查看已完成 MatchRun 的排序结果、证据解释与人工反馈；历史记录只读，复核不会改变原始候选顺序或模型分值。</p>
            </div>
          </section>
          <HistoricalFeedbackEntry />
        </div>
      </main>
    </div>
  );
}
