import type { ReactNode } from "react";

import { AppSidebar } from "@/features/matching-results/app-sidebar";

import shellStyles from "@/features/matching-results/matching-results.module.css";
import styles from "./phase10.module.css";


export function ReviewShell({ children, detail = false }: { children: ReactNode; detail?: boolean }) {
  return (
    <div className={shellStyles.appShell}>
      <a className={shellStyles.skipLink} href="#bad-case-workspace">跳转到 Bad Case 复核</a>
      <AppSidebar active="bad-cases" />
      <main className={shellStyles.mainSurface} id="bad-case-workspace">
        <header className={shellStyles.jobBar}>
          <div><span className={shellStyles.jobBarLabel}>质量复核</span><strong>历史匹配问题调查</strong><span>仅限 sandbox / synthetic 记录</span></div>
          <div className={shellStyles.jobMeta}><span>Evidence-first</span><span>追加式审计</span><span className={shellStyles.jobContextLabel}>{detail ? "Bad Case 详情" : "复核队列"}</span></div>
        </header>
        <div className={`${shellStyles.contentFrame} ${styles.reviewPage}`}>{children}</div>
      </main>
    </div>
  );
}
