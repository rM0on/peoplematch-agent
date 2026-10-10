# Decision Record: Recruiter Narrative Phase 2 Freeze

**Date:** 2026-10-08

**Decision:** CLOSED / NOT PASS for autonomous free-text Recruiter Narrative

**Status at decision time:** Accepted for project handoff; the next trusted product path was not yet complete. Later Fresh Trusted Top-3 validation passed with structured RecruiterProposition. This historical decision still closes autonomous free-text Narrative; see [current documentation index](../README.md).
**Scope:** Local synthetic PeopleMatch Agent experiments. No production or real-hiring claim.

## Problem and product objective

Recruiters need to understand quickly why a candidate merits review, which source-backed technical signal matters, what remains unknown, and what to verify first. The design principle was **facts constrained, expression free**. Free-text Qwen output was expected to communicate already-grounded evidence without inventing candidate experience, personal action, responsibility, ownership, technical decisions, scale, outcomes, or stronger job fit.

The core question was whether one model-generated narrative, even when supplied with typed `RecruiterProposition` and constrained references, could be trusted to preserve those epistemic limits automatically. Phase 2 evidence says **no**.

## Evidence and experiment route

The sequence retained evidence grounding, atomic facts, the V4 Claim Graph, V4.1 Decision Frame, V5 Hiring Context, native JSON Schema, strict Handle binding, typed `RecruiterPropositionV1`, provenance and candidate isolation. It then compared free verbalization with field-level Semantic Intent, Final Refinement, Interview Semantics, and one final short-triage convergence task. Blind semantic audit and older lexical Validator/Guard were observed only as diagnostics in the Proposition experiments; manual source-backed review was the primary semantic assessment.

| Archived batch | Development: supported / unsupported / uncertain | Development narratives with confirmed unsupported | Holdout: supported / unsupported / uncertain | Holdout narratives with confirmed unsupported |
| --- | --- | --- | --- | --- |
| Original baseline | 39 / 22 / 9 | 6/6 | not run | not run |
| Semantic Intent Recovered — best observed | 35 / 3 / 1 | 2/6 | 11 / 0 / 1 | 0/2 |
| Final Refinement | 46 / 11 / 4 | 6/6 | 16 / 3 / 1 | 2/2 |
| Interview Semantics Recovered | 34 / 10 / 3 | 6/6 | 15 / 5 / 1 | 1/2 |
| Final Convergence short triage | 24 / 6 / 3 | 4/6 | 8 / 3 / 1 | 2/2 |

The final convergence batch is `triage_phase2_final_20261008T0859Z`. Its frozen manifest, append-only JSONL and manual gold are in `backend/tests/fixtures/`. Across all eight synthetic samples: HTTP/native schema/Handle were 8/8, repair was 0, but manual review found 32 supported, 9 confirmed unsupported and 4 uncertain semantic items; 6/8 narratives had a confirmed unsupported item. The confirmed problems were five first-check scope leaks and four participation-scope presuppositions. The single sourced first-check topic was followed in only 1/8, while structured recommendation strength was respected in 8/8. Five of eight outputs were in English; several read like repeated Evidence summaries rather than useful recruiter briefings. The ranking values in the archived generation snapshots were unchanged, but this does **not** prove a newly executed end-to-end ranking run.

These small synthetic batches are descriptive engineering evidence, not statistically significant safety estimates. Different holdout scenarios are not a strict paired comparison. The best observed batch is a reference behavior, not a production release candidate; its current implementation module has subsequently changed, so the archived artifact is the authoritative comparison.

Primary pointers: `backend/tests/fixtures/recruiter_proposition_phase2_semantic_intent_recovered_20261007T0858Z.jsonl`, `backend/tests/fixtures/recruiter_proposition_phase2_semantic_intent_recovered_gold_v1.json`, `backend/tests/fixtures/triage_phase2_final_20261008T0859Z.manifest.json`, `backend/tests/fixtures/triage_phase2_final_20261008T0859Z.jsonl`, `backend/tests/fixtures/triage_phase2_final_20261008T0859Z_gold_v1.json`, and `docs/superpowers/plans/2026-10-08-recruiter-phase2-final-convergence.md`. Baseline, refinement, interview, failed-transport, tests, reports and other experiment files remain preserved in place.

## Why iteration stops

Native JSON Schema and Handle binding solved JSON shape and exact reference transport, **not** entailment of the final prose. Additional intent and interview layers did not monotonically improve either fidelity or product quality; later batches regressed from the best observed Semantic Intent Recovered result. Blind audit had meaningful signals but missed or misclassified natural-language propositions and is not a release gate. The older lexical Validator and Decision Frame Guard have false positives and coverage gaps relative to open Chinese recruiter language and are not a main release gate. A further prompt, intent, regex, or semantic-layer patch would repeat the same local-fix loop without evidence that autonomous free-text safety is attainable in this task. Phase 2 automatic Narrative iteration therefore ends irrespective of these artifacts being retained.

## Architecture decisions

| Component | Decision | Boundary |
| --- | --- | --- |
| Frozen extraction, Hybrid Retrieval, feature engineering, LambdaMART, optional frozen Cross-Encoder strategy, MatchRun, Evidence Grounding / ExplanationPlanV1 | **KEEP — existing trusted matching/explanation path** | Ranking owner remains LambdaMART under the configured frozen strategy; presentation never changes order, raw score or fingerprint. |
| `RecruiterPropositionV1` contract and canonical evidence-backed builder, provenance/source IDs, candidate ownership/isolation, recommendation strength, structured unknown and review semantics | **KEEP — trusted structured capability; planned integration into next recruiter-facing path** | Only canonical, source-traceable propositions may be presented as structured statements. This is implemented and tested in the experimental presentation modules, **not yet wired as the primary runtime Recruiter View**. Fresh Top-3 must validate it on fresh run evidence. |
| Shared OpenAI-compatible Provider, native JSON Schema, strict field-scoped Handle protocol | **KEEP — transport/structure capability** | Schema and Handle success establish shape and identity only; neither proves the prose is entailed. |
| Semantic Intent Recovered | **EXPERIMENTAL REFERENCE ONLY** | Best archived observed behavior, not an approved main-path free-text gate or a claim that the current module reproduces the archived version. |
| Final Refinement, `InterviewQuestionIntent`, requirement-verification experimental view and interview focus selection, final triage generation | **DEPRECATE FROM MAIN PATH; RETAIN AS EXPERIMENTAL HISTORY** | Do not compose these into the next main path or delete historical code/assets now. |
| Qwen free-text Recruiter Narrative V1–V5 / Proposition generation | **EXPERIMENTAL ONLY** | Optional human-review draft; no autonomous recruiter decision or trusted factual source. |
| Blind semantic auditor | **EXPERIMENTAL DIAGNOSTIC ONLY** | Its pass cannot release a narrative; its fail is a review signal, not a verified factual error. |
| V4 Claim Validator / V4.1 Decision Frame Guard and related lexical/modality rules | **LEGACY SHADOW DIAGNOSTICS ONLY for free-text Narrative** | Do not restore as the main Proposition or Narrative release gate; retain tests and history. This does not remove the existing, separate Phase 9 Evidence Grounding validation. |
| Existing V1/V2/V2.1 recruiter-narrative API routes | **EXPERIMENTAL SURFACES REQUIRING GOVERNANCE** | Current router mounts them; their presence must not be described as trusted auto-publication. Do not silently promote or delete them in this freeze. Any future product use requires explicit review/status labeling and authorization. |

**Trusted target data flow for the next phase (planned, not yet fully integrated):** configured real extraction → Hybrid Retrieval → frozen features → LambdaMART with optional Cross-Encoder only under the frozen strategy → immutable MatchRun → selected Evidence and grounding → canonical RecruiterProposition → structured recruiter-facing evidence/review/unknown fields. Existing Phase 9 grounded explanation remains a separate trusted artifact under its own contract; it is not proof that newly generated free-text Recruiter Narrative is safe.

**Optional experimental side path:** after the trusted facts exist, Qwen may draft recruiter prose via native schema and Handle binding. The output is marked **“Requires Human Review / 需人工复核”**, visually and contractually separate from sourced propositions. A draft failure or absence cannot change ranking, MatchRun, proposition facts, or the acceptance of the trusted Top-3 chain. No automatic publishing, hiring decision, probability claim, or fact-source promotion is permitted. A human must check substantive claims and approve any external use; a Schema/Handle/auditor/legacy-guard PASS is insufficient approval.

## Recruiter View and documentation boundary

The future Recruiter View should answer in about ten seconds: why review, one or a few key signals, material unknowns, and the first useful verification target. Those trusted items should come from source-backed structured propositions and evidence, presented as normal recruiter information rather than a schema/debug dump. Source links and precise evidence details remain accessible for review. If the optional draft is shown, it must carry the human-review/experimental label and cannot visually masquerade as verified candidate fact. No UI change is authorized by this record.

The next README/architecture/portfolio documentation pass may claim **evidence-grounded structured recruiter propositions**, deterministic provenance and candidate isolation, native structured output, real-provider controlled experiments, a manually annotated semantic gold set, observed semantic-strength drift in free text, human-review draft status, and ranking independence. It must not claim narrative semantic safety solved, fully grounded free generation, autonomous recruiter reasoning, production readiness, zero hallucination, or real-world hiring impact. Existing README and portfolio content are not changed in this freeze; reconcile them only in a separately approved documentation/product phase.

## Handoff

Fresh Top-3 is **unblocked for the trusted main chain**, not for autonomous free-text Narrative. The next approved work item is the proposed `docs/superpowers/plans/2026-10-08-fresh-top3-trusted-chain.md`. It must use a fresh synthetic JD and new MatchRun; prove 3/3 candidate evidence/proposition lineage, candidate isolation, stable ranking order/raw scores/fingerprint, explicit real-vs-mock provider provenance, and useful source-backed review/unknown/first-check fields. An optional Narrative Draft is separately labelled and nonblocking. No Fresh Top-3 run or UI/portfolio implementation occurs as part of this decision record.
