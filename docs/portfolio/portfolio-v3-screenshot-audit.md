# Portfolio v3 — Real Provider Screenshot Audit

> Evidence capture only. This document does not claim public deployment, production users, hiring accuracy, or online business impact.

## Capture identity

| Field | Value |
|---|---|
| Branch / baseline | `portfolio-demo` / `4fc3d22ea8f073f40d96ca5dc291d3605ca702e2` |
| Capture window | 2026-09-24 16:07:18–16:11:15 CST (08:07:18–08:11:15 UTC) |
| Browser viewport | 1440 × 1024, Chromium, headless capture |
| Job scenario | Synthetic AI Agent Engineer JD |
| Extraction provider | `openai_compatible` |
| Explanation provider | `openai_compatible` |
| Configured model | `qwen3.7-plus` |
| MatchRun | `50b6a328-cf6f-4ec5-93aa-1bf964eaacb9` |
| Ranking owner | `ltr` (LambdaMART) |
| Ranking fingerprint | `295fc25bc3042f6ae8c1686b889b03a247ba554b2cd6d1f717ec409ff0762468` |
| Explanation prompt | `explanation_prompt_v2` |
| Explanation attempts | 1; constrained repair was not triggered |
| Explanation validation | Schema `PASS`; Evidence grounding `PASS` |
| Browser errors | 0 |
| Sensitive UI scan | `PASS` |

The final screenshots were all overwritten by and verified against this single successful MatchRun. An earlier provider run that ended in `invalid_output` was rejected and is not represented in the final result screenshots. No raw provider response was saved.

## Screenshot evidence

### 01_real_product_overview.png

![PeopleMatch Agent product overview](../images/portfolio-v3/01_real_product_overview.png)

- **Purpose:** Establish the JD-first AI talent recommendation product and the seven-step user journey.
- **Technical signal:** The page separates Candidate Retrieval, Feature Engineering, LambdaMART ranking, and LLM explanation. The provider badge shows `OpenAI-compatible 已配置` without claiming a live connection test.
- **Authenticity:** Captured from the real-provider runtime immediately before the final MatchRun.
- **SHA256:** `5b2af3d908624dcf7eb9fa6151d6d22039d40b032fd627b4baadac1fd99e9785`

### 02_real_jd_matching_flow.png

![Real JD matching flow](../images/portfolio-v3/02_real_jd_matching_flow.png)

- **Purpose:** Show the synthetic AI Agent Engineer JD and the live `正在理解岗位需求…` state.
- **Technical signal:** The request entered `job_extraction_prompt_v1` through Qwen; the extraction completed on the first attempt and persisted a structured job record.
- **Boundary:** The current UI exposes the live extraction stage and later displays the parsed role title/location; it does not expose a separate full Job Profile Preview panel. The screenshot does not imply otherwise.
- **SHA256:** `d414894b32b77b38d9123134b55efdd4989bac4f7131a6549ab5e85b62a64b3b`

### 03_real_candidate_ranking.png

![Real candidate ranking](../images/portfolio-v3/03_real_candidate_ranking.png)

- **Purpose:** Show the persisted Top-K shortlist and the selected candidate’s ranking evidence.
- **Technical signal:** Retrieval rank, LTR rank, raw LTR score, feature signals, Run ID, and fingerprint are visible. The UI explicitly states that LTR Score is not a probability or hiring outcome.
- **Invariance evidence:** The candidate order and raw scores read after explanation were byte-for-byte equal to the original MatchRun response; the ranking fingerprint remained unchanged.
- **SHA256:** `f355d06d0a55c7380bf768b6b501ab71bc604c35984efb67c68f7edea04b7f6a`

### 04_real_llm_explanation.png

![Real evidence-grounded explanation](../images/portfolio-v3/04_real_llm_explanation.png)

- **Purpose:** Show the real-provider explanation beside the selected ranked candidate.
- **Technical signal:** The persisted output passed `ExplanationPlanV1` schema validation and Evidence grounding, contains supported strengths, explicit missing requirements/risks, and opaque evidence references.
- **Honest rendering boundary:** Qwen selects a constrained explanation plan from the evidence projection. The product then renders validated operations with controlled wording; the screenshot is not raw free-form model text. This is why some sentence forms are intentionally consistent while evidence references, missing requirements, risks, and output signatures differ by candidate.
- **Distinctness check:** All five persisted candidate explanation signatures were unique. The first three candidate detail UI signatures and explanation signatures were also unique.
- **SHA256:** `8fd94f9ed885faff397c2986602b6e7eeb2b577b1639c88a0488084c697313c3`

### 05_real_matchrun_trace.png

![Real MatchRun trace](../images/portfolio-v3/05_real_matchrun_trace.png)

- **Purpose:** Demonstrate auditability of the run that produced the captured ranking and explanation.
- **Technical signal:** Input resolution, LambdaMART ranking, and result persistence are shown as completed immutable steps. The boundary note states that explanation reads MatchRun Evidence Facts and cannot mutate order or scores.
- **Capture validation:** This viewport was force-positioned on the trace and has a distinct SHA256 from the explanation screenshot.
- **SHA256:** `7466a3c0db8626eeaa487ac7d554c66420b5bef5ba4d67799fd4e67a4b112c48`

### 06_real_candidate_profile.png

![Real candidate profile extraction](../images/portfolio-v3/06_real_candidate_profile.png)

- **Purpose:** Show the Candidate Lifecycle entry point and a real Qwen structured-profile preview.
- **Technical signal:** The synthetic resume was parsed by `candidate_extraction_prompt_v1` through the OpenAI-compatible provider. Skills, target role, seniority, projects, and missing fields are visible.
- **Data safety:** Preview mode used `persist=false`; the synthetic candidate was not added to the Candidate Pool and no index rebuild was triggered.
- **SHA256:** `2b15bb656b793ad30c8d4753231a91e5b1e9dcdb24c04ae161e10dbf15e1e6bf`

### 07_real_feedback_review.png

![Real feedback review workflow](../images/portfolio-v3/07_real_feedback_review.png)

- **Purpose:** Demonstrate the human review loop after AI recommendation.
- **Technical signal:** Feedback targets the persisted five-result MatchRun and keeps ranking, explanation, and profile review as explicit reviewer choices.
- **Data safety:** The form was displayed only; no feedback was submitted and no historical result was modified.
- **SHA256:** `7e546aa7f1e232d0d274a2a38c4b09e47b1444bb24fd430dfba65c1f7670be1c`

## Candidate differentiation check

The final Top-K contains multiple evidence profiles rather than five copies of one candidate:

- `cand_001` / `cand_003`: LLM application and Agent workflow profiles.
- `cand_041` / `cand_043`: applied AI, search relevance, evaluation, and project-evidence profiles.
- `cand_parse_0c301d86a7d24d1ea03962fbdd518ca6`: synthetic talent-library profile targeting recommendation engineering, with retrieval, feature engineering, and offline evaluation skills.

The final run did not place a dedicated backend-only archetype in Top-K. Backend Engineering is represented in the job requirements and the separate real candidate-profile extraction, but this audit does not relabel any ranked candidate as a backend specialist.

## Authenticity and privacy assertions

- No deterministic Mock provider or fallback was used for extraction or explanation.
- No static JSON or pre-generated recommendation result was injected.
- No explanation text, ranking result, database row, or screenshot pixel was manually edited.
- No Candidate Pool mutation occurred during capture; candidate parsing remained preview-only.
- No credentials, authentication headers, session cookies, email addresses, raw provider responses, real resumes, or local filesystem paths appear in the screenshots.
- The screenshots demonstrate a local prototype with synthetic data and offline evaluation context; they do not claim production deployment or real hiring effectiveness.
