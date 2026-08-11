# PeopleMatch Agent Product Requirements Document

## 1. Background

AI Builder roles often share vocabulary while differing sharply in actual direction: product-focused agents, retrieval systems, evaluation infrastructure, applied model work, and developer tooling can all mention Python, LLMs, and vector search. A useful matching system therefore needs evidence, constraints, and traceable ranking logic rather than keyword overlap alone.

PeopleMatch Agent is an autonomous, local-running prototype for exploring that problem with synthetic/sandbox data, public job-description examples, and manually created labels.

## 2. Problem

Keyword and embedding similarity can over-reward shared terminology while missing:

- whether a skill is supported by project evidence;
- whether the candidate and role point in the same work direction;
- whether seniority, location, and team stage are compatible;
- which stage caused a weak or incorrect recommendation;
- whether a later algorithm is actually better on a fixed offline dataset.

## 3. Product Goal

Build a traceable local recommendation system that can eventually structure profiles, retrieve candidate/job pairs, compute evidence-aware features, rank and rerank, generate grounded explanations, collect feedback, review bad cases, and compare runs through offline evaluation.

Phase 0's product goal is narrower: establish accurate product language, phase boundaries, repository structure, liveness, and a reproducible local engineering base.

## 4. Non-goals

The project does not target:

- production deployment or production hardening;
- a real recruitment marketplace;
- ATS or recruitment-platform integration;
- large-scale or distributed serving;
- online experimentation or A/B testing;
- private personal data ingestion;
- authentication, billing, employer accounts, or commercial operations;
- production traffic, latency, QPS, or impact claims.

## 5. Personas

### Candidate / AI Builder

Wants to understand which roles fit their demonstrated work and why, without a generic skill list being treated as evidence.

### Recruiter / Founder / Hiring Team

Wants a reviewable shortlist whose ranking signals, constraints, and supporting evidence can be inspected rather than accepted as a black box.

### Platform Operator

Wants to trace match runs, find bad cases, maintain sandbox labels, and compare offline algorithms with reproducible configurations.

## 6. Candidate Workflow

**PLANNED:** A candidate provides sandbox profile input, reviews a structured profile, corrects unsupported or misclassified evidence, sees matched roles, and inspects the evidence and constraints behind each explanation.

Phase 0 provides no candidate form, data, or parser.

## 7. Recruiter Workflow

**PLANNED:** A recruiter provides a public or sandbox job description, reviews structured role requirements, retrieves candidate matches, inspects ranking evidence and constraints, and records explicit feedback on a recommendation.

Phase 0 provides no recruiter workflow or fake matches.

## 8. Platform Operator Workflow

**PLANNED:** An operator traces a match run by stage, reviews feedback-linked bad cases, assigns documented failure categories, launches an offline evaluation, and compares runs on a fixed labeled dataset.

Phase 0 provides documentation and request IDs as the first traceability primitive only.

## 9. Candidate Profile Concept

**PLANNED:** A typed, versioned representation of skills, project evidence, role direction, seniority indicators, location/preferences, constraints, source references, and extraction confidence. Claimed skills and evidence must remain separate fields.

## 10. Job Profile Concept

**PLANNED:** A typed, versioned representation of required and preferred skills, responsibilities, role direction, seniority, location/work mode, team stage, constraints, and source references.

## 11. Matching Engine Concept

**PLANNED:** A staged pipeline of retrieval, feature engineering, deterministic constraints, learning-to-rank, and cross-encoder reranking. Each match run records stage inputs, outputs, versions, and configuration. The LLM does not own the final rank.

## 12. Match Explanation Concept

**PLANNED:** A readable account grounded in the evidence and constraints already used or observed by ranking. Explanation may summarize strengths, gaps, and uncertainty; it must not rewrite the rank or invent supporting experience.

## 13. Feedback Concept

**PLANNED:** Explicit, attributable signals such as useful/not useful, incorrect evidence, wrong direction, constraint mismatch, or explanation issue. Feedback is stored separately from the original immutable match run.

## 14. Bad Case Review Concept

**PLANNED:** A workflow for connecting poor recommendations to failure categories and pipeline stages: extraction, retrieval, feature computation, ranking, reranking, explanation, data quality, or label quality.

## 15. Offline Evaluation Concept

**PLANNED:** Reproducible evaluation on a small local dataset with manually documented labels. Future Recall, NDCG, MRR, and related results must identify dataset version, split, configuration, comparison baseline, and limitations. No result implies online impact.

## 16. Product Success Criteria

Phase 0 succeeds when:

- a reviewer can distinguish the current implementation from the target product;
- the repository starts through documented local commands;
- liveness and request tracing are deterministic and tested;
- the frontend reports real backend availability rather than fake state;
- future services have clear boundaries without speculative implementation;
- all claims follow privacy and evaluation-integrity rules.

Later-phase success criteria must be defined in their own phase specifications before implementation and measured only after real experiments run.

## 17. Phase Boundaries

- **Phase 0:** documentation, monorepo, liveness, frontend shell, local infrastructure configuration, tests.
- **Phase 0.5:** product design and UI system; no matching algorithms.
- **Phases 1–3:** data contracts, persistence, and extraction.
- **Phases 4–7:** retrieval, features, ranking, and reranking.
- **Phases 8–10:** orchestration, explanation, feedback, and bad-case review.
- **Phases 11–12:** offline evaluation and local prototype hardening.

A later phase begins only after the preceding phase's quality gate and an explicit user request.

## 18. Privacy / Honesty Constraints

- Use only synthetic/sandbox data, public job-description examples, and manually created labels.
- Do not ingest or commit private candidate data.
- Do not claim production deployment, real users, employers, integrations, traffic, revenue, partnerships, or online experiments.
- Do not invent performance metrics or algorithm improvements.
- Clearly label architecture, interfaces, and workflows as `CURRENT` or `PLANNED`.
