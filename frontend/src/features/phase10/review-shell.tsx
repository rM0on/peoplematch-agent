import type { ReactNode } from "react";

import { AppSidebar } from "@/features/matching-results/app-sidebar";

import shellStyles from "@/features/matching-results/matching-results.module.css";
import styles from "./phase10.module.css";


export function ReviewShell({ children, detail = false }: { children: ReactNode; detail?: boolean }) {
  return (
    <div className={shellStyles.appShell}>
      <a className={shellStyles.skipLink} href="#bad-case-workspace">Skip to Bad Case Review</a>
      <AppSidebar active="bad-cases" />
      <main className={shellStyles.mainSurface} id="bad-case-workspace">
        <header className={shellStyles.jobBar}>
          <div><span className={shellStyles.jobBarLabel}>Quality review</span><strong>Historical matching investigations</strong><span>Sandbox / synthetic records only</span></div>
          <div className={shellStyles.jobMeta}><span>Evidence-first</span><span>Append-only audit</span><span className={shellStyles.jobContextLabel}>{detail ? "Case detail" : "Review queue"}</span></div>
        </header>
        <div className={`${shellStyles.contentFrame} ${styles.reviewPage}`}>{children}</div>
      </main>
    </div>
  );
}
