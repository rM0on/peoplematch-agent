import { CheckCircleIcon } from "@phosphor-icons/react/dist/csr/CheckCircle";

import type { PipelineStage } from "./types";
import styles from "./matching-results.module.css";


type PipelineStripProps = {
  stages: PipelineStage[];
  activeStageId: PipelineStage["id"];
  onStageSelect: (stageId: PipelineStage["id"]) => void;
};

export function PipelineStrip({ stages, activeStageId, onStageSelect }: PipelineStripProps) {
  return (
    <section className={styles.pipelinePanel} aria-label="Matching pipeline stages">
      <div className={styles.pipelineTrack}>
        {stages.map((stage, index) => {
          const isActive = stage.id === activeStageId;

          return (
            <div className={styles.pipelineStepWrap} key={stage.id}>
              <button
                className={`${styles.pipelineStep} ${isActive ? styles.pipelineStepActive : ""}`}
                type="button"
                aria-pressed={isActive}
                onClick={() => onStageSelect(stage.id)}
              >
                <CheckCircleIcon size={15} weight={isActive ? "fill" : "regular"} />
                <span>{stage.label}</span>
              </button>
              {index < stages.length - 1 ? <span className={styles.pipelineConnector} /> : null}
            </div>
          );
        })}
      </div>
      <p className={styles.pipelineDetail}>{stages.find((stage) => stage.id === activeStageId)?.detail}</p>
    </section>
  );
}
