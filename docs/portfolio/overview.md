# PeopleMatch Agent Portfolio Overview

> Historical pre-Fresh screenshot walkthrough. The current, frozen recruiter-facing screenshot set and its run provenance are documented in [Final portfolio screenshots](../images/portfolio-final/README.md). Do not treat the older mock captures below as the real-provider Fresh Top-3 validation.

PeopleMatch Agent is an **AI-powered talent matching and recommendation system**. A recruiter provides a Job Description (JD); the system structures the requirement, retrieves candidates from a talent pool, ranks them with LambdaMART, and generates explanations that must remain grounded in recorded evidence.

它不是让 LLM 直接决定候选人顺序的简历匹配工具。系统把语义理解、候选召回、学习排序、证据解释和人工复核拆成可独立验证的阶段。

## Designed workflow

```text
Job Description
    → Structured Job Profile
    → Dense + Sparse Hybrid Retrieval
    → Explicit Feature Engineering
    → LambdaMART Ranking
    → Top-K Candidates
    → Evidence-grounded Explanation
    → MatchRun / Feedback / Bad Case Review
```

Candidate ingestion is a separate lifecycle:

```text
Resume Text → Structured Candidate Profile → Human Confirmation → Candidate Pool
```

## What the project demonstrates

- **AI application engineering:** schema-first extraction, provider isolation, safe error mapping and versioned prompts.
- **Recommendation systems:** Dense/Sparse retrieval, Reciprocal Rank Fusion, explicit pair features and Learning-to-Rank.
- **LLM safety:** safe evidence projection, candidate-scoped semantic selection, deterministic ExplanationPlanV1 binding and grounding validation. Historical full-object Provider and repair experiments are archived, not the current trusted path.
- **Traceability:** immutable MatchRun history, model/configuration provenance and ranking fingerprints.
- **Evaluation discipline:** frozen data/protocol boundaries, Retrieval and Ranking metrics, and explicit limitations.

## Product evidence

All captures below were produced from the running `portfolio-demo` application at 1440 × 1024 with synthetic data and the deterministic mock provider. They contain no real candidate information or credentials.

### 01 · Product overview

![PeopleMatch Agent product overview](../images/portfolio/01_product_overview.png)

**Purpose:** establish the JD-first product model and show that the system searches a candidate pool rather than scoring one résumé in isolation.

**Technical signal:** provider status, seven-step recommendation story and the explicit separation between LLM understanding and LambdaMART ranking.

### 02 · JD matching flow

![JD-first recommendation input](../images/portfolio/02_jd_matching_flow.png)

**Purpose:** show the real recommendation entry point with a synthetic Chinese JD.

**Technical signal:** Job Description as query, reproducible mock mode and safe sample-data disclosure.

### 03 · Candidate ranking

![Top-K candidate ranking](../images/portfolio/03_candidate_ranking.png)

**Purpose:** show the shortlist, recommendation tier, retrieval rank, LTR rank and raw LambdaMART score.

**Technical signal:** ranking is owned by the learned model; the UI explicitly states that the score is not a probability or hiring prediction.

### 04 · Evidence-grounded explanation

![Evidence-grounded recommendation explanation](../images/portfolio/04_evidence_explanation.png)

**Purpose:** explain why the selected candidate is recommended and which requirements still need verification.

**Technical signal:** candidate evidence, job requirement references and diagnostic references are displayed from the persisted MatchRun evidence projection.

### 05 · MatchRun trace

![MatchRun trace and ranking protection](../images/portfolio/05_matchrun_trace.png)

**Purpose:** connect the user-visible result with its immutable execution record.

**Technical signal:** run identity, result fingerprint, completed orchestration steps and the boundary that explanation cannot change scores or ordering. The current visible trace lists input resolution, LambdaMART ranking and result persistence; other pipeline detail remains available through persisted provenance rather than invented UI steps.

### 06 · Candidate lifecycle

![Candidate profile preview](../images/portfolio/06_candidate_lifecycle.png)

**Purpose:** show how a résumé becomes a structured profile before entering the talent library.

**Technical signal:** extraction preview, missing-field visibility and an explicit human confirmation gate. This capture stops before persistence and does not modify the candidate pool.

### 07 · Feedback review

![Historical feedback review](../images/portfolio/07_feedback_badcase.png)

**Purpose:** show the human review surface for a completed MatchRun.

**Technical signal:** feedback is bound to persisted history and does not rewrite the original ordering. Bad Cases are created explicitly rather than inferred automatically from feedback.

## Verified boundaries

- Local AI application prototype; no production SaaS or public deployment claim.
- Synthetic curated candidate/job data; no real résumé or hiring outcome.
- Default screenshots use deterministic mock mode. The OpenAI-compatible boundary received a local controlled Qwen compatibility check, but that live result is not a reproducible repository artifact.
- LambdaMART is the default ranking owner. Cross-Encoder remains an optional frozen experiment.
- Offline metrics describe the frozen sandbox only and are not hiring accuracy.

## Continue reading

- [System architecture](architecture.md)
- [Engineering decisions](engineering-decisions.md)
- [Interview guide](interview-guide.md)
- [Frozen offline evaluation](../offline-evaluation.md)
