# Phase 15 Production AI Provider Architecture Design

## Status

Approved design for implementation. This phase productizes the existing real-provider boundary; it does not claim that the local prototype is production-ready or that any external provider has been live-verified.

## Decision

PeopleMatch keeps two independent domain interfaces:

- Profile Extraction owns schema-first Candidate/Job extraction.
- Explanation Generation owns evidence-reference planning over a completed historical MatchRun.

Both interfaces compose the existing OpenAI-compatible chat transport. Phase 15 does not introduce a third client and does not merge the two domains into a generic two-method `LLMProvider`.

The runtime supports deterministic `mock` mode and a generic `openai_compatible` mode. The existing `deepseek` selector remains a compatibility alias, but the underlying configuration and transport are provider-neutral.

## Repository Finding

The pre-implementation review found that Provider abstraction already exists:

- Profile extraction has a provider protocol, deterministic mock, strict output validation, bounded repair, and an adapter over the Phase 9 transport.
- Explanation generation has a provider protocol, an OpenAI-compatible HTTP transport, timeout/error mapping, bounded output, and secret-safe provenance.
- The JD-first browser workflow already accepts arbitrary text. Arbitrary text fails only in deterministic mock mode because mock outputs are intentionally registered fixtures.

Phase 15 therefore generalizes and exposes the existing capability instead of rebuilding it.

## Frozen Boundaries

The following remain byte-for-byte and semantically frozen:

- Phase 11 dataset, labels, query splits, contracts, manifests, selected artifacts, metrics, and results.
- The original 48 Candidate Profiles and frozen Candidate Pool source data.
- Phase 4 Retrieval behavior and configuration semantics.
- Phase 5 feature registry, values, order, and fingerprint.
- Phase 6 LambdaMART artifact, scoring, and ranking ownership.
- Phase 7 Cross-Encoder experiment and artifacts.
- Phase 9 Evidence contracts, reference ownership, grounding, deterministic rendering, and ranking invariance.

Phase 15 may change only Provider configuration/adapters, extraction prompt packaging, non-secret status reporting, runtime error presentation, documentation, and tests.

## Configuration Contract

### Selectors

Extraction and explanation remain independently selectable:

- `EXTRACTION_PROVIDER=mock|openai_compatible`
- `EXPLANATION_PROVIDER=mock|openai_compatible`

`deepseek` is accepted as a backwards-compatible alias for `openai_compatible`. Unknown values fail closed. There is no implicit fallback from a configured real provider to mock.

### Shared transport settings

The generic transport reads:

- `LLM_BASE_URL`
- `LLM_MODEL`
- `LLM_API_KEY`

Task-specific retry, timeout, prompt-size, and output-token bounds remain under the existing Extraction and Explanation settings. Existing DeepSeek-prefixed values may be read only as a compatibility fallback when the generic equivalent is absent. Conflicting generic and legacy values fail validation instead of choosing silently.

The API key is never returned, logged, fingerprinted, persisted, rendered, or sent to the browser. Provider configuration fingerprints include only normalized non-secret settings.

### URL and model validation

Real mode requires a credential-free HTTPS base URL, a bounded safe model identifier, and a non-empty local API key. User-info, query parameters, fragments, insecure HTTP, and unsupported selectors are rejected before any network call.

## Prompt Versioning

Extraction system instructions move from an inline Python constant into immutable text artifacts:

- `candidate_extraction_prompt_v1.txt`
- `job_extraction_prompt_v1.txt`

Each artifact has a closed version identifier and deterministic fingerprint derived from its content and output contract. Repair guidance remains bounded runtime data and cannot add unsupported facts.

The existing `explanation_prompt_v1.txt` and `explanation_plan_v1` contract remain unchanged. Phase 15 does not allow a Provider to author persisted factual prose; it may only select approved evidence references and template operations.

## Runtime Data Flow

```text
Arbitrary JD text
  -> Profile Extraction task adapter
  -> shared OpenAI-compatible transport
  -> strict JobExtractionDraft validation and bounded repair
  -> persisted Job Profile
  -> unchanged Hybrid Retrieval
  -> unchanged Feature Engineering
  -> unchanged LambdaMART Top-K
  -> immutable MatchRun and Evidence Bundle
  -> Explanation task adapter over the same transport configuration
  -> closed evidence-reference plan
  -> unchanged deterministic grounding/rendering
  -> browser response
```

Mock mode follows the same domain orchestration but accepts only registered synthetic fixtures. It remains the default for tests, CI, and reproducible local demonstration. Real mode enables arbitrary permitted JD/Resume text without changing downstream matching ownership.

## Provider Status Contract

A dedicated read-only endpoint reports runtime configuration readiness without performing an external Provider call. It is separate from `/health`, whose liveness semantics remain unchanged.

The response contains only closed, non-secret data for each task:

- task: `extraction` or `explanation`
- mode: `mock` or `openai_compatible`
- configured: boolean
- provider name and configured model when safe
- capability text indicating whether arbitrary input is supported

The response never includes API keys, authorization headers, raw URLs, prompts, raw inputs, or Provider responses. The UI says “已配置” rather than “已连接” because readiness is not a network health check.

## Frontend Experience

The JD field remains the primary recommendation input. “加载示例 JD” is optional assistance, not a prerequisite.

The workbench shows:

- deterministic mock mode: registered synthetic examples are available; arbitrary input requires real-provider configuration;
- OpenAI-compatible configured mode: arbitrary JD input is supported;
- unconfigured real mode: a clear setup error before recommendation starts.

Progress states remain bounded and map to actual stages:

1. 正在理解岗位需求
2. 正在准备候选检索
3. 正在执行候选召回与 LambdaMART 排序
4. 正在生成证据约束解释

Errors are mapped to short recoverable Chinese messages. Request IDs may be shown for diagnosis, but stack traces, Provider payloads, credentials, and raw upstream messages are never displayed.

## Explanation Integrity

Real Provider use does not turn explanation into free-form factual generation. Personalization comes from each Candidate’s own persisted Profile, MatchRun, deterministic Evidence Facts, and the Provider’s bounded selection of supported references. Backend grounding and rendering remain authoritative.

Explanation generation must prove that candidate order, result fingerprint, rank, and raw LTR score are identical before and after the Provider call.

## Failure Semantics

- Missing or unsafe configuration: fail before network access.
- Timeout: `provider_timeout`, no retry beyond the configured bound.
- Transport, rate-limit, or upstream HTTP failure: typed unavailable response; no raw upstream body.
- Malformed envelope, prose instead of JSON, or schema-invalid output: bounded repair, then `provider_output_invalid`.
- Unsupported arbitrary input in mock mode: explain that the deterministic fixture is unavailable; do not silently switch providers.
- Extraction failure prevents persistence, index refresh, retrieval, and ranking.
- Explanation failure preserves the completed immutable MatchRun but must not fabricate a successful explanation.

## Testing Strategy

Implementation is RED-first.

Backend tests cover:

- independent Extraction/Explanation selectors;
- generic configuration and legacy alias compatibility;
- conflicting configuration rejection;
- unsafe URL, missing key, invalid model, timeout, HTTP/rate-limit, malformed envelope, schema-invalid output, and bounded repair;
- versioned extraction prompt identity and fingerprint;
- status response closure and secret redaction;
- arbitrary synthetic JD through a mock HTTP transport;
- ranking order/fingerprint/score invariance;
- no Provider dependency in Phase 11 evaluation.

Frontend tests cover:

- Provider status contract validation;
- mock, configured, and unavailable status presentation;
- arbitrary JD submission without loading a sample;
- stage-specific loading copy;
- recoverable Provider errors without secret or stack leakage.

Browser E2E uses a local mock OpenAI-compatible HTTP transport and disposable PostgreSQL/Qdrant state. It must not require an external credential or mutate the frozen Candidate source data. A live smoke is run only when a legitimate local credential is present and uses synthetic input.

## Documentation And Claims

README documents the generic OpenAI-compatible configuration, task ownership, mock behavior, arbitrary-JD flow, and safe local setup.

Allowed claim:

> The system implements an OpenAI-compatible Provider path for schema-first JD extraction and evidence-grounded explanation while LambdaMART remains the ranking owner.

Without a credentialed successful smoke, the repository must continue to state:

> Real-provider live smoke: NOT RUN — LOCAL PROVIDER CREDENTIAL REQUIRED.

Forbidden claims include production readiness, verified support for every compatible vendor, real users, real hiring accuracy, online improvement, provider-generated ranking, and unrestricted factual generation.

## Acceptance Gate

Phase 15 implementation passes only when:

- generic and mock configurations are both deterministic and fail closed;
- arbitrary JD completes the real-provider-compatible mock-transport path;
- Provider status is useful and contains no secret material;
- extraction prompts are versioned and fingerprinted;
- real Provider errors are bounded and recoverable in the UI;
- ranking invariance is verified;
- full backend and frontend gates pass;
- disposable browser E2E passes;
- secret/privacy scans pass;
- all frozen algorithm, Candidate Pool, Evidence, and Phase 11 paths have zero diff from `1d4a69bd317084e1486c273aec19dc35182b76cc`;
- documentation preserves the local-prototype and live-smoke limitations;
- no push is performed.
