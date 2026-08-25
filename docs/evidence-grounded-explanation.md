# Evidence-grounded Explanation

**Phase 9 status:** In Progress

**Phase 9.1 status:** Persistence and contracts are frozen.

**Phase 9.2 status:** Deterministic historical Evidence Bundle and fact engine
are frozen.

**Phase 9.3/9.4 status:** Backend provider planning, grounding, deterministic
rendering, persistence orchestration, and APIs are implemented and ready for
review. Phase 9 remains in progress until this backend slice is frozen; no
frontend explanation UI is included.

## Current Boundary

Phase 9.1 adds an explanation persistence aggregate without changing the
frozen ranking lifecycle:

```text
MatchRun
  -> ExplanationRun
       -> MatchExplanation[]
```

An `ExplanationRun` starts as `RUNNING` and may become `COMPLETED` or
`FAILED`. Terminal runs have no normal repository mutation path. A later
regeneration will create a new `explanation_run_id`; this is
application/repository-layer terminal immutability, not database-level
tamper-proof storage.

Request preconditions belong to later orchestration and may reject before an
ExplanationRun exists. Once accepted, a durable `RUNNING` row may exist before
evidence construction or provider execution, so early `RUNNING` and `FAILED`
records permit incomplete evidence and provider provenance. `COMPLETED`
requires complete evidence, provider, prompt, output, count, timestamp, and
result-fingerprint fields.

The current backend orchestration is:

```text
completed historical MatchRun
  -> frozen EvidenceBundle + EvidenceFacts
  -> opaque provider-reference projection
  -> untrusted explanation_plan_v1 selection
  -> reference resolution + deterministic semantic grounding
  -> fixed backend template rendering
  -> explanation_output_v1
  -> atomic terminal persistence
```

The provider is not a source of factual claims. It cannot return summary prose,
missing requirements, rewritten resume text, ranks, scores, or new facts. It can
only select closed categories, opaque references, and bounded operations already
present in the prompt projection. Internal Evidence IDs are resolved only after
the response returns, and provider output is never persisted directly.

Phase 9.2 does not change that persistence lifecycle. Its
`EvidenceBundleBuilder` accepts only a completed historical MatchRun aggregate,
validates the frozen snapshot versions and fingerprints, reconstructs the exact
Phase 8 result fingerprint from persisted MatchResult values and provenance,
and rejects unsupported diagnostics versions before building evidence. It then
orders persisted history canonically and emits deterministic
`evidence_facts_v1` records. It does not call repositories, Qdrant, retrieval,
feature, ranking, Cross-Encoder, or any model provider.

Structured evidence labels use the versioned
`evidence_label_normalization_v1` identity contract: Unicode NFKC
normalization, collapsed whitespace, trimming, and case-folding occur before
hashing, sorting, deduplication, or ownership comparison. This normalization
applies only to structured historical labels; it does not turn raw source prose
into provider-safe evidence.

## Versioned Contracts

- `evidence_bundle_v1` is the internal historical audit payload. It may carry
  persisted MatchRun identity, structured historical Job/Candidate evidence,
  ranking facts, runtime provenance, and workflow metadata.
- `provider_evidence_v1` is the separate allowlisted payload that a future
  provider may receive. A single canonical projection from the internal bundle
  produces closed, typed retrieval, feature, ranking, diagnostic, and top-1
  comparison fields. Provider nested models are separate from the richer
  historical models, and the projection constructs every approved field
  explicitly. It has no generic name/value, metadata, attributes, or payload
  channel and excludes request IDs, RunSteps, internal workflow and model
  fingerprints, errors, and secret configuration.
- `evidence_facts_v1` is the internal deterministic fact substrate. Its
  checked-in JSON Schema closes statement keys, comparison dimensions, ranks,
  and object properties. Runtime validation additionally requires exact
  Candidate coverage and resolves every reference and semantic fact mapping
  against the source Evidence Bundle. Semantic match reasons cite only
  structured source evidence such as Candidate skills, projects, project
  evidence, matched Job requirements, or exact persisted relation diagnostics.
  Feature and ranking values are isolated in typed `ranking_context` records or
  top-1 comparisons; they cannot directly support semantic match reasons. When
  required source evidence is unavailable, the semantic reason is omitted.
- `explanation_output_v1` defines bounded Candidate explanation output with
  evidence references and structured rewrite operations. It contains no
  writable ranking, score, probability, confidence, or final-match field.
- `explanation_plan_v1` is the provider-output contract. Its checked-in schema
  permits only canonical top-k Candidate plan entries, closed template keys,
  opaque `ref_####` selections, and bounded operations. It contains no
  provider-authored factual text field.

Both evidence payloads and their independent canonical fingerprints are
stored when available. Candidate and result fingerprints use the same
canonical JSON and SHA-256 convention as Phase 8. Timestamps, request IDs,
provider response IDs, credentials, and transaction identifiers are not
inputs to explanation content fingerprints.

`evidence_facts_v1` retains two distinct bindings. `bundle_fingerprint` binds
facts to the exact audit bundle, including immutable MatchRun/result identity.
`normalized_content_fingerprint` fingerprints the canonical provider-safe
projection, so equivalent normalized structured labels have one semantic
content identity without discarding the Phase 8 audit fingerprint.

Candidate IDs and ranks are unique and stored in contiguous ascending rank
order. Candidate-owned Evidence IDs are bound to that parent rank and
Candidate identity, and fact namespaces are restricted to their matching fact
kind. LTR bundles reject Cross-Encoder provenance and Candidate CE facts;
explicit Cross-Encoder experiment bundles require both runtime provenance and
persisted Candidate CE rank/score facts.

The JSON Schema artifacts enforce structural types, bounds, closed properties,
and operation-specific Evidence ID syntax. Runtime Pydantic validation adds the
cross-object ownership, uniqueness, canonical ordering, and ranking-variant
consistency rules that JSON Schema does not express.

## Privacy

The persisted provider contract continues the Phase 8 structured snapshot
boundary. The actual model prompt is narrower: a deterministic transient
projection replaces internal Candidate/Evidence identities with opaque
`candidate_####` and `ref_####` values and includes only closed fact categories,
enums, and bounded reference lists. Rich
historical labels, requirement text, target roles, technologies, locations,
project summaries, outcomes, and evidence-statement prose remain internal and
are not projected. Provider identifiers use a restricted normalized token
contract, so legal identifier fields cannot carry raw resume/JD/private prose.

Raw resumes/JDs, Candidate or company names, URLs, request/workflow data,
evaluation labels and splits, hard-negative metadata, errors, and provider
secrets have no provider input property. Numeric ranking evidence uses strict
integer/finite-float fields, while relations and statuses use closed enums.
Provider diagnostics use closed enums and typed requirement-ID lists rather
than a generic string/value channel.

The repository also requires supplied provider evidence to equal the canonical
explicit projection of the validated internal bundle. Explanation output
references are checked against that persisted bundle for existence, Candidate
and rank ownership, and kind compatibility. These are narrowly defined
data-minimization and grounding contracts, not claims of general semantic
redaction or complete privacy/security enforcement.

## Provider, Repair, and Transaction Boundary

`ExplanationProvider` is provider-neutral. The deterministic mock is offline;
the DeepSeek configuration uses a generic OpenAI-compatible chat-completions
transport adapter. Provider selection, endpoint, model, timeout, prompt byte
limit, output-token limit, and maximum one repair are environment controlled;
requests cannot select a provider or model.

The prompt is versioned and fingerprinted with its evidence and output contract
fingerprints. A repair request carries only a bounded failure category and a
fresh copy of the canonical opaque projection; raw prior output is discarded.
No provider HTTP call or repair attempt holds a database transaction open.

Migration `20260825_0004` adds only bounded generation-attempt audit metadata:
attempt number/status, bounded error category, provider kind/name/model and
configuration fingerprint, and timestamps. It does not store prompts, provider
responses, evidence payloads, credentials, authorization headers, or stack
traces. Phase 9.1 terminal transition locking and atomic child persistence remain
the authority for completion/failure.

The backend exposes:

- `POST /api/v1/match-runs/{match_run_id}/explanations`;
- `GET /api/v1/explanation-runs/{explanation_run_id}`;
- `GET /api/v1/match-runs/{match_run_id}/explanation-runs`.

## Not Implemented

Frontend explanation integration, authentication/users, distributed queues,
Redis/Celery business usage, feedback, and offline explanation-quality
evaluation are not implemented. The provider does not generate final prose;
backend templates render non-causal descriptions of recorded evidence. These
controls reduce the accepted output surface but are not a claim of perfect
hallucination prevention, privacy, or production hiring effectiveness.
