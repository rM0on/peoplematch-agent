import { CaretRightIcon } from "@phosphor-icons/react/dist/csr/CaretRight";
import { CheckCircleIcon } from "@phosphor-icons/react/dist/csr/CheckCircle";
import { MapPinIcon } from "@phosphor-icons/react/dist/csr/MapPin";
import { MinusCircleIcon } from "@phosphor-icons/react/dist/csr/MinusCircle";
import { WarningCircleIcon } from "@phosphor-icons/react/dist/csr/WarningCircle";

import type { CandidateMatch, EvidenceLevel } from "./types";
import styles from "./matching-results.module.css";


type CandidateShortlistProps = {
  candidates: CandidateMatch[];
  selectedCandidateId: string;
  onSelect: (candidateId: string) => void;
};

const evidenceCopy: Record<EvidenceLevel, string> = {
  demonstrated: "Demonstrated",
  partial: "Partial",
  "claim-only": "Claim only",
};

function EvidenceIcon({ level }: { level: EvidenceLevel }) {
  if (level === "demonstrated") {
    return <CheckCircleIcon size={14} weight="fill" />;
  }

  if (level === "partial") {
    return <MinusCircleIcon size={14} weight="fill" />;
  }

  return <WarningCircleIcon size={14} weight="fill" />;
}

export function CandidateShortlist({
  candidates,
  selectedCandidateId,
  onSelect,
}: CandidateShortlistProps) {
  return (
    <section className={styles.shortlist} id="shortlist" aria-labelledby="shortlist-title">
      <div className={styles.shortlistHeader}>
        <div>
          <p className={styles.eyebrow}>Top K ranking</p>
          <h2 id="shortlist-title">Shortlist</h2>
        </div>
        <span>{candidates.length} matches</span>
      </div>

      <div className={styles.candidateList}>
        {candidates.map((candidate) => {
          const isSelected = candidate.id === selectedCandidateId;

          return (
            <button
              className={`${styles.candidateRow} ${isSelected ? styles.candidateRowSelected : ""}`}
              key={candidate.id}
              type="button"
              aria-label={`Select ${candidate.label}`}
              aria-pressed={isSelected}
              onClick={() => onSelect(candidate.id)}
            >
              <span className={styles.rankNumber}>#{candidate.rank}</span>
              <span className={styles.candidateBody}>
                <span className={styles.candidateTopline}>
                  <span>
                    <strong>{candidate.label}</strong>
                    <small>{candidate.role}</small>
                  </span>
                  <span className={styles.shortlistScore}>{candidate.score}</span>
                </span>
                <span className={styles.candidateLocation}>
                  <MapPinIcon size={13} />
                  {candidate.location}
                </span>
                <span className={styles.candidateReason}>{candidate.primaryReason}</span>

                {isSelected ? (
                  <span className={styles.miniFeatureGrid} aria-label="Selected candidate score overview">
                    {candidate.features.map((feature) => (
                      <span key={feature.label}>
                        <small>{feature.shortLabel}</small>
                        <strong>{feature.value}</strong>
                      </span>
                    ))}
                  </span>
                ) : null}

                <span className={styles.candidateMeta}>
                  <span className={`${styles.evidenceState} ${styles[`evidence-${candidate.evidenceStrength}`]}`}>
                    <EvidenceIcon level={candidate.evidenceStrength} />
                    {evidenceCopy[candidate.evidenceStrength]}
                  </span>
                  <span className={`${styles.riskInline} ${styles[`risk-${candidate.risk.level}`]}`}>
                    {candidate.risk.level} risk
                  </span>
                  <CaretRightIcon className={styles.rowCaret} size={15} weight="bold" />
                </span>
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
