# Portfolio Screenshot Plan

## Status and Integrity

This plan defines Phase 0.5 portfolio captures. The selected Phase 0.5B Matching Results screen is a design implementation, not evidence of matching behavior. It displays `Design Mock` and uses fictional, non-personal illustrative records; screenshots must not imply production usage, measured impact, or algorithm output.

## Capture Standard

- **Primary viewport:** 1440 × 1024 desktop.
- **Browser chrome:** excluded unless needed to prove local execution.
- **State:** one focused decision, no open debug overlays, no clipped text.
- **Content:** synthetic design personas and generic/public-style roles only; no real candidate personal data.
- **Label:** `Design Mock` for ideation; later screenshots use accurate current/planned labels.

## Priority 1 — Hero: Matching Results

### Screenshot purpose

Make the product legible in one frame as an evidence-aware ranking system rather than a résumé search tool.

### Technical capability it should prove

Ranked candidate comparison, feature-level decision evidence, project evidence, material risk, and the separation between ranking evidence and grounded explanation.

### Above the fold

- persistent product navigation;
- selected job, role direction, strategy, and run metadata;
- top three candidates with rank and overall score;
- primary reason, evidence strength, risk, and missing must-have;
- one selected candidate's evidence/feature detail;
- visible `Illustrative Data — Design Mock` during design phases.

### Must not appear

Fake uplift metrics, all candidates expanded, full résumés, raw JSON, multiple large charts, modal stacks, or an explanation presented as the ranking algorithm.

## Priority 2 — Candidate Profile: Project Evidence

### Screenshot purpose

Show that claimed skills and demonstrated project evidence are different product concepts.

### Technical capability it should prove

Skill-to-evidence traceability, project provenance, evidence gaps, profile completeness, and role-direction context.

### Above the fold

- candidate identity and target roles;
- locations and seniority;
- evidence coverage summary;
- two or three project evidence records linked to capabilities;
- one visible `Claim only` or partial-evidence state;
- restrained overclaim/evidence-gap risk.

### Must not appear

Private contact details, a universal candidate score, a decorative tag cloud, unsupported personality inference, or every profile field at once.

## Priority 3 — Agent Run: Pipeline Trace

### Screenshot purpose

Demonstrate that a ranking is produced through an inspectable pipeline rather than an opaque AI response.

### Technical capability it should prove

Stage status, timing, input/output summaries, version/config references, request/run correlation, and failure localization.

### Above the fold

- run ID, strategy, status, and job context;
- parse → retrieval → features → LTR → rerank → explanation trace;
- one expanded stage with concise input/output summary;
- clear separation of core execution from follow-on feedback/bad-case/eval events.

### Must not appear

Full prompt text, secrets, giant raw payloads, every downstream workflow shown as completed, or an animated novelty pipeline.

## Priority 4 — Bad Case Review: Recommendation Debugging

### Screenshot purpose

Show how a wrong recommendation becomes an attributable and testable product decision.

### Technical capability it should prove

FP/FN taxonomy, root-cause linkage, affected stage/feature, immutable source run, fix hypothesis, and validation plan.

### Above the fold

- observed mismatch and case classification;
- compact candidate/job/run context;
- root-cause evidence;
- affected feature or stage;
- proposed fix and `Not yet validated` state.

### Must not appear

Generic error logs, blame language about a candidate, a fix shown as successful without evaluation, or a wall of unprioritized labels.

## Priority 5 — Evaluation Dashboard: Strategy Comparison

### Screenshot purpose

Show disciplined local offline comparison without implying production impact.

### Technical capability it should prove

Dataset/configuration context, ranking metric comparison, explanation-quality separation, system latency, and bad-case slices.

### Above the fold

- dataset version, split, label policy, and limitations;
- selected strategies on a common comparison axis;
- ranking metrics grouped separately from explanation quality and latency;
- link from a metric slice to related bad cases;
- `Illustrative Data — Design Mock` until real evaluations exist.

### Must not appear

Online uplift, business impact, revenue/users, unlabeled percentages, cherry-picked winners, explanation presented as ranking improvement, or unrelated dashboard widgets.

## Visual Exploration Captures

Phase 0.5A produced exactly three Matching Results visual directions. They remain decision artifacts, not implementation screenshots. Each direction kept the same product truth while changing hierarchy, layout strategy, density, interaction framing, and data presentation.

The direction set explores:

- evidence-first talent intelligence;
- ranking and decision comparison;
- AI matching observability.

The user selected Evidence-first Talent Intelligence and requested a deliberate fusion with stronger ranking overview and a lightweight pipeline/decision trace. Phase 0.5B implemented only that fused Matching Results hero direction; Candidate Profile, Agent Run, Bad Case, and Eval remain screenshot plans rather than built pages.

## Capture Checklist

### Product truth

- [ ] Current and planned capability labels are accurate.
- [ ] Mock values are labeled `Illustrative Data — Design Mock`.
- [ ] No real candidate data, company-private data, or secret is visible.
- [ ] No production, user, traffic, revenue, or online-improvement claim appears.

### Information hierarchy

- [ ] The page purpose is clear within three seconds.
- [ ] The primary decision/action is visible above the fold.
- [ ] Job/candidate/run context is identifiable without reading every label.
- [ ] Ranking evidence is visually distinct from explanation.
- [ ] Risk includes a reason and is not communicated by color alone.

### Visual quality

- [ ] Capture is exactly 1440 × 1024 unless an exception is documented.
- [ ] Text is crisp, uncropped, and predominantly 14–16 px body size.
- [ ] No card nesting, excessive shadow, glassmorphism, or decorative gradient dominates.
- [ ] Rows, charts, and scores use aligned scales and restrained color.
- [ ] Focus/hover-only content is not required to understand the screenshot.

### Portfolio narrative

- [ ] The screenshot proves one technical idea, not the whole roadmap.
- [ ] Supporting annotation can explain current vs planned state.
- [ ] The five screenshots form a coherent story: rank → evidence → trace → debug → evaluate.
