# PeopleMatch Agent Version Strategy

PeopleMatch Agent separates the stable local portfolio experience from the paused public-cloud deployment work without deleting or rewriting either history.

## `portfolio-demo`

**Purpose:** AI Engineer portfolio、GitHub 展示、面试演示与本地完整运行。

This branch is based on the stable pre-cloud checkpoint `ac7de7b59af1a1d22bd6b9af636acaf82f61c87e` and keeps the complete application workflow:

- FastAPI backend and Next.js frontend;
- JD-first recommendation and Candidate Lifecycle;
- Hybrid Retrieval、Feature Engineering 与 LambdaMART Ranking；
- Evidence-grounded Explanation、MatchRun、Feedback 与 Bad Case Review；
- frozen Offline Evaluation evidence;
- deterministic mock mode for reproducible local demos and the optional OpenAI-compatible Provider boundary.

It does not require Oracle Cloud、Cloudflare Tunnel or public-runtime secrets. It remains a local AI application prototype rather than a hosted production service.

## `cloud-deployment-archive`

**Purpose:** Future public deployment recovery point.

This branch is pinned to Cloud-4A checkpoint `50a435e313c174c7b2c0669274706d33b0ffc5c4` and preserves:

- Cloud-1 Production Docker Runtime foundation;
- Cloud-2 Public Security Boundary;
- Cloud-3 Artifact Delivery and Runtime Readiness;
- Cloud-4A Oracle ARM / Cloudflare pre-cloud deployment preparation.

Public deployment is paused until Oracle ARM、Cloudflare Tunnel and production secrets are configured. The pause does not remove the deployment design, security boundary or artifact-verification work, and it does not imply that a public URL currently exists.

## Frozen invariants

The branch separation does not change Candidate Pool data, Retrieval semantics, Feature Engineering, LambdaMART ordering, optional Cross-Encoder experiments, Evidence grounding or Phase 11 evaluation artifacts and results.

## Recommended use

- Use `portfolio-demo` for local review, screenshots, GitHub portfolio presentation and interviews.
- Use `cloud-deployment-archive` when public infrastructure is ready and Cloud-4 deployment resumes.
- Do not merge cloud-only operational complexity back into the portfolio branch unless a later task explicitly requires it.
