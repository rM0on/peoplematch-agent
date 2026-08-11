export type EvidenceLevel = "demonstrated" | "partial" | "claim-only";
export type RiskLevel = "low" | "medium" | "high";

export type FeatureScore = {
  label: string;
  shortLabel: string;
  value: number;
};

export type ProjectEvidence = {
  title: string;
  summary: string;
  level: EvidenceLevel;
  skills: string[];
};

export type RankComparison = {
  candidateId: string;
  summary: string;
  advantages: string[];
};

export type CandidateMatch = {
  id: string;
  label: string;
  rank: number;
  score: number;
  role: string;
  location: string;
  primaryReason: string;
  features: FeatureScore[];
  evidenceStrength: EvidenceLevel;
  risk: {
    level: RiskLevel;
    label: string;
  };
  missingMustHaves: string[];
  projects: ProjectEvidence[];
  explanation: string;
  interviewFocus: string;
  retrievedRank: number;
  rerankImpact: string;
  comparison: RankComparison;
};

export type PipelineStage = {
  id: "parse" | "retrieval" | "features" | "ltr" | "rerank" | "explain";
  label: string;
  detail: string;
};
