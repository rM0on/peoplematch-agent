import { ArrowRightIcon } from "@phosphor-icons/react/dist/csr/ArrowRight";
import { CaretDownIcon } from "@phosphor-icons/react/dist/csr/CaretDown";
import { CheckCircleIcon } from "@phosphor-icons/react/dist/csr/CheckCircle";
import { CircleIcon } from "@phosphor-icons/react/dist/csr/Circle";
import { GitBranchIcon } from "@phosphor-icons/react/dist/csr/GitBranch";
import { InfoIcon } from "@phosphor-icons/react/dist/csr/Info";
import { MapPinIcon } from "@phosphor-icons/react/dist/csr/MapPin";
import { MinusCircleIcon } from "@phosphor-icons/react/dist/csr/MinusCircle";
import { ShieldCheckIcon } from "@phosphor-icons/react/dist/csr/ShieldCheck";
import { WarningCircleIcon } from "@phosphor-icons/react/dist/csr/WarningCircle";

import type { CandidateMatch, EvidenceLevel } from "./types";
import styles from "./matching-results.module.css";


type RankingDetailProps = {
  candidate: CandidateMatch;
  comparisonCandidate: CandidateMatch;
  comparisonOpen: boolean;
  onComparisonToggle: () => void;
  onReview: () => void;
};

const evidenceCopy: Record<EvidenceLevel, string> = {
  demonstrated: "Demonstrated",
  partial: "Partial",
  "claim-only": "Claim only",
};

function EvidenceStatusIcon({ level }: { level: EvidenceLevel }) {
  if (level === "demonstrated") {
    return <CheckCircleIcon size={15} weight="fill" />;
  }

  if (level === "partial") {
    return <MinusCircleIcon size={15} weight="fill" />;
  }

  return <WarningCircleIcon size={15} weight="fill" />;
}

function FeatureIndicator({ label, value }: { label: string; value: number }) {
  return (
    <div className={styles.featureIndicator} title={`${label}: ${value} — illustrative design value`}>
      <span>
        <small>{label}</small>
        <strong>{value}</strong>
      </span>
      <span className={styles.featureTrack} aria-hidden="true">
        <span style={{ width: `${value}%` }} />
      </span>
    </div>
  );
}

export function RankingDetail({
  candidate,
  comparisonCandidate,
  comparisonOpen,
  onComparisonToggle,
  onReview,
}: RankingDetailProps) {
  const higherRankedCandidate =
    candidate.rank < comparisonCandidate.rank ? candidate : comparisonCandidate;
  const lowerRankedCandidate =
    candidate.rank < comparisonCandidate.rank ? comparisonCandidate : candidate;

  return (
    <article className={styles.rankingDetail} aria-live="polite">
      <header className={styles.detailHeader}>
        <div>
          <p className={styles.eyebrow}>Rank #{candidate.rank} · selected</p>
          <h2>{candidate.label}</h2>
          <p className={styles.detailRole}>
            {candidate.role}
            <span aria-hidden="true">·</span>
            <MapPinIcon size={14} />
            {candidate.location}
          </p>
        </div>
        <div className={styles.overallScore} aria-label={`Illustrative final match score ${candidate.score}`}>
          <span className={`${styles.overallScoreValue} overall-score__value`}>{candidate.score}</span>
          <small>Final score</small>
        </div>
      </header>

      <section className={styles.whySection} aria-labelledby="why-rank-title">
        <div className={styles.sectionHeadingRow}>
          <div>
            <p className={styles.eyebrow}>Decision overview</p>
            <h3 id="why-rank-title">Why this rank</h3>
          </div>
          <span className={`${styles.riskBadge} ${styles[`risk-${candidate.risk.level}`]}`}>
            <ShieldCheckIcon size={15} />
            {candidate.risk.label}
          </span>
        </div>

        <p className={styles.primaryReason}>{candidate.primaryReason}</p>

        <div className={styles.featureOverview} aria-label="Illustrative feature score overview">
          {candidate.features.map((feature) => (
            <FeatureIndicator key={feature.label} label={feature.label} value={feature.value} />
          ))}
        </div>

        <div className={styles.decisionMetaGrid}>
          <div>
            <span>Evidence state</span>
            <strong className={`${styles.evidenceState} ${styles[`evidence-${candidate.evidenceStrength}`]}`}>
              <EvidenceStatusIcon level={candidate.evidenceStrength} />
              {evidenceCopy[candidate.evidenceStrength]}
            </strong>
          </div>
          <div>
            <span>Missing must-have</span>
            <strong className={styles.missingRequirement}>
              <WarningCircleIcon size={15} />
              {candidate.missingMustHaves[0] ?? "None identified"}
            </strong>
          </div>
        </div>

        <div className={styles.comparisonPanel}>
          <button
            type="button"
            className={styles.comparisonTrigger}
            aria-expanded={comparisonOpen}
            aria-controls="adjacent-rank-comparison"
            onClick={onComparisonToggle}
          >
            <span>
              <GitBranchIcon size={16} />
              Why {higherRankedCandidate.label} ranks above {lowerRankedCandidate.label}
            </span>
            <CaretDownIcon
              className={comparisonOpen ? styles.caretOpen : ""}
              size={15}
              weight="bold"
            />
          </button>
          {comparisonOpen ? (
            <div className={styles.comparisonBody} id="adjacent-rank-comparison">
              <p>{candidate.comparison.summary}</p>
              <ul>
                {candidate.comparison.advantages.map((advantage) => (
                  <li key={advantage}>{advantage}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      </section>

      <section className={styles.evidenceSection} id="project-evidence" aria-labelledby="evidence-title">
        <div className={styles.sectionHeadingRow}>
          <div>
            <p className={styles.eyebrow}>Skill → artifact trace</p>
            <h3 id="evidence-title">Project evidence</h3>
          </div>
          <div className={styles.evidenceLegend} aria-label="Evidence state legend">
            <span className={styles["evidence-demonstrated"]}>
              <CircleIcon size={8} weight="fill" />
              Demonstrated
            </span>
            <span className={styles["evidence-partial"]}>
              <CircleIcon size={8} weight="fill" />
              Partial
            </span>
            <span className={styles["evidence-claim-only"]}>
              <CircleIcon size={8} weight="fill" />
              Claim only
            </span>
          </div>
        </div>

        <div className={styles.evidenceList}>
          {candidate.projects.map((project) => (
            <div className={styles.evidenceRow} key={project.title}>
              <div className={`${styles.evidenceMarker} ${styles[`evidence-${project.level}`]}`}>
                <EvidenceStatusIcon level={project.level} />
              </div>
              <div className={styles.evidenceContent}>
                <div className={styles.evidenceTopline}>
                  <strong>{project.title}</strong>
                  <span className={`${styles.evidencePill} ${styles[`evidence-${project.level}`]}`}>
                    {evidenceCopy[project.level]}
                  </span>
                </div>
                <p>{project.summary}</p>
                <div className={styles.skillList} aria-label={`${project.title} supported skills`}>
                  {project.skills.map((skill) => (
                    <span key={skill}>{skill}</span>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      <div className={styles.bottomGrid}>
        <section className={styles.traceSection} id="decision-trace" aria-labelledby="trace-title">
          <div className={styles.traceTitle}>
            <GitBranchIcon size={17} />
            <div>
              <p className={styles.eyebrow}>Decision trace</p>
              <h3 id="trace-title">Rerank impact</h3>
            </div>
          </div>
          <p>{candidate.rerankImpact}</p>
          <div className={styles.traceRoute} aria-label="Illustrative rerank transition">
            <span>Retrieved #{candidate.retrievedRank}</span>
            <ArrowRightIcon size={14} />
            <strong>Final #{candidate.rank}</strong>
          </div>
        </section>

        <section className={styles.explanationSection} aria-labelledby="explanation-title">
          <div className={styles.explanationTitle}>
            <InfoIcon size={18} weight="fill" />
            <div>
              <p className={styles.eyebrow}>Evidence-bounded narrative</p>
              <h3 id="explanation-title">Grounded explanation</h3>
            </div>
          </div>
          <p>{candidate.explanation}</p>
          <p className={styles.interviewFocus}>
            <strong>Interview focus:</strong> {candidate.interviewFocus}
          </p>
        </section>
      </div>

      <footer className={styles.detailActions}>
        <button className={styles.secondaryAction} type="button" onClick={onReview}>
          Review persisted history
        </button>
        <a className={styles.secondaryAction} href="#decision-trace">
          Open decision trace
        </a>
        <a className={styles.primaryAction} href="#project-evidence">
          Inspect project evidence
          <ArrowRightIcon size={16} weight="bold" />
        </a>
      </footer>
    </article>
  );
}
