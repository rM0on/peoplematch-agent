import type { CandidateMatch, PipelineStage } from "./types";


export const pipelineStages: PipelineStage[] = [
  {
    id: "parse",
    label: "Parse",
    detail: "Structured candidate and job signals prepared for the design mock.",
  },
  {
    id: "retrieval",
    label: "Retrieval",
    detail: "Dense and sparse retrieval stages contribute the initial shortlist.",
  },
  {
    id: "features",
    label: "Features",
    detail: "Evidence, role direction, constraints, and fit signals are separated.",
  },
  {
    id: "ltr",
    label: "LTR",
    detail: "The learned ranking stage combines traceable features; it is planned, not implemented.",
  },
  {
    id: "rerank",
    label: "Rerank",
    detail: "Rerank impact is shown as an illustrative decision trace only.",
  },
  {
    id: "explain",
    label: "Explain",
    detail: "Grounded explanation summarizes ranking evidence without changing rank.",
  },
];

export const candidates: CandidateMatch[] = [
  {
    id: "candidate-a",
    label: "Candidate A",
    rank: 1,
    score: 92,
    role: "Applied AI Engineer",
    location: "Shanghai · Hybrid-ready",
    primaryReason: "Strong evidence across agent workflows, evaluation, and product delivery.",
    features: [
      { label: "Skill fit", shortLabel: "Skill", value: 94 },
      { label: "Evidence", shortLabel: "Evidence", value: 96 },
      { label: "Role direction", shortLabel: "Direction", value: 91 },
      { label: "Location fit", shortLabel: "Location", value: 88 },
      { label: "Seniority fit", shortLabel: "Seniority", value: 90 },
    ],
    evidenceStrength: "demonstrated",
    risk: { level: "low", label: "Low · one validation gap" },
    missingMustHaves: ["Delivery-incident case evidence"],
    projects: [
      {
        title: "Evaluation Harness Lab",
        summary: "Designed a rubric-driven evaluation workflow and documented an error taxonomy.",
        level: "demonstrated",
        skills: ["Evaluation", "Bad-case review", "Python"],
      },
      {
        title: "Support Agent Studio",
        summary: "Built a tool-calling workflow with human review boundaries and traceable steps.",
        level: "demonstrated",
        skills: ["Agent workflow", "Tool calling", "Observability"],
      },
      {
        title: "Ranking Explorer",
        summary: "Compared ranking features in a local prototype; offline labels are not yet attached.",
        level: "partial",
        skills: ["Ranking", "Feature analysis"],
      },
      {
        title: "Portfolio statement",
        summary: "Lists recommendation-system ownership without a linked artifact or case note.",
        level: "claim-only",
        skills: ["Recommendation systems"],
      },
    ],
    explanation:
      "Candidate A leads this illustrative shortlist because the strongest must-have capabilities are tied to inspectable projects, while role direction and working-location constraints remain aligned. The remaining gap should be validated in interview rather than inferred away.",
    interviewFocus: "Ask for a concrete delivery failure and how the evaluation loop changed afterward.",
    retrievedRank: 3,
    rerankImpact: "+2 positions after project-evidence strength outweighed a small sparse-keyword gap.",
    comparison: {
      candidateId: "candidate-b",
      summary: "Candidate A has stronger project evidence and closer AI product direction than Candidate B.",
      advantages: [
        "+14 evidence strength",
        "+9 role direction",
        "One fewer missing must-have",
      ],
    },
  },
  {
    id: "candidate-b",
    label: "Candidate B",
    rank: 2,
    score: 74,
    role: "Automation Engineer",
    location: "Remote · China",
    primaryReason: "Strong workflow automation delivery with partial ranking evidence.",
    features: [
      { label: "Skill fit", shortLabel: "Skill", value: 82 },
      { label: "Evidence", shortLabel: "Evidence", value: 72 },
      { label: "Role direction", shortLabel: "Direction", value: 68 },
      { label: "Location fit", shortLabel: "Location", value: 91 },
      { label: "Seniority fit", shortLabel: "Seniority", value: 76 },
    ],
    evidenceStrength: "partial",
    risk: { level: "medium", label: "Medium · direction gap" },
    missingMustHaves: ["Evaluation design", "Ranking-system experience"],
    projects: [
      {
        title: "Workflow Automation Studio",
        summary: "Implemented multi-step operations automation with explicit hand-off states.",
        level: "demonstrated",
        skills: ["Workflow automation", "Integrations"],
      },
      {
        title: "Search Quality Notebook",
        summary: "Explored retrieval trade-offs, but the artifact has no labeled comparison set.",
        level: "partial",
        skills: ["Retrieval", "Analysis"],
      },
      {
        title: "Profile statement",
        summary: "Mentions learning-to-rank exposure without a project artifact.",
        level: "claim-only",
        skills: ["LTR"],
      },
    ],
    explanation:
      "Candidate B remains competitive on delivery and location fit, but the evidence set supports workflow automation more strongly than recommendation ranking. The illustrative rank therefore preserves a clear direction and evaluation gap.",
    interviewFocus: "Probe whether search-quality analysis included labels, baselines, and bad-case review.",
    retrievedRank: 2,
    rerankImpact: "No position change; evidence review confirmed the retrieval-stage order.",
    comparison: {
      candidateId: "candidate-c",
      summary: "Candidate B ranks above Candidate C through stronger delivered workflow evidence.",
      advantages: ["+11 project evidence", "+7 seniority fit", "Better location alignment"],
    },
  },
  {
    id: "candidate-c",
    label: "Candidate C",
    rank: 3,
    score: 68,
    role: "ML Platform Engineer",
    location: "Beijing · On-site",
    primaryReason: "Solid platform fundamentals, with weaker product-direction alignment.",
    features: [
      { label: "Skill fit", shortLabel: "Skill", value: 79 },
      { label: "Evidence", shortLabel: "Evidence", value: 61 },
      { label: "Role direction", shortLabel: "Direction", value: 58 },
      { label: "Location fit", shortLabel: "Location", value: 63 },
      { label: "Seniority fit", shortLabel: "Seniority", value: 69 },
    ],
    evidenceStrength: "partial",
    risk: { level: "medium", label: "Medium · location mismatch" },
    missingMustHaves: ["Agent workflow delivery", "Evidence-led evaluation"],
    projects: [
      {
        title: "Model Serving Toolkit",
        summary: "Documented local model-serving and monitoring patterns in a reproducible sandbox.",
        level: "demonstrated",
        skills: ["ML platform", "Monitoring"],
      },
      {
        title: "Agent prototype note",
        summary: "Describes a planned agent workflow, but no working artifact is linked.",
        level: "claim-only",
        skills: ["Agent workflow"],
      },
    ],
    explanation:
      "Candidate C shows useful platform depth, but the evidence is less aligned with the job's applied-agent direction and location constraint. Those gaps are explicit rather than hidden inside the overall score.",
    interviewFocus: "Ask how platform work translated into an end-user AI workflow and measured quality.",
    retrievedRank: 2,
    rerankImpact: "-1 position after role-direction evidence was considered.",
    comparison: {
      candidateId: "candidate-b",
      summary: "Candidate B ranks above Candidate C through closer workflow and location alignment.",
      advantages: ["Stronger agent-workflow evidence", "Closer location fit", "+10 direction fit"],
    },
  },
];

export const jobContext = {
  title: "Applied AI Engineer",
  company: "Northstar Labs",
  location: "Shanghai · Hybrid",
  seniority: "Senior IC",
  strategy: "Evidence-aware v0.5 mock",
  runId: "run_design_005b",
} as const;
