"use client";

import { BriefcaseIcon } from "@phosphor-icons/react/dist/csr/Briefcase";
import { ChartBarIcon } from "@phosphor-icons/react/dist/csr/ChartBar";
import { CirclesThreePlusIcon } from "@phosphor-icons/react/dist/csr/CirclesThreePlus";
import { FolderOpenIcon } from "@phosphor-icons/react/dist/csr/FolderOpen";
import { GitBranchIcon } from "@phosphor-icons/react/dist/csr/GitBranch";
import { ListChecksIcon } from "@phosphor-icons/react/dist/csr/ListChecks";
import { SparkleIcon } from "@phosphor-icons/react/dist/csr/Sparkle";
import { TargetIcon } from "@phosphor-icons/react/dist/csr/Target";
import { UsersThreeIcon } from "@phosphor-icons/react/dist/csr/UsersThree";
import { WarningCircleIcon } from "@phosphor-icons/react/dist/csr/WarningCircle";
import Link from "next/link";

import styles from "./matching-results.module.css";


const plannedNavigation = [
  { label: "Overview", icon: ChartBarIcon },
  { label: "Candidates", icon: UsersThreeIcon },
  { label: "Jobs", icon: BriefcaseIcon },
];

const reviewNavigation = [
  { label: "Runs", icon: GitBranchIcon, href: null },
  { label: "Bad Cases", icon: WarningCircleIcon, href: "/bad-cases" },
  { label: "Evaluation", icon: ListChecksIcon, href: null },
];

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
          <p className={styles.navLabel}>Workspace</p>
          {plannedNavigation.map(({ label, icon: Icon }) => (
            <button className={styles.navItem} key={label} type="button" disabled>
              <Icon size={17} />
              <span>{label}</span>
            </button>
          ))}
        </div>

        <div className={styles.navGroup}>
          <p className={styles.navLabel}>Decisioning</p>
          <Link className={`${styles.navItem} ${active === "matching" ? styles.navItemActive : ""}`} href="/">
            <TargetIcon size={17} weight="bold" />
            <span>Matching</span>
          </Link>
          {reviewNavigation.map(({ label, icon: Icon, href }) => href ? (
            <Link className={`${styles.navItem} ${active === "bad-cases" ? styles.navItemActive : ""}`} href={href} key={label}>
              <Icon size={17} />
              <span>{label}</span>
            </Link>
          ) : (
            <button className={styles.navItem} key={label} type="button" disabled><Icon size={17} /><span>{label}</span></button>
          ))}
        </div>
      </nav>

      <div className={styles.sidebarFooter}>
        <div className={styles.mockBadge}>
          <CirclesThreePlusIcon size={16} weight="bold" />
          <span>Design Mock</span>
        </div>
        <p>Illustrative data only</p>
        <Link href={active === "matching" ? "#project-evidence" : "/#project-evidence"}>
          <FolderOpenIcon size={15} />
          Evidence view
        </Link>
      </div>
    </aside>
  );
}
