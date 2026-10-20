# PeopleMatch Agent documentation

Start with the [project README](../README.md) for the product, screenshots, local setup and test commands. This index separates the trusted current path from historical experiments.

| Topic | Read |
| --- | --- |
| Product and local demo | [Demo Guide](demo-guide.md), [PRD](PRD.md) |
| Current architecture | [Architecture](portfolio/architecture.md), [system details](architecture.md) |
| Offline evaluation and limitations | [Evaluation](offline-evaluation.md), [engineering evidence](portfolio-evidence.md) |
| Final screenshots | [Screenshot provenance](images/portfolio-final/README.md) |
| Portfolio case study | [PDF](portfolio/PeopleMatch-Agent-Portfolio.pdf), [build source](../scripts/portfolio/README.md) |
| V5 Requirement Review | [Engineering case](release/v5-publication/engineering-case.md), [reproduction tiers](v5-reproduction-guide.md), [Public Portfolio](portfolio/v5/PeopleMatch-AI-Native-Engineer-Public-Portfolio.pdf) |
| Engineering decisions | [Decision records](decisions/), [portfolio decisions](portfolio/engineering-decisions.md) |

The trusted recruiter output uses persisted MatchRun ranking, candidate-scoped Evidence, canonical ExplanationPlanV1 with Grounding, and structured RecruiterProposition. Free-text Recruiter Narrative is a human-review draft only. Phase 9 full-object provider prompts and Narrative Phase 2 experiments remain historical engineering evidence, not the current trusted runtime protocol.

All demo candidates and evaluation records are synthetic. The final Bad Case screenshot depicts an independent synthetic review workflow, not a failure of the Fresh Trusted Top-3 run. The portfolio describes a local prototype and controlled validation, not production performance.
