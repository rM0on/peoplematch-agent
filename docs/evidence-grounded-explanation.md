# Evidence-grounded Explanation

**Phase 9 status:** In Progress

**Phase 9.1 status:** Persistence and contracts are frozen.

**Phase 9.2 status:** Deterministic historical Evidence Bundle and fact-engine
hardening is in progress. Phase 9 remains in progress; provider-backed
natural-language explanation is planned for Phase 9.3.

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

The provider contract continues the Phase 8 structured snapshot boundary. Its
input is an explicit allowlist of closed identifiers, enums, bounded lists of
requirement Evidence IDs, and finite numeric ranking/feature values. Rich
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

## Not Implemented In Phase 9.2

Provider integration, prompts, parsing/repair, LLM grounding/repair
orchestration, HTTP routes, frontend integration, feedback, and offline
explanation-quality evaluation remain later Phase 9, 10, or 11 work. The
Phase 9.2 fact layer is deterministic and evidence-backed but intentionally
does not produce natural-language or causal explanations.
