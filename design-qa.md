# Phase 0.5B Design QA

## Comparison target

- **Source visual truth:** Product Design visual reference used during QA; intentionally not retained in the repository because its illustrative copy included disallowed production/performance claims.
- **Implementation screenshot:** `screenshots/phase-0.5b-matching-results-1440x1024.png`
- **Local implementation:** `http://localhost:3001`
- **Viewport:** `1440 × 1024` CSS px
- **Device scale factor:** `1`
- **State:** Candidate A selected, adjacent-rank comparison collapsed, Rerank stage active, light color scheme, reduced motion

## Pixel and density normalization

- Source image: `1487 × 1058` px.
- Implementation capture: `1440 × 1024` px.
- Source and implementation have effectively the same aspect ratio. The source was visually normalized to the implementation frame at approximately `0.968×`; the implementation was captured at 1 CSS px = 1 image px. No browser chrome or surrounding canvas was included.

## Capture result

- HTTP status: `200`.
- Document width: `1440` CSS px; scroll width: `1440` CSS px.
- No horizontal overflow or overflowing child regions were detected.
- Final document height: `1035` CSS px; all first-viewport decision content and both actions remain visible in the `1440 × 1024` capture.
- Shortlist: `342 × 582` CSS px.
- Selected-candidate detail: `817 × 806` CSS px.
- Evidence rows: `63 / 63 / 63 / 62` CSS px, preserving readable title, summary, state, and skill tags.

## Full-view comparison evidence

The source and final implementation were opened together at original resolution. The implementation preserves the selected visual direction's core hierarchy:

1. persistent desktop navigation and job context;
2. Matching Results title and lightweight Parse → Retrieval → Features → LTR → Rerank → Explain strip;
3. shortlist + selected-detail split;
4. Final score, component features, risk, and missing must-have before explanation;
5. compact `Why Candidate A ranks above Candidate B` disclosure;
6. project evidence with `Demonstrated / Partial / Claim only` states;
7. visible decision trace, grounded explanation, and evidence action in the first viewport.

Important typography and evidence labels remained readable in the original-size full-view comparison, so a separate crop did not reveal additional fidelity information. Interaction state and layout boxes were checked directly in the browser at 1× density.

## Required fidelity surfaces

### Fonts and typography

The Inter-compatible system sans stack and system monospace metadata maintain the reference's technical, calm hierarchy. Page title, candidate identity, rank score, evidence title, risk labels, and explanatory copy remain distinct. Dense metadata is smaller than body copy but remains legible at the target viewport.

### Spacing and layout rhythm

The final pass keeps the 30/70 shortlist-detail emphasis selected for the Evidence-first fusion. Section dividers and whitespace provide grouping without nested-card overload. The complete decision sequence fits the first viewport without horizontal clipping.

### Colors and tokens

Warm neutral surfaces, restrained teal, muted amber, and quiet claim-only brown preserve the source direction. Positive evidence and risk do not share identical visual grammar, and all statuses retain text labels rather than relying on color alone.

### Image and icon fidelity

The target contains no product imagery. The implementation uses one consistent Phosphor line-icon family. The abstract source brand mark is represented by the existing PeopleMatch Sparkle mark; this remains a Phase 0.5 brand placeholder rather than a finalized logo claim.

### Copy and content

All candidates, job context, scores, evidence, and trace values are fictional illustrative design content. `Design Mock`, `Illustrative data only`, and `Illustrative data · Design Mock` remain visible. The implementation intentionally omits fake source URLs, commits, measured improvements, and production provenance that appeared in the visual direction reference. That reference was used only for layout comparison and was excluded from the final repository.

## Interaction and accessibility verification

- Candidate B selection updated the detail heading, Final score to `74`, and project evidence.
- `Why Candidate A ranks above Candidate B` changed `aria-expanded` from false to true and revealed the comparison summary.
- Selecting LTR changed `aria-pressed` to true and displayed the learned-ranking-stage note; Rerank was restored before final capture.
- Candidate focus state rendered a `2px solid rgb(21, 95, 87)` outline with `2px` offset.
- Candidate hover state changed the interactive foreground treatment without layout shift.
- No horizontal overflow was detected.
- Reduced-motion mode was used for capture.

## Browser console status

- Console errors: `0`.
- Uncaught page errors: `0`.
- Failed requests: `0`.
- Non-successful HTTP responses: `0`.
- Observed request origins: `http://localhost:3001` only.

## Comparison history

### Pass 1 — blocked

- **P2:** Selected-candidate detail ended at `y=1159`; Grounded explanation and actions were below the 1024px first viewport.
- **P2:** The development-mode Next indicator obscured the sidebar footer in the screenshot.
- **P2:** Browser console reported a missing `/favicon.ico` resource.

### Fixes

- Reduced only the excessive vertical padding and gaps in the page header, selected-candidate header, Why-this-rank section, and evidence rows.
- Kept evidence text, state labels, skill tags, and all decision sections; no product information was removed.
- Captured the built local preview instead of the development overlay.
- Added the PeopleMatch app icon route so browser resource loading is clean.

### Pass 2 — blocked

- Grounded explanation became fully visible, but the action footer still ended at `y=1046`.
- `/favicon.ico` was confirmed as the only console error.

### Pass 3 — passed

- Selected-candidate detail ends at `y=1023`; both actions end at `y=1022` and are fully visible.
- No horizontal overflow, console errors, page errors, failed requests, or non-successful responses remain.
- Candidate selection, comparison disclosure, pipeline selection, focus, and hover checks passed.

### Git closeout integrity pass — passed

- Refreshed the `1440 × 1024` screenshot after correcting rerank transitions and removing production/performance wording from visible design-mock content.
- Candidate A now shows `Retrieved #3 → Final #1`; Candidate C shows `Retrieved #2 → Final #3`, and the adjacent comparison reads in the actual ranking direction.
- `Illustrative data · Design Mock` remains visible at both `1440` and `720` CSS-pixel widths; the `720` viewport has no horizontal overflow.
- The skip link becomes visible on focus, and the inert Job context button was replaced by static context text.
- Playwright reported HTTP `200`, zero console/page errors, zero failed requests, and zero non-successful responses.
- The original visual exploration reference was excluded from the repository because its copy contained disallowed fictional production/performance claims; the final implementation screenshot contains no such claims.

## Remaining acceptable differences

- The implementation gives the evidence-detail region more width than the source to support the selected Evidence-first fusion and readable artifact summaries.
- The source uses a table with richer provenance metadata; the implementation uses an evidence list because Phase 0.5 has no real sources and must not fabricate provenance.
- The implementation keeps a compact candidate identity header and places decision trace beside the grounded explanation, reflecting the requested Ranking Console and Observability fusion.
- Exact text, scores, and project names differ because all implementation content is explicitly fictional design-mock data.

## Final result

passed

## Final verification gate

- `npm test`: **PASS** — 2 test files passed, 12 tests passed, 0 failed (Vitest 3.2.7).
- Closeout review added regression coverage for visible mock labeling, consistent rerank transitions, ranking-direction copy, skip navigation, and the removal of an inert control.

## Phase 0.5B Final Gate

READY FOR PHASE 1
