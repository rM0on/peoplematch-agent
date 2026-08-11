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

import styles from "./matching-results.module.css";


const plannedNavigation = [
  { label: "Overview", icon: ChartBarIcon },
  { label: "Candidates", icon: UsersThreeIcon },
  { label: "Jobs", icon: BriefcaseIcon },
];

const reviewNavigation = [
  { label: "Runs", icon: GitBranchIcon },
  { label: "Bad Cases", icon: WarningCircleIcon },
  { label: "Evaluation", icon: ListChecksIcon },
];

export function AppSidebar() {
  return (
    <aside className={styles.sidebar} aria-label="Primary navigation">
      <a className={styles.brand} href="#matching-results" aria-label="PeopleMatch Agent home">
        <span className={styles.brandMark} aria-hidden="true">
          <SparkleIcon size={18} weight="fill" />
        </span>
        <span>
          <strong>PeopleMatch</strong>
          <small>Agent</small>
        </span>
      </a>

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
          <a className={`${styles.navItem} ${styles.navItemActive}`} href="#matching-results">
            <TargetIcon size={17} weight="bold" />
            <span>Matching</span>
          </a>
          {reviewNavigation.map(({ label, icon: Icon }) => (
            <button className={styles.navItem} key={label} type="button" disabled>
              <Icon size={17} />
              <span>{label}</span>
            </button>
          ))}
        </div>
      </nav>

      <div className={styles.sidebarFooter}>
        <div className={styles.mockBadge}>
          <CirclesThreePlusIcon size={16} weight="bold" />
          <span>Design Mock</span>
        </div>
        <p>Illustrative data only</p>
        <a href="#project-evidence">
          <FolderOpenIcon size={15} />
          Evidence view
        </a>
      </div>
    </aside>
  );
}
