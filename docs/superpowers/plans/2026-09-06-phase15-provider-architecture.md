# Phase 15 Provider Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable arbitrary JD input through a generic OpenAI-compatible Provider configuration while preserving independent Extraction and Explanation domains, deterministic mock mode, frozen LambdaMART ranking, and Evidence-grounded output.

**Architecture:** Keep `ProfileExtractionService` and `ExplanationGenerationService` as separate domain owners. Both compose the existing `OpenAICompatibleChatProvider` through one provider-neutral configuration resolver; extraction remains a strict schema adapter and explanation remains a closed evidence-reference planner. Add versioned extraction prompt artifacts, a non-secret read-only Provider status API, and bounded frontend status/loading/error presentation.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, httpx, PostgreSQL, Qdrant, Next.js 16, React 19, TypeScript 5, Vitest, Playwright, Docker Compose.

## Global Constraints

- Baseline implementation commit: `c21343e567e6f88694c2f35161d6f427175b0f74`.
- Preserve Phase 11 dataset, labels, query splits, contracts, manifests, selected artifacts, metrics, and results.
- Preserve the original 48 Candidate Profiles and frozen Candidate Pool source data.
- Preserve Retrieval behavior, Feature Engineering semantics/order/fingerprint, LambdaMART model/scoring, Cross-Encoder experiment, MatchRun ranking ownership, and Evidence contracts.
- Keep Extraction and Explanation as independent domain interfaces; do not create a universal two-method `LLMProvider`.
- Keep deterministic mock as the default for tests and local demos; never silently fall back from real mode to mock.
- Never expose, log, fingerprint, persist, render, or return an API key or raw upstream payload.
- Real Provider configuration requires a credential-free HTTPS URL; network-free tests inject `httpx.MockTransport` rather than weakening production validation.
- The existing `explanation_prompt_v1.txt`, explanation plan schema, grounding, and deterministic rendering remain unchanged.
- Use npm because `frontend/package-lock.json` is present; frontend final verification uses Node 22 LTS.
- Use RED first for every changed behavior and observe a meaningful failure before implementation.
- Do not push.

---

### Task 1: Provider-neutral configuration resolver

**Files:**
- Create: `backend/app/services/llm/__init__.py`
- Create: `backend/app/services/llm/configuration.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/services/explanation/generation/factory.py`
- Modify: `backend/app/services/profile_extraction/factory.py`
- Modify: `.env.example`
- Modify: `docker-compose.yml`
- Create: `backend/tests/test_phase15_provider_configuration.py`
- Modify: `backend/tests/test_phase12_real_extraction_provider.py`
- Modify: `backend/tests/test_explanation_openai_compatible_provider.py`

**Interfaces:**
- Produces: `ProviderMode`, `ProviderTask`, `ResolvedProviderSelection`, `resolve_provider_selection(settings, task)`.
- Consumes: existing `Settings`, `OpenAICompatibleChatProvider`, domain-specific factories, and `ExplanationProviderConfigurationError`.
- `ResolvedProviderSelection` contains `mode`, `selector`, `provider_name`, `base_url`, `model`, and an API key stored with `repr=False`; it exposes a non-secret deterministic `configuration_fingerprint`.

- [ ] **Step 1: Write RED tests for generic configuration and closed selectors**

```python
def test_generic_openai_compatible_settings_feed_both_domain_factories():
    settings = Settings(
        _env_file=None,
        extraction_provider="openai_compatible",
        explanation_provider="openai_compatible",
        llm_base_url="https://provider.example/v1",
        llm_model="provider-model",
        llm_api_key="phase15-private-key",
    )
    extraction = resolve_provider_selection(settings, ProviderTask.EXTRACTION)
    explanation = resolve_provider_selection(settings, ProviderTask.EXPLANATION)
    assert extraction.mode is ProviderMode.OPENAI_COMPATIBLE
    assert explanation.mode is ProviderMode.OPENAI_COMPATIBLE
    assert extraction.model == explanation.model == "provider-model"
    assert "phase15-private-key" not in repr(extraction)


def test_deepseek_alias_uses_legacy_values_only_when_generic_values_are_absent():
    settings = Settings(
        _env_file=None,
        extraction_provider="deepseek",
        explanation_deepseek_base_url="https://api.deepseek.example/v1",
        explanation_deepseek_model="deepseek-chat",
        explanation_deepseek_api_key="phase15-private-key",
    )
    resolved = resolve_provider_selection(settings, ProviderTask.EXTRACTION)
    assert resolved.mode is ProviderMode.OPENAI_COMPATIBLE
    assert resolved.provider_name == "deepseek"


@pytest.mark.parametrize("selector", ["", "auto", "openai", "unknown"])
def test_unknown_provider_selectors_fail_closed(selector):
    with pytest.raises(ExplanationProviderConfigurationError):
        resolve_provider_selection(
            Settings(_env_file=None, extraction_provider=selector),
            ProviderTask.EXTRACTION,
        )


def test_conflicting_generic_and_legacy_transport_values_fail_closed():
    settings = Settings(
        _env_file=None,
        extraction_provider="deepseek",
        llm_model="generic-model",
        explanation_deepseek_model="different-legacy-model",
    )
    with pytest.raises(ExplanationProviderConfigurationError, match="conflict"):
        resolve_provider_selection(settings, ProviderTask.EXTRACTION)
```

- [ ] **Step 2: Run focused tests and capture meaningful RED**

Run:

```powershell
backend/.venv/Scripts/python.exe -m pytest backend/tests/test_phase15_provider_configuration.py backend/tests/test_phase12_real_extraction_provider.py backend/tests/test_explanation_openai_compatible_provider.py -q
```

Expected: new tests fail because `app.services.llm.configuration` and generic settings do not exist; existing Phase 12 tests remain otherwise valid.

- [ ] **Step 3: Implement the closed resolver and generic settings**

Use this contract shape in `configuration.py`:

```python
class ProviderMode(str, Enum):
    MOCK = "mock"
    OPENAI_COMPATIBLE = "openai_compatible"


class ProviderTask(str, Enum):
    EXTRACTION = "extraction"
    EXPLANATION = "explanation"


@dataclass(frozen=True)
class ResolvedProviderSelection:
    mode: ProviderMode
    selector: str
    provider_name: str
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = field(default=None, repr=False)
    configuration_fingerprint: str | None = None
```

The resolver must:

1. return a closed mock selection without reading transport credentials;
2. accept `openai_compatible` and compatibility alias `deepseek`;
3. prefer generic values only when legacy values are absent or identical;
4. reject conflicting generic/legacy values;
5. validate HTTPS URL, safe model, and non-empty key before constructing transport;
6. fingerprint only provider name, normalized URL, model, and task timeout.

Add optional `llm_base_url`, `llm_model`, and `llm_api_key` fields to `Settings`. Keep the existing task-specific timeout/token settings and DeepSeek-prefixed compatibility fields.

- [ ] **Step 4: Update both factories to consume the resolver**

`build_profile_extraction_provider()` returns the existing domain adapter and `ProviderDescriptor`. `build_explanation_provider()` returns the existing explanation transport. Neither factory may inspect environment variables directly or call the other domain factory.

- [ ] **Step 5: Update Compose and `.env.example` without credentials**

Document and forward:

```dotenv
EXTRACTION_PROVIDER=mock
EXPLANATION_PROVIDER=mock
LLM_BASE_URL=
LLM_MODEL=
LLM_API_KEY=
```

Keep the DeepSeek-prefixed variables under an explicitly marked compatibility section. Do not put example tokens or personal endpoints in tracked files.

- [ ] **Step 6: Run Task 1 GREEN**

Run the focused command from Step 2. Expected: all selected tests pass, with no network call.

---

### Task 2: Versioned extraction prompt artifacts and provenance

**Files:**
- Create: `backend/app/services/profile_extraction/prompt_assets/candidate_extraction_prompt_v1.txt`
- Create: `backend/app/services/profile_extraction/prompt_assets/job_extraction_prompt_v1.txt`
- Modify: `backend/app/services/profile_extraction/prompts.py`
- Modify: `backend/app/services/profile_extraction/provider.py`
- Modify: `backend/app/services/profile_extraction/parser.py`
- Modify: `backend/app/schemas/extraction.py`
- Create: `backend/tests/test_phase15_extraction_prompt_contract.py`
- Modify: `backend/tests/test_extraction_parser.py`
- Modify: `backend/tests/test_extraction_api.py`
- Modify: `frontend/src/types/demo.ts`
- Modify: `frontend/src/lib/demo-api.ts`
- Modify: `frontend/src/lib/demo-api.test.ts`

**Interfaces:**
- Produces: `PromptSpec.prompt_version`, `PromptSpec.prompt_fingerprint`, `load_extraction_prompt_v1(task)`.
- Extends: `ProviderRequest` and API `ExtractionMetadata` with `prompt_version` and `prompt_fingerprint`.
- Preserves: existing output draft schemas and validation behavior.

- [ ] **Step 1: Write RED tests for immutable prompt identity**

```python
def test_candidate_and_job_prompt_artifacts_are_distinct_versioned_and_hash_pinned():
    candidate = load_extraction_prompt_v1(ExtractionTask.CANDIDATE)
    job = load_extraction_prompt_v1(ExtractionTask.JOB)
    assert candidate.version == "candidate_extraction_prompt_v1"
    assert job.version == "job_extraction_prompt_v1"
    assert candidate.fingerprint != job.fingerprint
    assert re.fullmatch(r"[a-f0-9]{64}", candidate.fingerprint)


def test_prompt_fingerprint_covers_system_instruction_and_output_contract():
    prompt = build_job_prompt("synthetic source " * 10)
    expected = canonical_fingerprint({
        "prompt_version": prompt.prompt_version,
        "system_message": prompt.system_message,
        "output_contract": prompt.output_contract,
    })
    assert prompt.prompt_fingerprint == expected
```

Also assert prompt files contain the untrusted-input, no-browsing, JSON-only, source-supported, and no-invention requirements.

- [ ] **Step 2: Run focused prompt tests and observe RED**

```powershell
backend/.venv/Scripts/python.exe -m pytest backend/tests/test_phase15_extraction_prompt_contract.py backend/tests/test_extraction_parser.py backend/tests/test_extraction_api.py -q
```

Expected: failures show missing prompt artifacts/provenance fields, not syntax or fixture errors.

- [ ] **Step 3: Move the extraction instructions into two text artifacts**

Both artifacts retain the current security semantics. Candidate and Job files differ only where their task wording needs to be explicit. `prompts.py` reads UTF-8 files, rejects missing/empty content, and fingerprints the artifact plus the exact Pydantic JSON schema.

- [ ] **Step 4: Propagate trusted prompt provenance**

Add these closed fields:

```python
class ExtractionMetadata(ContractModel):
    provider: str
    provider_kind: str
    prompt_version: str = Field(pattern=r"^(candidate|job)_extraction_prompt_v1$")
    prompt_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    attempts: int = Field(ge=1, le=2)
    repaired: bool
    persisted: bool
    input_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
```

The parser sources both fields from the server-built `PromptSpec`, never from Provider output. Update frontend runtime validation and fixtures to require the fields.

- [ ] **Step 5: Run Task 2 GREEN**

Run backend prompt/parser/API tests and `npm test -- --run src/lib/demo-api.test.ts`. Expected: all pass.

---

### Task 3: Read-only Provider status API

**Files:**
- Create: `backend/app/schemas/provider_status.py`
- Create: `backend/app/services/llm/status.py`
- Create: `backend/app/api/routes/provider_status.py`
- Modify: `backend/app/api/router.py`
- Create: `backend/tests/test_phase15_provider_status.py`

**Interfaces:**
- Produces: `GET /api/v1/system/ai-provider-status` returning `ApiResponse[AIProviderStatusData]`.
- Consumes: `Settings` and the pure configuration resolver only.
- Does not instantiate an HTTP client, call a Provider, load embeddings, or touch a database.

- [ ] **Step 1: Write RED contract/API tests**

```python
def test_mock_status_is_ready_but_arbitrary_input_is_not_supported(client):
    response = client.get("/api/v1/system/ai-provider-status")
    assert response.status_code == 200
    extraction = response.json()["data"]["extraction"]
    assert extraction == {
        "task": "extraction",
        "mode": "mock",
        "configured": True,
        "provider_name": "deterministic_mock",
        "configured_model": None,
        "arbitrary_input_supported": False,
    }


def test_status_never_returns_secret_url_prompt_or_raw_payload(client, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "must-not-leak")
    payload = client.get("/api/v1/system/ai-provider-status").text
    for forbidden in ("must-not-leak", "Authorization", "raw_prompt", "base_url"):
        assert forbidden not in payload
```

Add tests for configured generic mode, incomplete generic mode, and independent mixed modes.

- [ ] **Step 2: Run status tests and observe RED**

```powershell
backend/.venv/Scripts/python.exe -m pytest backend/tests/test_phase15_provider_status.py -q
```

Expected: 404 or import failure because the endpoint/schema do not exist.

- [ ] **Step 3: Implement closed status schemas and projection**

Use `Literal`/enum fields only. A configured real mode reports `provider_name` and safe model; incomplete mode reports `configured=false` without returning the missing value or validation exception text. The endpoint is an inspection projection, not a connectivity probe.

- [ ] **Step 4: Run Task 3 GREEN and health regression**

```powershell
backend/.venv/Scripts/python.exe -m pytest backend/tests/test_phase15_provider_status.py backend/tests/test_health.py -q
```

Expected: PASS and `/health` remains independent of Provider configuration.

---

### Task 4: Provider error taxonomy and secret-safe mapping

**Files:**
- Modify: `backend/app/services/explanation/generation/provider.py`
- Modify: `backend/app/services/explanation/generation/openai_compatible.py`
- Modify: `backend/app/services/profile_extraction/openai_compatible.py`
- Modify: `backend/app/exceptions.py`
- Modify: `backend/tests/test_explanation_openai_compatible_provider.py`
- Modify: `backend/tests/test_phase12_real_extraction_provider.py`
- Create: `backend/tests/test_phase15_provider_error_contract.py`

**Interfaces:**
- Produces: transport-level `ExplanationProviderRateLimitError` and API-level `ProviderRateLimitError` with code `provider_rate_limited` and status 503.
- Preserves: existing timeout, transport, HTTP status, malformed response, and bounded response-size behavior.

- [ ] **Step 1: Write RED tests for rate limit and redaction**

```python
@pytest.mark.parametrize("status", [401, 403, 500, 503])
def test_upstream_http_error_does_not_expose_body_or_authorization(status):
    # MockTransport returns a body containing a fake key and stack text.
    # The raised exception contains only the numeric status.


def test_rate_limit_maps_to_closed_domain_error():
    # A 429 transport response becomes ProviderRateLimitError.
    # str(error) is the fixed safe message and has no Retry-After/body content.
```

Add timeout, malformed JSON, prose content, schema-invalid JSON, and retry-exhaustion assertions. Existing parser tests provide bounded repair evidence; do not add transport retries that would duplicate the domain retry loop.

- [ ] **Step 2: Run error tests and observe RED**

```powershell
backend/.venv/Scripts/python.exe -m pytest backend/tests/test_phase15_provider_error_contract.py backend/tests/test_phase12_real_extraction_provider.py backend/tests/test_explanation_openai_compatible_provider.py -q
```

- [ ] **Step 3: Add the minimal typed mapping**

The transport checks 429 before generic non-success handling. Extraction maps it to the closed domain exception. Explanation orchestration retains its immutable FAILED attempt audit and does not reveal the upstream response body.

- [ ] **Step 4: Run Task 4 GREEN**

Run the command from Step 2. Expected: all selected tests pass.

---

### Task 5: Provider status and arbitrary-JD frontend experience

**Files:**
- Create: `frontend/src/types/provider-status.ts`
- Create: `frontend/src/lib/provider-status-api.ts`
- Create: `frontend/src/lib/provider-status-api.test.ts`
- Create: `frontend/src/features/provider-status/provider-status-badge.tsx`
- Create: `frontend/src/features/provider-status/provider-status-badge.test.tsx`
- Modify: `frontend/src/features/matching-results/matching-results-screen.tsx`
- Modify: `frontend/src/features/matching-results/matching-results.module.css`
- Modify: `frontend/src/features/matching-results/matching-results.test.tsx`
- Modify: `frontend/src/lib/demo-api.ts`

**Interfaces:**
- Produces: runtime-validated `fetchAIProviderStatus()` and `<ProviderStatusBadge />`.
- Consumes: `/api/v1/system/ai-provider-status` and existing `runDemo({jobText,onStage})`.
- Preserves: JD-first workflow, sample as optional helper, Candidate Pool and ranking/result contracts.

- [ ] **Step 1: Write RED API contract tests**

```typescript
it("rejects provider status responses containing an unknown mode", async () => {
  mockFetch({ success: true, data: { extraction: { mode: "auto" } } });
  await expect(fetchAIProviderStatus()).rejects.toMatchObject({ code: "invalid_response" });
});

it("accepts independent extraction and explanation status", async () => {
  mockFetch(validMixedStatus);
  await expect(fetchAIProviderStatus()).resolves.toEqual(validMixedStatus.data);
});
```

- [ ] **Step 2: Write RED component/workflow tests**

```typescript
it("submits an arbitrary JD without loading the sample", async () => {
  await user.type(screen.getByLabelText("岗位描述文本"), arbitraryJDLongerThan60Chars);
  await user.click(screen.getByRole("button", { name: "开始推荐" }));
  expect(apiMocks.runDemo).toHaveBeenCalledWith(
    expect.objectContaining({ jobText: arbitraryJDLongerThan60Chars }),
  );
});

it("labels provider configuration honestly", async () => {
  providerMocks.fetchAIProviderStatus.mockResolvedValue(genericReadyStatus);
  render(<MatchingResultsScreen />);
  expect(await screen.findByText("OpenAI-compatible 已配置")).toBeTruthy();
  expect(screen.queryByText("已连接")).toBeNull();
});
```

Add assertions for mock limitations, incomplete real configuration, stage text, rate-limit error, retry action, and absence of raw Provider messages.

- [ ] **Step 3: Run focused frontend tests and observe RED**

```powershell
Set-Location frontend
npm test -- --run src/lib/provider-status-api.test.ts src/features/provider-status/provider-status-badge.test.tsx src/features/matching-results/matching-results.test.tsx
```

Expected: import/expectation failures for the new status contract and copy.

- [ ] **Step 4: Implement runtime validation and the read-only badge**

The badge uses three product states:

- `Deterministic Mock` — “仅支持已注册安全示例”；
- `OpenAI-compatible 已配置` — “支持任意岗位 JD”；
- `Real Provider 配置不完整` — setup guidance without names of missing secrets.

Status fetch failure must not disable the workbench; show “Provider 状态不可用” and let the actual request fail through its typed API path.

- [ ] **Step 5: Refine actual loading/error copy without inventing progress**

Map existing observable stages to:

```typescript
const stageCopy: Record<DemoStage, string> = {
  job: "正在理解岗位需求…",
  index: "正在准备候选检索…",
  ranking: "正在召回候选人并计算 LambdaMART 排序…",
  explanation: "正在生成证据约束解释…",
  complete: "推荐已完成",
};
```

Do not add a fake percentage or claim that retrieval and feature computation are independently observable when they still occur inside one MatchRun request.

- [ ] **Step 6: Run Task 5 GREEN**

Run the focused frontend command. Expected: PASS.

---

### Task 6: Arbitrary-JD real-provider-compatible integration and ranking invariance

**Files:**
- Create: `backend/tests/test_phase15_arbitrary_jd_pipeline.py`
- Create: `frontend/e2e/phase15_provider_app.py`
- Create: `frontend/e2e/phase15-provider.spec.ts`
- Create: `frontend/playwright.phase15.config.ts`
- Create: `frontend/e2e/run-phase15-e2e.ps1`
- Modify: `frontend/package.json`

**Interfaces:**
- Produces: a test-only ASGI entrypoint with injected `httpx.MockTransport` instances behind the real OpenAI-compatible adapter.
- Consumes: real Job parse API, MatchRun API, Explanation API, disposable PostgreSQL, isolated Qdrant collections, and frozen LTR artifact.
- Never permits: external network, production HTTP URL exceptions, frozen dataset writes, or Provider ownership of ranking.

- [ ] **Step 1: Write backend RED integration test for arbitrary JD**

Use a JD string that does not match any registered mock fixture. Inject an OpenAI-compatible transport whose HTTP response contains a valid `JobExtractionDraft`. Assert:

```python
assert parsed.extraction.provider_kind == "openai_compatible"
assert parsed.extraction.prompt_version == "job_extraction_prompt_v1"
assert parsed.draft.role_title == "AI 应用工程师"
assert private_key not in repr(parsed)
```

Then execute frozen MatchRun and explanation services against disposable dependencies and capture the result fingerprint before and after explanation:

```python
before = await match_runs.get(run_id)
await explanations.generate(run_id, requested_top_k=5, request_id="phase15-test")
after = await match_runs.get(run_id)
assert after.result_fingerprint == before.result_fingerprint
assert [(x.candidate_id, x.result_rank, x.ltr_score_raw) for x in after.results] == [
    (x.candidate_id, x.result_rank, x.ltr_score_raw) for x in before.results
]
```

- [ ] **Step 2: Run the new backend test and observe RED**

```powershell
backend/.venv/Scripts/python.exe -m pytest backend/tests/test_phase15_arbitrary_jd_pipeline.py -q
```

Expected: fail on missing generic configuration/prompt provenance/status behavior rather than ranking output.

- [ ] **Step 3: Build the test-only Provider entrypoint**

`phase15_provider_app.py` injects `httpx.MockTransport` into the existing `OpenAICompatibleChatProvider` for both task adapters. It returns:

- a valid source-supported synthetic Job extraction object for the unregistered arbitrary JD;
- valid evidence-reference plans generated from the actual closed Provider prompt evidence.

The entrypoint contains only synthetic data and is imported only by the Phase 15 Playwright configuration. It must not change production URL validation or runtime factories.

- [ ] **Step 4: Write Browser E2E before enabling the test entrypoint**

The browser test must:

1. load `/` without clicking “加载示例 JD”;
2. confirm `OpenAI-compatible 已配置`;
3. type an arbitrary Chinese JD containing Python, RAG, LLM Agent, and FastAPI;
4. click “开始推荐”;
5. observe all bounded progress states;
6. receive Top-K results and distinct evidence-backed candidate sections;
7. verify each explanation contains only response Evidence refs;
8. fetch the persisted MatchRun and prove order/fingerprint/raw scores match the create response;
9. exercise a typed Provider failure and verify no fake key/upstream body appears;
10. record zero page/console errors.

- [ ] **Step 5: Run disposable Phase 15 E2E to GREEN**

```powershell
Set-Location frontend
npm run test:e2e:phase15
```

The PowerShell runner must require a database named with a new `peoplematch_phase15_` prefix, apply migrations, seed the unchanged 48-person sandbox into that disposable database, use unique Qdrant collection names, and clean only those exact disposable resources. Expected: all Phase 15 tests pass with zero skipped required integration.

---

### Task 7: Documentation, regression, freeze audit, and checkpoint

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/development-roadmap.md`
- Modify: `docs/demo-guide.md`
- Modify: `docs/portfolio-evidence.md`
- Modify: `scripts/demo_doctor.py`
- Modify: `backend/tests/test_phase12_demo_doctor.py`

**Interfaces:**
- Documents: generic OpenAI-compatible settings, independent domain responsibilities, arbitrary-JD behavior, mock limitation, live-smoke status, and ranking ownership.
- Preserves: local-prototype claim boundary and Phase 11 evidence.

- [ ] **Step 1: RED the doctor’s provider-neutral readiness projection**

Update tests so the doctor recognizes `LLM_API_KEY`, reports only configured/unconfigured state, and never emits its value, base URL, or model when unsafe.

- [ ] **Step 2: Implement minimal doctor and documentation updates**

README must show:

```dotenv
EXTRACTION_PROVIDER=openai_compatible
EXPLANATION_PROVIDER=openai_compatible
LLM_BASE_URL=https://your-provider.example/v1
LLM_MODEL=your-model-id
LLM_API_KEY=
```

It must state that compatibility depends on the provider implementing the used Chat Completions JSON-object behavior. It must not list unverified vendors as live-tested.

- [ ] **Step 3: Run focused Phase 15 suites**

```powershell
backend/.venv/Scripts/python.exe -m pytest backend/tests/test_phase15_provider_configuration.py backend/tests/test_phase15_extraction_prompt_contract.py backend/tests/test_phase15_provider_status.py backend/tests/test_phase15_provider_error_contract.py backend/tests/test_phase15_arbitrary_jd_pipeline.py backend/tests/test_phase12_real_extraction_provider.py backend/tests/test_explanation_openai_compatible_provider.py backend/tests/test_extraction_parser.py backend/tests/test_extraction_api.py backend/tests/test_phase12_demo_doctor.py -q

Set-Location frontend
npm test -- --run src/lib/provider-status-api.test.ts src/features/provider-status/provider-status-badge.test.tsx src/features/matching-results/matching-results.test.tsx src/lib/demo-api.test.ts
```

Expected: zero failures and zero skipped required Phase 15 tests.

- [ ] **Step 4: Run full current-source verification**

```powershell
backend/.venv/Scripts/python.exe -m pytest backend/tests -q
Set-Location frontend
npm test
npm run typecheck
npm run lint
npm run build
npm run test:e2e:phase15
```

Run frontend commands with Node 22 LTS. Record exact pass/fail/skip counts. Conditional integrations skipped by the full backend suite are not considered verified unless the Phase 15 disposable run covers them explicitly.

- [ ] **Step 5: Run privacy, secret, links, and formatting checks**

```powershell
git diff --check
git status --short --untracked-files=all
rg -n "(sk-[A-Za-z0-9_-]{16,}|Bearer [A-Za-z0-9._-]{12,}|BEGIN (RSA|OPENSSH|EC) PRIVATE KEY)" . -g '!frontend/node_modules/**' -g '!frontend/.next/**' -g '!backend/.venv/**'
```

Validate README relative links and confirm no raw Resume/JD, upstream response, credential, absolute personal path, cache, log, database, or test trace is tracked.

- [ ] **Step 6: Prove frozen paths are unchanged**

Compare against `c21343e567e6f88694c2f35161d6f427175b0f74` and require zero diff for:

```powershell
git diff c21343e -- data/eval data/dataset data/contracts artifacts
git diff c21343e -- backend/app/services/retrieval backend/app/services/features backend/app/services/ranking backend/app/services/cross_encoder
git diff c21343e -- backend/app/services/explanation/evidence backend/app/services/match_runs
git diff c21343e -- data/eval/query_splits.json data/eval/dataset_freeze_manifest.json
```

The Phase 15 implementation may modify explanation transport/configuration code, but not Evidence contracts, grounding, rendering, historical ownership, or selected evaluation artifacts. Any unexpected frozen-path diff is a blocker.

- [ ] **Step 7: Live Provider smoke decision**

If a legitimate Git-ignored local credential exists, run one minimal synthetic arbitrary-JD smoke and one grounded explanation smoke without printing or persisting the raw Provider response. Otherwise record exactly:

```text
REAL PROVIDER LIVE SMOKE = NOT RUN — LOCAL PROVIDER CREDENTIAL REQUIRED
```

Mock-transport verification must never be called a live-provider PASS.

- [ ] **Step 8: Review actual code and product behavior**

Review configuration resolution, secret handling, prompt provenance, status closure, Provider lifecycle, retry ownership, ranking invariance, frontend status accuracy, error recovery, and claim wording. Classify unresolved findings as BLOCKER/MAJOR/MINOR and close all integrity findings before checkpoint.

- [ ] **Step 9: Audit final diff and create one implementation checkpoint**

```powershell
git status --short --untracked-files=all
git diff --name-only c21343e
git diff --stat c21343e
git diff --check
git diff c21343e
git add -- .env.example docker-compose.yml README.md docs/architecture.md docs/development-roadmap.md docs/demo-guide.md docs/portfolio-evidence.md scripts/demo_doctor.py backend/app/core/config.py backend/app/exceptions.py backend/app/api/router.py backend/app/api/routes/provider_status.py backend/app/schemas/extraction.py backend/app/schemas/provider_status.py backend/app/services/llm backend/app/services/profile_extraction backend/app/services/explanation/generation/factory.py backend/app/services/explanation/generation/openai_compatible.py backend/app/services/explanation/generation/provider.py backend/tests/test_phase15_provider_configuration.py backend/tests/test_phase15_extraction_prompt_contract.py backend/tests/test_phase15_provider_status.py backend/tests/test_phase15_provider_error_contract.py backend/tests/test_phase15_arbitrary_jd_pipeline.py backend/tests/test_phase12_real_extraction_provider.py backend/tests/test_explanation_openai_compatible_provider.py backend/tests/test_extraction_parser.py backend/tests/test_extraction_api.py backend/tests/test_phase12_demo_doctor.py frontend/package.json frontend/src/types/demo.ts frontend/src/types/provider-status.ts frontend/src/lib/demo-api.ts frontend/src/lib/demo-api.test.ts frontend/src/lib/provider-status-api.ts frontend/src/lib/provider-status-api.test.ts frontend/src/features/provider-status frontend/src/features/matching-results/matching-results-screen.tsx frontend/src/features/matching-results/matching-results.module.css frontend/src/features/matching-results/matching-results.test.tsx frontend/e2e/phase15_provider_app.py frontend/e2e/phase15-provider.spec.ts frontend/e2e/run-phase15-e2e.ps1 frontend/playwright.phase15.config.ts docs/superpowers/plans/2026-09-06-phase15-provider-architecture.md
git commit -m "feat: add provider-neutral llm runtime"
```

Do not include local `.env`, external responses, caches, Playwright traces, databases, model files, or screenshots containing secrets. Do not push.

- [ ] **Step 10: Post-commit verification**

```powershell
git status --short --untracked-files=all
git rev-parse HEAD
git log -3 --oneline
git show --stat --oneline HEAD
```

Require a clean working tree and report the implementation SHA, exact verification evidence, live-smoke limitation, and frozen-path proof.

## Principal Risks And Controls

| Risk | Control |
| --- | --- |
| Rebuilding an already existing Provider abstraction | Generalize configuration only; retain both domain protocols and one transport |
| Provider compatibility variance | Claim only the tested Chat Completions JSON-object contract; fail malformed responses closed |
| Secret leakage | `repr=False`, non-secret fingerprints, closed status schema, safe API errors, repository scan |
| Mock silently masking real failures | No fallback; selected real mode fails explicitly |
| Prompt drift without provenance | Versioned text files plus deterministic prompt/contract fingerprint |
| Fake loading progress | Show only stages observable from current orchestration |
| Personalized prose inventing facts | Provider selects closed Evidence refs; backend grounding/rendering stays authoritative |
| Explanation mutating ranking | Compare immutable MatchRun fingerprint/order/raw scores before and after generation |
| Phase 11 or model drift | Baseline path diff audit against `c21343e`; any unexpected change blocks commit |
| Misleading “connected” state | Status says “已配置”; no connectivity claim without an explicit live smoke |

## Acceptance Summary

- Generic and legacy Provider configuration are validated and secret-safe.
- Arbitrary JD succeeds through the OpenAI-compatible mock-transport integration without loading a registered sample.
- Mock mode remains deterministic and explicitly fixture-bounded.
- Extraction prompt version/fingerprint appears in trusted API metadata.
- Provider status is useful, read-only, network-free, and contains no secret material.
- Timeout/rate-limit/unavailable/invalid-output failures are typed and recoverable.
- Candidate explanations remain per-candidate Evidence-grounded projections; no free-form factual authority is added.
- LambdaMART order, score, and result fingerprint are invariant across explanation generation.
- Focused/full backend, frontend test/typecheck/lint/build, and disposable E2E pass.
- Phase 11, Candidate Pool, Retrieval, Feature Engineering, LambdaMART, CE, Evidence contracts, and Evaluation have zero unauthorized diff.
- Live Provider status is reported honestly according to credential availability.
- One implementation checkpoint is created; push remains NO.
