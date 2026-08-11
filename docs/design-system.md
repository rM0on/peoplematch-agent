# Design System Direction

## Status

Phase 0.5A established the semantic rules. For Phase 0.5B, the user selected the Evidence-first fusion: warm neutral work surfaces, a restrained teal accent, compact feature indicators, textual evidence states, and muted amber for review risk. These values are an implementation baseline for the Matching Results design mock, not a complete production token library.

The UI uses an Inter-compatible system sans stack and a system monospace stack for scores and run metadata. Main panels use approximately 10 px radius, hairline neutral borders, and little to no shadow. Phosphor's rounded line icon family supplies interface icons; custom CSS or handwritten SVG substitutes are not used.

## Visual Principles

### Evidence before assertion

Project sources, requirement coverage, and feature contribution receive more visual weight than generated explanation prose. A high score never replaces evidence.

### Comparison before decoration

Align values to support rank comparison. Use spacing, typography, and common baselines before adding containers or color.

### Calm precision

Risk and failure are visible without making a candidate look dangerous. Technical metadata is precise without turning the whole product into a terminal.

### Progressive disclosure

First viewport: context, rank, reason, evidence strength, material risk. Detail: feature diagnostics, citations, explanation, and raw technical records.

### Honest state

Loading is not empty, unavailable is not zero, design mock values are not results, and explanation quality is not ranking quality.

## Typography

The system uses one Inter-compatible UI sans stack and one system monospace stack. This keeps the local prototype dependency-light while maintaining the selected direction's calm, technical hierarchy.

| Role | Intended scale | Use |
|---|---|---|
| Display / Page Title | 28–36 px, compact line height | Page identity and one-line decision context |
| Section Heading | 20–24 px | Major page regions |
| Card/Row Heading | 16–18 px | Candidate, job, stage, or diagnosis name |
| Body | 14–16 px, 1.45–1.6 line height | Primary product content |
| Secondary | 14 px | Supporting explanation and labels |
| Metric | 24–40 px, tabular numerals | Overall score or a small number of key metrics |
| Mono / Technical | 12–13 px | Run ID, strategy version, latency, request ID |

Twelve-pixel text is reserved for short technical metadata and compact labels. It must not become the default body size. Long explanations target a readable 55–65 character line length.

## Spacing

Use a 4 px base rhythm with a deliberately small set of practical intervals:

- 8 px for tight label/icon relationships;
- 12–16 px inside compact controls and rows;
- 20–24 px between related groups;
- 32 px between sections within a page;
- 48–64 px for major page separation.

Spacing creates grouping before borders. Dense comparison rows may be compact, but evidence and explanation text require more vertical breathing room.

## Surface Hierarchy

1. **Background:** application canvas; quiet neutral tone.
2. **Surface:** default content plane; often the same plane as the canvas with grouping and dividers.
3. **Elevated Surface:** drawer, selected detail, sticky context, or overlay only.

Do not make every section a card. Use one shared surface for lists and comparisons, separated by rows and section dividers. Nested cards are prohibited unless the inner object is independently movable/actionable.

## Semantic Color Roles

Exact color values are intentionally deferred. The system requires these semantic roles:

| Role | Meaning |
|---|---|
| Background | Main application canvas |
| Surface | Primary reading/comparison surface |
| Elevated Surface | Selected detail, drawer, or overlay |
| Primary Text | Main labels and decisions |
| Secondary Text | Supporting explanations |
| Muted | Low-emphasis metadata and disabled context |
| Border | Quiet structure and row separation |
| Accent | Selection, links, primary actions, overall score emphasis |
| Success | Completed/healthy and substantiated positive state |
| Warning | Review needed; medium risk or partial evidence |
| Danger | Material mismatch/failure; restrained use |
| Info | Neutral system context and provenance |

Match strength (`Strong`, `Moderate`, `Weak`) and risk (`Low`, `Medium`, `High`) are separate semantic scales. They must not share identical colors or visual grammar. Feature scores use one accent family rather than rainbow hues.

All meaningful foreground/background pairings must meet WCAG 2.2 AA. Color is always reinforced with text and, where useful, shape/iconography.

## Radius

- Small controls and compact badges: approximately 6–8 px.
- Panels, selected detail, and drawers: approximately 10–12 px.
- Pills: status, filters, or short categorical values only.

Large decorative radii are not the default. A shortlist table or evidence map should read as a structured work surface, not a collection of floating bubbles.

## Borders and Dividers

Use 1 px low-contrast borders. Dividers are preferred for list rows and page sections. Strong borders identify selection or keyboard focus, not ordinary containment. Dashed borders are reserved for empty/drop states and never imply evidence uncertainty by themselves.

## Elevation

Use no more than two practical elevation levels:

- **Level 0:** page and normal grouped content.
- **Level 1:** sticky detail, drawer, popover, or temporarily raised selection.

Shadows remain soft and subtle. They do not separate every card or create glassmorphism.

## Score Treatments

### Overall Ranking Score

- Highest emphasis within a candidate summary after rank/name.
- Numeric value plus qualitative band.
- Always contextualized by job, run, and strategy.
- May use a compact ring, numeral block, or anchored bar depending on selected direction; never a decorative gauge.

### Component Feature Scores

- Aligned horizontal indicators on a shared scale.
- Same accent family; strength comes from length/value, not feature-specific colors.
- Labels remain readable without hover.
- Retrieval diagnostics (semantic/sparse) form a secondary group.

### Comparison

- Two or more candidates use aligned columns or small multiples with identical axes.
- Sorting changes are explicit and keyboard accessible.
- A value without its denominator/scale is not shown.

## Risk Treatments

| Severity | Visual intent | Required content |
|---|---|---|
| Low | Quiet neutral/success indicator | Category and concise reason |
| Medium | Muted amber/warning indicator | Category, evidence basis, review action |
| High | Restrained danger indicator | Material requirement, evidence basis, match impact |

Risk appears as a badge plus a short reason, not a red score bar. High risk may add a left marker or icon, but never paints the entire candidate row red. `Risk` refers to match uncertainty or requirement conflict, not personal character.

## Evidence Treatments

### Evidence Chip

An evidence chip names a project/source and support status. It is actionable only when it opens a real evidence detail. Chips do not replace readable evidence text.

### Evidence List

Evidence rows align capability, support level, project, and provenance. `Claim only`, `Partial`, and `Demonstrated` are textual states with restrained visual distinction.

### Citation Detail

Source context opens in an anchored detail region, drawer, or sheet. It shows source type, excerpt/context, and the exact capability relationship. It never fabricates source links in design mocks.

## Component Architecture

The later implementation should compose accessible primitives into domain components:

| Layer | Planned components |
|---|---|
| Shell | AppShell, Sidebar, TopBar, PageHeader, SectionHeader |
| Primitive/status | ScoreBadge, ScoreBar, RiskBadge, EvidenceChip, Tooltip, InlineAlert |
| Data | DataTable, EvidenceList, FeatureBreakdown, MetricComparisonChart |
| Domain | MatchResultRow/Card, CandidateSummary, JobSummary, RunStep, TraceTimeline, BadCaseCard, StrategySelector |
| State/disclosure | LoadingSkeleton, EmptyState, ErrorState, Drawer, Sheet |

The component API should remain shadcn/ui-compatible: semantic variants, accessible states, forwardable composition, and local ownership. Phase 0.5A does not add shadcn/ui packages or components.

## Chart Principles

- Use charts only when they outperform a table or aligned labels.
- Strategy comparison favors aligned dot plots, grouped bars, or compact tables.
- Use line charts only for ordered run/time trends; never connect unrelated strategies.
- Use identical scales for comparisons and display exact values on focus/hover plus a table alternative.
- Ranking metrics, explanation quality, and latency remain in separate groups.
- Metric labels include `@K`, units, dataset/split, and strategy/configuration context.
- Radar charts, 3D charts, pie charts with many slices, and rainbow palettes are avoided.
- Any design mock chart carries `Illustrative Data — Design Mock`; no visualized value is reported as an experiment result.

## Interaction and Motion

Motion communicates selection or continuity, not AI spectacle. Use short transitions for row selection, drawer entry, and trace expansion. No looping gradient, pulsing score, or animated chart is required. Reduced-motion users receive immediate state changes.

## Content Conventions

- Use `Planned` for capabilities not implemented.
- Use `Design Mock` or `Illustrative Data` for visual exploration values.
- Use `Unavailable` for failed requests, not zero or empty.
- Use `No evidence found` rather than inferring absence of skill.
- Use `Why not top 1` only for comparative ranking evidence, not a generated personal critique.
