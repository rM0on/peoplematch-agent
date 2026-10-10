# Final portfolio screenshot set

This set was captured from running local frontend/backend services on synthetic sandbox data. It is presentation evidence, not production or real-user evidence.

| File | What it shows | Source |
| --- | --- | --- |
| `01-recruiter-view.png` | Top-3 recruiter triage, review action, core unknown | Persisted Fresh MatchRun `22326fc2-1766-4c3c-a8f0-2cc81f70849c` |
| `02-evidence-provenance.png` | Recruiter-facing claim opened to project/skill material and JD requirement | Same persisted Fresh MatchRun |
| `03-engineering-view.png` | Feature values, LTR raw score, fingerprint and run linkage | Same persisted Fresh MatchRun; raw score is not probability |
| `04-agent-run.png` | Persisted trace separated from derived explanation metadata | Same persisted Fresh MatchRun |
| `05-eval-dashboard.png` | Frozen synthetic Phase 11 R1/R2 comparison and caveats | `data/eval/phase11/runs/20260831T173246Z_test_corrected_final/report.json` |
| `06-bad-case-review.png` | Human feedback, evidence, analysis and planned action | Isolated disposable synthetic Phase 10 review fixture, **not** a Fresh Top-3 model failure |
| `responsive-recruiter-view-mobile.png` | Responsive proof | Same persisted Fresh MatchRun |

The six desktop images form the core story. The mobile image is supporting proof, not a core portfolio page. Candidate/Job Profile was omitted because it repeated the structured-data story without adding comparable product or algorithm evidence.

Re-capture commands (PowerShell, from `frontend`):

```powershell
npx playwright test --config=playwright.portfolio.config.ts
powershell -ExecutionPolicy Bypass -File e2e/run-portfolio-bad-case.ps1
```

The Bad Case command creates and drops only its named disposable test database. It does not write to the current development database. Do not use screenshots to imply real users, production traffic, online lift, autonomous hiring, or zero hallucination. Free-text Recruiter Narrative remains experimental and requires human review.
