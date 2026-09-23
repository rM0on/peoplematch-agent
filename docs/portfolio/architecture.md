# PeopleMatch Agent Architecture

## Design goal

The system separates probabilistic language tasks from ranking ownership. LLM providers structure inputs and plan explanations; deterministic retrieval, explicit features and LambdaMART decide candidate order; validation code controls what may be displayed.

```mermaid
flowchart TD
    User[Recruiter / Hiring Manager] --> Web[Next.js Product UI]
    Web --> API[FastAPI API]

    JD[Job Description] --> Extract[Profile Extraction Provider]
    Extract --> Job[Structured Job Profile]

    Resume[Resume Text] --> CandidateExtract[Candidate Extraction Provider]
    CandidateExtract --> Preview[Structured Candidate Preview]
    Preview --> Confirm[Human Confirmation]
    Confirm --> Postgres[(PostgreSQL Candidate Truth)]
    Postgres --> Qdrant[(Qdrant Derived Index)]

    API --> Extract
    API --> Retrieval[Hybrid Retrieval]
    Job --> Retrieval
    Postgres --> Retrieval
    Qdrant --> Retrieval
    Retrieval --> Dense[Dense Semantic Retrieval]
    Retrieval --> Sparse[Sparse BM25 Retrieval]
    Dense --> RRF[Equal-weight RRF]
    Sparse --> RRF
    RRF --> Features[10 Explicit Pair Features]
    Features --> LTR[LambdaMART Ranking]
    LTR --> TopK[Top-K Candidate Order]

    TopK --> Run[Immutable MatchRun]
    Run --> Evidence[Evidence Builder]
    Evidence --> Projection[Opaque Provider Projection]
    Projection --> Explain[Explanation Provider]
    Explain --> Schema[ExplanationPlanV1 Validation]
    Schema --> Grounding[Grounding Validation]
    Grounding --> Render[Deterministic Rendering]
    Render --> Web

    Run --> Feedback[Feedback / Bad Case Review]
    LTR -. optional frozen experiment .-> CE[Cross-Encoder Reranking]
```

## Responsibility boundaries

| Component | Owns | Does not own |
| --- | --- | --- |
| Extraction provider | JD/Resume semantic structuring | Candidate order or ranking score |
| Dense retrieval | Semantic candidate recall | Final recommendation order |
| Sparse retrieval | Exact technical-term recall | Final recommendation order |
| RRF | First-stage retrieval fusion | Learned relevance ordering |
| Feature engineering | Frozen candidate/job pair signals | Free-form interpretation |
| LambdaMART | Default final candidate order and raw margin | Natural-language explanation |
| Cross-Encoder | Optional experimental shortlist reorder | Default product order |
| Evidence builder | Historical facts and ownership | New candidate facts |
| Explanation provider | Structured wording plan | Ranking mutation or unsupported claims |
| Grounding validator | Evidence-reference integrity | Provider fallback or fact invention |

## Data and state

### PostgreSQL

The source of truth for Candidate/Job profiles, MatchRuns, match results, explanations, feedback and Bad Cases.

### Qdrant

A rebuildable derived vector index. It does not replace the structured profile truth stored in PostgreSQL.

### Redis

Present in the local infrastructure contract; the `portfolio-demo` product workflow does not depend on Redis business state.

### Model artifacts

The frozen LambdaMART model and feature metadata determine ranking compatibility. Startup must not silently substitute a missing or incompatible model.

## Runtime data flow

1. The JD is validated and parsed into a `JobProfile`.
2. Dense and Sparse retrievers query the same candidate corpus.
3. Equal-weight RRF creates the first-stage pool.
4. Ten frozen explicit features are calculated for each candidate/job pair.
5. LambdaMART produces raw margins and the default Top-K order.
6. MatchRun persists ordering, scores, provenance and evidence ownership.
7. The provider receives opaque evidence references rather than unrestricted profile content.
8. Schema and grounding validation reject unsupported output; one constrained repair may correct reference-format violations without adding facts.
9. The rendered explanation is stored against the historical MatchRun and can be reviewed without altering ranking.

## Invariants

- Explanation generation cannot alter Candidate ordering, LTR score or ranking fingerprint.
- Provider failure does not authorize fallback ranking or fabricated success.
- Feedback and Bad Cases are observations, not automatic training labels.
- Cross-Encoder results do not replace the default LambdaMART product order.
- Phase 11 evaluation data and results remain frozen independently of runtime candidate ingestion.

## Provider boundary

Extraction and Explanation remain separate task domains while sharing the OpenAI-compatible transport. Each task can use deterministic mock or `openai_compatible` configuration independently. API keys remain backend environment variables and are never part of frontend state, screenshots, MatchRuns or evaluation artifacts.
