# Frontend Product Design

## Document Status

- **Phase:** 0.5B — Selected UI Direction Implementation
- **Status:** Completed; Evidence-first fusion selected, implemented, and verified
- **Scope:** Implement the Matching Results hero screen as a frontend design mock. No matching business API or algorithm is implemented in this phase.
- **Data integrity:** Any values shown in visual exploration are `Illustrative Data — Design Mock`, not system output or evaluation results.

## Phase 0.5B Selected Direction

The selected direction is **Evidence-first Talent Intelligence**, refined as a deliberate fusion rather than copied verbatim:

- the primary frame remains a shortlist + selected-candidate detail split;
- `Why this rank`, `Project evidence`, `Demonstrated / Partial / Claim only`, and `Grounded explanation` carry the main hierarchy;
- the first viewport adds Final score, Skill fit, Evidence, Direction, Location, Seniority, Risk, and Missing must-have without turning every signal into a large card;
- `Why A ranks above B` is a compact adjacent-rank disclosure, not a second comparison dashboard;
- Parse → Retrieval → Features → LTR → Rerank → Explain appears as a lightweight stage strip, with simplified rerank impact inside the selected-candidate detail;
- the page remains a hiring decision surface rather than an observability console.

The `1440 × 1024` implementation target was derived from the selected Product Design visual reference. That source image was not retained because its illustrative copy included disallowed production/performance claims; the verified implementation capture is `screenshots/phase-0.5b-matching-results-1440x1024.png`.

## Design Goals

PeopleMatch Agent is an evidence-aware matching and recommendation console, not an ATS, recruiting CRM, résumé scorecard, or chatbot. Its interface must help a reviewer answer five questions in order:

1. What is being matched, under which strategy and run?
2. Why does one candidate rank above another?
3. Which project evidence supports each claimed capability?
4. Which gaps or constraints create decision risk?
5. If the recommendation is wrong, which stage should be investigated next?

The product should feel calm enough for hiring decisions and technical enough for ranking diagnostics. Information density is welcome when hierarchy remains obvious. The UI must never make a generated explanation look like the source of a ranking decision.

## Personas and Decision Needs

### Candidate / AI Builder

The candidate starts with a profile and moves toward role fit. The main needs are supported skills, target-role alignment, missing evidence, role-specific gaps, and concrete portfolio/profile improvements. The experience must not present inferred risk as a personality judgment.

### Recruiter / Founder / Hiring Team

The hiring reviewer starts with a job and moves toward a shortlist. The main needs are ranking comparison, must-have coverage, evidence credibility, role direction, constraints, interview questions, and an explanation of why a lower-ranked candidate is not first.

### Platform Operator

The operator starts with a run or reported mismatch and moves toward root cause. The main needs are stage trace, feature contribution, false-positive/false-negative classification, strategy comparison, reproducible evaluation context, and a proposed validation path.

## Information Architecture

The desktop product uses one stable left navigation with seven destinations:

- **Overview** — system orientation and recent work.
- **Profiles**
  - **Candidates** — candidate list and profile details.
  - **Jobs** — job list and profile details.
- **Matching** — job- or candidate-led ranking results.
- **Runs** — match execution trace and stage outputs.
- **Bad Cases** — attributed recommendation failures.
- **Evaluation** — offline strategy comparisons.

Settings, billing, teams, notifications, inbox, authentication, and ATS workflow are intentionally absent. Contextual actions live in the page that owns them: `Run match` on a Job Profile, `Inspect evidence` on Matching Results, and `Review bad case` on a run or result.

## Navigation Model

At 1440 px, the sidebar remains visible and reserves enough width for labels without competing with the main canvas. The top bar is contextual rather than global: breadcrumbs, current job/candidate/run, and at most two page actions. It is not a second full navigation system.

Navigation preserves three context keys when moving through the demo:

- selected job or candidate;
- active match run;
- active ranking strategy.

Deep links from a candidate result to evidence, run trace, or bad case keep a compact context strip so the user can return to the same shortlist position rather than reconstructing the workflow.

## Page Map and Hierarchy

### 1. Overview Dashboard

**Purpose:** explain the product and provide a launch point within ten seconds.

**First viewport:** concise product statement; local/system state; data readiness fields; recent run list; most recent evaluation context; current bad-case categories. Candidate, job, run, and bad-case counts are design fields only until real data exists.

**Progressive detail:** run history, evaluation notes, and failure slices appear below the first viewport or through destination links.

**Must not dominate:** vanity metrics, fake percentage improvement, large decorative charts, generic activity feeds, or marketing copy.

### 2. Candidate Profile

**Purpose:** separate identity and preferences from evidence-backed capability.

**Hierarchy:**

1. Identity, target roles, locations, and seniority.
2. Profile completeness and missing fields.
3. Project evidence — the primary body region.
4. Skills and AI tools linked to supporting projects.
5. Overclaim or evidence-gap risks with reasons.

Projects are grouped as evidence records, not decorative portfolio cards. Each project exposes the role, outcome context, source type, and the skills it supports. A claimed skill without evidence remains visible as `Claim only`; it is never silently promoted to demonstrated capability.

### 3. Job Profile

**Purpose:** establish the decision context before matching.

**Hierarchy:** company/role, location/work mode, seniority, product stage, and role direction appear before raw description text. Must-have requirements use stronger typographic priority and a dedicated group; nice-to-have items use quieter treatment. Evaluation focus explains what the shortlist should optimize for.

`Run match` is the primary action. The action describes the selected strategy and leads to a new run context; Phase 0.5A specifies the interaction only.

### 4. Matching Results

**Purpose:** make ranking decisions understandable without opening a sequence of modals. This is the product's primary demo and portfolio screen.

The page follows `overview → evidence → detail`:

1. **Run context:** job, strategy, timestamp/status, result count, and run identifier.
2. **Shortlist summary:** rank, overall score, primary reason, evidence strength, risk, and missing must-have for every candidate.
3. **Selected-candidate detail:** feature breakdown, cited evidence, gaps, grounded explanation, interview questions, and `Why not top 1` when applicable.

The shortlist and detail region share one screen. Desktop selection updates the adjacent or anchored detail region; it does not open a modal. Only the selected candidate expands to diagnostic depth.

### 5. Agent Run / Workflow

**Purpose:** show how a match was produced and where it failed.

The primary execution lane contains `parse_candidate`, `parse_job`, `hybrid_retrieve`, `feature_score`, `ltr_rank`, `cross_encoder_rerank`, and `llm_explain`. Feedback, bad-case review, and evaluation are linked follow-on events, not falsely implied as mandatory steps in every run.

Each stage shows status first, then latency, input/output summary, version/configuration reference, and error type. Raw payloads remain behind a disclosure or drawer. The visual model is an observability trace with causality and timing, not a checklist.

### 6. Bad Case Review

**Purpose:** turn a wrong recommendation into a testable improvement hypothesis.

The page reads left to right:

`Observed mismatch → FP/FN classification → evidence/root cause → affected stage or feature → proposed fix → validation plan`

Candidate and job context remain visible but subordinate to diagnosis. The original run is immutable and linked. A fix suggestion never claims success until a later offline evaluation validates it.

### 7. Evaluation Dashboard

**Purpose:** compare future strategies on one documented local dataset.

The page uses three explicit sections:

- **Ranking metrics:** Recall@K, Precision@K, NDCG@K, MRR, pairwise accuracy.
- **Explanation quality:** grounding/consistency measures, shown separately and never presented as ranking lift.
- **System latency:** stage and end-to-end local observations.

Dataset version, split, label policy, strategy configuration, and limitations appear above the comparison. The first comparison view favors aligned dot plots or a compact table over a collection of unrelated metric cards.

## Primary Workflows

### Candidate Workflow

`Candidate Profile → Evidence coverage → Matched Jobs → Match detail → Gaps and risks → Profile/portfolio next step`

The candidate does not see a global personal score. Fit is contextual to one job and supported by cited evidence.

### Recruiter Workflow

`Job Profile → Run match → Ranked shortlist → Compare evidence → Inspect candidate → Prepare interview questions`

Must-have gaps stay visible through the shortlist comparison so a high semantic score cannot hide a constraint failure.

### Platform Operator Workflow

`Run list → Run trace → Suspected stage → Bad-case review → Fix hypothesis → Evaluation comparison`

The operator can move from an observed result to the originating feature and configuration without losing run context.

## Demo Path

The primary 3–5 minute demo is:

1. **Overview:** establish that the product matches AI Builders using evidence and traceable ranking.
2. **Job Profile:** show role direction and the distinction between must-have and nice-to-have requirements.
3. **Run Match:** start from an explicit strategy; no hidden automatic workflow.
4. **Matching Results:** compare the top candidates and explain why rank 1 leads.
5. **Candidate Evidence Drill-down:** connect a claimed skill to project evidence and surface a gap.
6. **Agent Run Trace:** show which stages contributed to the result.
7. **Bad Case:** demonstrate how a false positive/negative becomes a root-cause hypothesis.
8. **Eval Strategy Comparison:** show how the hypothesis would later be evaluated on a fixed local dataset.

The demo uses forward links and a preserved run context. It does not return repeatedly to Overview or require more than one nested disclosure per page.

## Matching Results Structure

### Page Header

- Job title, role direction, location, and seniority.
- Strategy selector with a clear `Design Mock` label in design exploration.
- Run status, run ID, and generated-at metadata in monospace.
- One primary action: inspect the selected candidate or continue to run trace, depending on the chosen visual direction.

### Shortlist Summary

Every candidate summary exposes only:

- rank and overall ranking score;
- one primary fit reason;
- evidence strength;
- risk severity with reason count;
- missing must-have count or `none identified`;
- selection affordance.

Semantic and sparse scores are diagnostic retrieval signals, not headline scores. They appear in the comparison/detail layer, where users can understand their role.

### Selected Candidate Detail

Detail is organized into five ordered regions:

1. **Ranking evidence:** feature contribution and constraints.
2. **Project evidence:** source-backed skill-to-project relationships.
3. **Gaps and risk:** missing requirements, direction/location/seniority mismatch, overclaim risk.
4. **Grounded explanation:** narrative generated from existing ranking evidence; visually labeled as explanation, not scoring logic.
5. **Decision preparation:** interview questions and `Why not top 1` comparison for lower ranks.

The first viewport does not show raw JSON, full résumés, every score, model prompts, long explanation prose, or all candidates expanded.

## Score System

### Overall Ranking Score

The overall score receives the strongest numeric emphasis and is always paired with rank and a qualitative band (`Strong`, `Moderate`, `Weak`). It must identify the strategy/run that produced it. A score is not shown as candidate quality independent of a job.

### Component Feature Scores

Skill, evidence, direction, location, and seniority share one restrained visual encoding: compact aligned indicators on a common scale. Numeric values are available for comparison, but labels and evidence links carry equal importance. Semantic and sparse retrieval scores sit in a secondary diagnostic group.

Radar charts are not the default because area and angle comparison obscure close differences. A radar alternative is acceptable only in a single-candidate exploratory view, never for precise shortlist comparison.

### Penalties and Risk

Missing must-have, evidence gaps, and hard constraints use a separate negative/risk treatment. They do not reuse the positive score bar or subtract through unexplained red segments. Each penalty includes its affected requirement and the evidence or missing-evidence basis.

## Evidence Visualization

The default pattern is a readable skill-to-evidence map:

| Skill or capability | Support status | Project evidence | Source context |
|---|---|---|---|
| Capability label | Demonstrated / Partial / Claim only | One or more project records | Source type and excerpt location |

Project records may support several capabilities, but the UI groups relationships by the question the reviewer is asking: “what evidence supports this skill?” Network diagrams are avoided because they become unreadable with more than a few nodes.

Evidence strength is expressed with words and restrained indicators. `No evidence found` is a valid, visible state. Evidence citations open in a drawer or anchored detail region so the shortlist remains stable.

## Risk System

Risk is professional decision support, not a label on a person.

- **Low:** no material issue identified in the available profile; quiet neutral/success treatment.
- **Medium:** review needed; muted warning treatment and explicit reason.
- **High:** a material requirement or evidence conflict; restrained danger treatment, never a full red candidate row.

Supported categories are overclaim/evidence gap, missing requirement, role-direction mismatch, location mismatch, and seniority mismatch. Every risk includes category, severity, evidence basis, and impact on the current match. Tooltips explain the rule; they do not hide the reason.

## Design Language

The target is a professional AI recruiting SaaS control console with the precision of developer tooling and the judgment-oriented calm of talent intelligence software.

- **AI-native:** pipeline and provenance are visible, without decorative AI gradients.
- **Technical:** run IDs, strategies, stages, and versions are legible.
- **Trustworthy:** evidence and uncertainty are more prominent than generated prose.
- **Premium:** typography, spacing, and restraint create quality; shadows and glass effects do not.
- **Data-rich:** aligned comparison and progressive disclosure support density.

The interface avoids cyberpunk/neon styling, glassmorphism, card nesting, rainbow scores, chatbot framing, giant marketing heroes, and generic admin widgets.

## Component Taxonomy

Phase 0.5A plans components but implements none of them.

### Application Structure

`AppShell`, `Sidebar`, `TopBar`, `PageHeader`, `SectionHeader`.

### Data and Decision Primitives

`DataTable`, `ScoreBadge`, `ScoreBar`, `RiskBadge`, `EvidenceChip`, `EvidenceList`, `FeatureBreakdown`, `Tooltip`, `InlineAlert`.

### Domain Compositions

`MatchResultRow`, `MatchResultCard`, `CandidateSummary`, `JobSummary`, `RunStep`, `TraceTimeline`, `BadCaseCard`, `StrategySelector`, `MetricComparisonChart`.

### System States and Disclosure

`EmptyState`, `ErrorState`, `LoadingSkeleton`, `Drawer`, `Sheet`.

The later component system should be shadcn/ui-compatible: accessible primitives, semantic variants, composable slots, and project-owned domain composition rather than copied page templates.

## Responsive Strategy

- **Desktop, 1280 px and above:** persistent sidebar; shortlist and selected-candidate detail can coexist; 1440 × 1024 is the portfolio target.
- **Compact desktop/tablet, 768–1279 px:** sidebar becomes a rail or drawer; shortlist and detail stack; the job/run context remains sticky.
- **Mobile, below 768 px:** comparison becomes a ranked list with one selected detail below; secondary diagnostic columns move into disclosures; evidence and risk are never removed.

The desktop experience is primary. Mobile supports review and navigation, not a compressed imitation of every operator comparison tool.

## Loading, Empty, and Error States

| Page | Loading | Empty state and next step | Error and recovery |
|---|---|---|---|
| Overview | Skeleton for status, recent runs, and evaluation context | `No local product data yet` → create/review the first profile when that phase exists | Preserve available modules; retry failed source independently |
| Candidate Profile | Identity shell plus evidence-row skeletons | `No candidate profiles yet` → add a sandbox profile in a later phase | Identify failed section; preserve profile context; retry |
| Job Profile | Role context and requirement skeletons | `No job profiles yet` → add a public/sandbox job in a later phase | Keep last safe context; show request ID; retry |
| Matching Results | Stable job header plus ranked-row skeletons | `Select a job or candidate to begin matching` → open Profiles | Distinguish failed run from no matches; link to trace |
| Agent Run | Stage placeholders preserving order | `No match runs yet` → start from a Job Profile in a later phase | Mark the failed stage; expose error type and request ID |
| Bad Cases | Filter and diagnosis-shell skeletons | `No reviewed bad cases yet` → review a flagged result when available | Preserve filters; retry list or open immutable run |
| Evaluation | Strategy header and aligned-chart skeletons | `No evaluation runs yet` → configure a local evaluation in a later phase | Show dataset/config context; retry without fabricating values |

Empty states explain both why the page is empty and the next valid action. `Nothing here` is never sufficient. Loading states preserve final layout geometry; errors never become empty success.

## Accessibility

- Meet WCAG 2.2 AA contrast for text, controls, and meaningful chart marks.
- Every color-coded score or risk also has text, shape, or icon meaning.
- Maintain visible focus, logical tab order, skip navigation, and semantic landmarks.
- Data tables use real headers and row/column associations; selected rows expose state programmatically.
- Drawers and sheets trap and restore focus; Escape closes only dismissible overlays.
- Tooltips are supplemental. Critical score, evidence, and risk meaning remains visible without hover.
- Charts provide a textual/table alternative and do not rely on color alone.
- Respect reduced motion; trace progress does not require animation to communicate status.
