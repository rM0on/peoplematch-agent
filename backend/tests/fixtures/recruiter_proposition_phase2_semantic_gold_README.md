# RecruiterProposition Phase 2 semantic gold (synthetic, offline)

This is a frozen evaluation asset, not a product runtime fixture or a new model generation. It preserves the six final Qwen outputs from the Phase 2 closure experiment. The original six experiment JSON records were recovered from that run's local command transcript; they were **not** regenerated. All candidates, job contexts and evidence in the comparison fixture are synthetic.

Files:

- `recruiter_proposition_phase2_semantic_gold_v1.json`: exact six final Narrative texts and manually adjudicated semantic spans.
- `recruiter_proposition_phase2_historical_predictions_v1.json`: sanitized original experiment records, including blind-extractor atoms, auditor issues, handle selections, shadow diagnostics and timings. Full Provider HTTP payloads are not retained.
- `recruiter_proposition_phase2_provenance_v1.json`: frozen canonical Proposition objects, V2/V3 source facts, V4 source claims, selected evidence terms and ranking snapshots. Each source ID can be traced without the previous chat.

`scenario_id` is the identity key; `candidate_001` and `candidate_002` intentionally recur in different independent scenario groups. A gold item is addressed by `(scenario_id, field, index, quote)`. Its quote must occur exactly once within the paragraph. `supported` means the frozen Propositions support that meaning, `unsupported` means the prose adds semantic strength, and `uncertain` means this single-annotator record cannot reliably adjudicate the clause. An `uncertain` item is excluded from binary precision/recall, never silently counted safe. Audit labels are separate from the runtime Proposition contract. `unsupported_responsibility`, `unsupported_scale` and `unsupported_outcome` are valid audit labels but have zero confirmed instances in these six outputs.

Run from repository root in PowerShell, without any Provider request:

```powershell
$env:PYTHONPATH='backend;backend/tests'
backend/.venv/Scripts/python.exe backend/tests/semantic_gold_proposition_v1.py
backend/.venv/Scripts/python.exe -m pytest backend/tests/test_recruiter_proposition_semantic_gold_v1.py -q
```

The evaluator rebuilds the synthetic fixture and checks exact Proposition, fact, evidence and ranking provenance. It replays the archived blind atoms through the **unmodified** `semantic_audit_proposition_v1.py`; generator-selected handles are checked for transport integrity but are never treated as proof of prose entailment.

Metric unit: an independently labelled substantive semantic item. A blind atom detects an item if its literal quote in the same paragraph covers at least half the gold item's characters. Character coverage and exact-quote count are reported separately; this overlap measure is not exact span-boundary accuracy. Only issue codes that actually assert unsupported meaning count as unsupported-addition alerts. Missing topics, quote coverage and extraction gaps are reported as diagnostic errors, not automatic factual failures. Repeated or coreferential phrases and nine `uncertain` items make all numbers exploratory; this is one small, single-annotator synthetic dataset, not a statistically significant benchmark or a production release gate.

The current archived baseline is six failed paragraph-level audits despite valid HTTP, schema and handles. The evaluator's output is the authoritative recomputation; do not adjust gold labels in response to metric changes. If labels are changed after independent human review, version the dataset and record the adjudication rather than overwriting V1.
