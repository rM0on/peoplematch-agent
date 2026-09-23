# PeopleMatch Agent Interview Guide

## 30-second introduction

PeopleMatch Agent 是一个岗位 Query 驱动的人才推荐系统。LLM 把 JD 和 Resume 结构化，Dense 与 BM25 负责候选召回，LambdaMART 基于显式特征决定 Top-K，最后 LLM 只能在 MatchRun 已记录的 Evidence 上生成解释。项目重点不是调用模型，而是把 Retrieval、Ranking、Grounding、Feedback 和 Offline Evaluation 组成一条可复现、可审计的 AI Application pipeline。

## 2-minute introduction

传统简历搜索的三个问题是：输入非结构化、关键词检索缺少语义能力、LLM 直接打分难以稳定评估。PeopleMatch Agent 将这些问题分开处理。

首先，Profile Extraction Provider 把 JD 或 Resume 转成受 Pydantic Schema 约束的结构化画像。然后 Dense Retrieval 和 BM25 从候选池分别做语义和精确召回，通过 RRF 合并。每个 candidate/job pair 会生成十个冻结特征，LambdaMART 负责默认排序。

排序完成后，系统持久化 MatchRun、候选顺序、模型 provenance 和 Evidence。Explanation Provider 只能引用 opaque Evidence references，输出还要通过 Schema 与 Grounding Validation。Feedback 与 Bad Case 用于人工复核，但不会自动污染训练标签。

Phase 11 用冻结的 synthetic sandbox 分别评测 Retrieval 和 Controlled Ranking，同时明确披露样本规模、judgment coverage 与 Test exposure，因此项目可以讨论结果，也不会把离线指标包装成真实招聘准确率。

## 10-minute technical deep dive

### 1. Problem and ownership

- Product entry: Job Description as recommendation query.
- Candidate lifecycle: résumé extraction and human confirmation are separate from recommendation.
- Ranking owner: LambdaMART.
- Language owner: extraction and evidence-constrained explanation providers.

### 2. Retrieval

- Dense retrieval captures semantics and paraphrases.
- Sparse BM25 protects exact skill/tool matching.
- Equal-weight RRF combines ranks without calibrating incompatible raw scores.
- Retrieval is evaluated with Recall@K on the full frozen corpus.

### 3. Ranking

- Ten explicit features cover similarity, requirements, projects, direction, tools, location, seniority and risk penalties.
- LambdaMART optimizes query-group ordering rather than absolute classification.
- Raw margins are retained for audit and never described as probabilities.
- Controlled Ranking compares strategies on the same 48-candidate pool.

### 4. Explanation safety

- MatchRun is fixed before explanation begins.
- Provider input uses opaque references and bounded evidence categories.
- Structured output, grounding checks and constrained repair fail closed.
- Candidate order, score and fingerprint are checked for invariance.

### 5. Evaluation and review

- Retrieval: Recall@5/10/20.
- Ranking: NDCG@5/10, MRR@10 and explicit pairwise accuracy.
- Standard Precision@K is intentionally omitted because most candidate/job pairs are unjudged.
- Feedback and Bad Case analysis remain separate from explicit evaluation labels.

### 6. Runtime and provider architecture

- Next.js → FastAPI → PostgreSQL/Qdrant.
- Extraction and Explanation adapters share OpenAI-compatible transport but retain separate provider selection.
- Deterministic mock supports reproducible local and browser E2E tests.
- Secrets stay in backend environment variables.

## High-probability questions

### Why not ask ChatGPT to match the résumé directly?

That would mix understanding, scoring and explanation into one non-deterministic output. This project isolates those responsibilities so ranking can be reproduced and evaluated independently of generated language.

### Why not rank only by Embedding similarity?

Similarity misses exact technical requirements, project evidence, location/seniority constraints and risk penalties. Embedding is one retrieval and feature signal, not the complete decision rule.

### Why Hybrid Retrieval?

Dense handles semantic equivalence; BM25 stabilizes exact technical terms. RRF combines their orderings without requiring raw-score calibration. The evaluation also shows Hybrid is not automatically the best strategy on every small dataset.

### Why LambdaMART?

The task is relative ordering within a job query. LambdaMART directly learns that ordering from explicit graded judgments and supports NDCG-based evaluation and feature-level inspection.

### How do you prevent hallucinated explanations?

The provider receives bounded evidence references, returns a structured plan, and must pass schema and grounding validation. Unsupported references and facts are rejected. Repair may correct reference formatting but cannot add evidence.

### What if the LLM provider fails?

The request returns a stable, redacted error. It does not silently switch to mock or replace the frozen ranking. Existing MatchRun ranking evidence remains unchanged.

### How do you evaluate recommendation quality?

Retrieval and ranking are evaluated separately. Recall@K measures whether relevant candidates enter the pool; NDCG/MRR/pairwise metrics measure ordering on a controlled pool. The dataset and exposure limitations are reported beside the results.

### Why was Cross-Encoder not selected?

It was implemented and evaluated, but the frozen comparison did not establish superiority over LambdaMART. The default remains the evidence-supported model rather than the newest model.

### How would you deploy it?

The application already runs as Next.js, FastAPI, PostgreSQL, Redis and Qdrant under Docker Compose. The archived cloud branch contains production-runtime, security-boundary and artifact-readiness work. Public deployment is paused until external infrastructure is configured; the portfolio does not claim production SLA.

## Three-minute demo route

1. Open the recommendation workbench and explain that JD is the query and LLM does not own ranking.
2. Load the synthetic JD and run the deterministic workflow.
3. Point out Retrieval rank, LTR rank and why LTR score is not a probability.
4. Expand technical evidence and show that explanation references persisted evidence.
5. Show MatchRun identity/fingerprint and open Recommendation History for human review.
6. If time remains, show Candidate Lifecycle and explain the pre-persistence confirmation gate.

## Claims to avoid

- “The system has 95.93% hiring accuracy.”
- “It is production-ready or used by real recruiters.”
- “LLM decides the best candidate.”
- “Feedback automatically improves the model.”
- “Cross-Encoder or Hybrid Retrieval is universally superior.”
