"use client";

import { CirclesThreePlusIcon } from "@phosphor-icons/react/dist/csr/CirclesThreePlus";
import { FolderOpenIcon } from "@phosphor-icons/react/dist/csr/FolderOpen";
import { SparkleIcon } from "@phosphor-icons/react/dist/csr/Sparkle";
import { TargetIcon } from "@phosphor-icons/react/dist/csr/Target";
import { WarningCircleIcon } from "@phosphor-icons/react/dist/csr/WarningCircle";
import Link from "next/link";

import styles from "./matching-results.module.css";

export function AppSidebar({ active = "matching" }: { active?: "matching" | "bad-cases" }) {
  return (
    <aside className={styles.sidebar} aria-label="Primary navigation">
      <Link className={styles.brand} href="/" aria-label="PeopleMatch Agent home">
        <span className={styles.brandMark} aria-hidden="true">
          <SparkleIcon size={18} weight="fill" />
        </span>
        <span>
          <strong>PeopleMatch</strong>
          <small>Agent</small>
        </span>
      </Link>

      <nav className={styles.sidebarNav}>
        <div className={styles.navGroup}>
          <p className={styles.navLabel}>推荐与复核</p>
          <Link className={`${styles.navItem} ${active === "matching" ? styles.navItemActive : ""}`} href="/">
            <TargetIcon size={17} weight="bold" />
            <span>推荐工作台</span>
          </Link>
          <Link className={`${styles.navItem} ${active === "bad-cases" ? styles.navItemActive : ""}`} href="/bad-cases">
            <WarningCircleIcon size={17} />
            <span>Bad Case 复核</span>
          </Link>
        </div>
      </nav>

      <div className={styles.sidebarFooter}>
        <div className={styles.mockBadge}>
          <CirclesThreePlusIcon size={16} weight="bold" />
          <span>Local Prototype</span>
        </div>
        <p>Synthetic demo · Evidence first</p>
        <Link href={active === "matching" ? "#matching-results" : "/#matching-results"}>
          <FolderOpenIcon size={15} />
          定位推荐结果
        </Link>
      </div>
    </aside>
  );
}
