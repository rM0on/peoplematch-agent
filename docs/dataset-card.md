# PeopleMatch Phase 1 Dataset Card

## Purpose

The PeopleMatch Phase 1 dataset provides a versioned local sandbox for testing later profile extraction, retrieval, evidence-aware ranking, reranking, bad-case analysis, and offline evaluation. Its central design question is whether a future system can distinguish shared AI vocabulary from demonstrated work, role direction, and practical constraints.

## Scope

Version `1.0.0` contains 48 candidate profiles, 24 fictional job profiles, 288 graded job-to-candidate judgments, and 48 pairwise preferences. Pydantic v2 models with schema version `1.0` are canonical. The dataset is deliberately small and is not production-scale.

## Synthetic Data Policy

All candidate narratives, projects, evidence statements, jobs, and companies are synthetic. Candidate names are numbered identifiers; companies such as Northstar Labs and Helix AI are fictional sandbox entities. Artifact references use `sandbox://`, and optional profile links use `example.invalid`. No real candidate, resume, GitHub profile, private employer data, or recruitment-platform integration is represented.

Labels use `annotation_source = "synthetic_curated"`. This means they were constructed as part of the sandbox and have not been independently human-reviewed.

## Candidate Archetypes

The dataset contains four profiles for each of these archetypes:

1. LLM Application / Agent Engineer
2. Recommendation / Ranking Engineer
3. ML Infra / MLOps Engineer
4. AI Product Engineer
5. RAG / Search Engineer
6. NLP / Model Algorithm Engineer
7. AI Security Engineer
8. Backend / Distributed Systems Engineer
9. Data Engineer
10. Frontend AI Product Engineer
11. Early-career Strong Project Candidate
12. Overclaim Candidate

Variants change seniority, location, work-style preference, evidence availability, missing fields, and overclaim risk. Each archetype also uses multiple project concept families, narrative forms, technology combinations, adjacent skills, and evidence types. Variant quality order is permuted by archetype rather than tied to a global candidate position. Claimed skills and supporting evidence remain separate records.

## Job Archetypes

The 24 jobs cover AI matching, recommendation, LLM agents, AI product, RAG, search/retrieval, applied ML, ML platform, MLOps, AI infrastructure, backend AI, full-stack AI, NLP algorithms, AI security, data engineering, and ML systems. Eight roles add a distinct stage, seniority, evaluation, or product emphasis to those core archetypes.

`job_001`, AI Matching Algorithm Engineer at fictional Northstar Labs, is the core demo query. It combines people-to-role matching, retrieval, ranking, offline evaluation, and AI-product context without referring to a real employer or platform.

## Hard Negative Design

Each job has at least one hard negative and the dataset contains explicit cases for:

- high semantic overlap but wrong role direction;
- claimed keywords without available supporting evidence;
- retrieval or agent vocabulary used only superficially;
- seniority, location, or work-style conflicts;
- a missing must-have despite otherwise adjacent skills;
- broad overclaim risk;
- evidence-rich profiles whose wording is less directly similar to a job.

Hard negatives use relevance grade 0 or 1. Their rationales name both the misleading overlap and the actual mismatch. Generic AI or Python proximity and evaluation-only overlap are insufficient. A grade 2 record is a difficult positive, not a hard negative.

## Label Scale

- `3` — strong match: role direction and must-haves align, evidence is sufficient, and no material declared constraint conflicts.
- `2` — plausible match: credible adjacent fit with one or more documented gaps.
- `1` — weak or misleading match: surface similarity exists, but direction, evidence, or requirements substantially weaken the pair.
- `0` — non-match: critical direction or hard requirements are unsupported.

Every job has at least 12 labels, at least two grade-3 labels, at least two grade-2 labels, grade diversity, and at least one hard negative.

## Pairwise Labels

Each job has two pairwise preferences. They compare an evidence-supported candidate against a weaker, superficially similar candidate and record mismatch reason codes. Pairwise labels are intended for future pairwise-accuracy checks and ranking diagnostics; no pairwise model exists in Phase 1.

## Split Strategy

Jobs are the query groups:

- Train: 14 jobs
- Dev: 5 jobs
- Test: 5 jobs

All relevance and pairwise labels for one job stay in the same split. Candidate profiles may appear under multiple job queries because the protected unit is the query, but no job judgment crosses splits.

## Frozen Baseline

Dataset `1.0.0` with schema `1.0` is the frozen Phase 1 baseline. The canonical-file hashes and exact train/dev/test job IDs are recorded in `data/eval/dataset_freeze_manifest.json`. Test queries `job_020`, `job_021`, `job_022`, `job_023`, and `job_024` must not be changed in response to future retrieval, feature, LTR, reranking, or evaluation results.

If a genuine annotation defect is found later, the correction must state its reason, increment the dataset version, regenerate the freeze manifest, and re-report every affected experiment. Silent edits to the frozen files or test labels are prohibited.

## Known Limitations

- The written profiles are synthetic and more structured than many real resumes or job descriptions.
- Evidence availability is described by curated fixture states rather than independently verified repositories.
- Location coverage is limited to four Chinese cities and a small remote-policy vocabulary.
- Each candidate archetype has the same profile count, which is useful for coverage but not market-representative.
- Pairwise preferences are derived from the same synthetic curation policy as graded labels and are not an independent ground-truth source.

## Ranking Feature Leakage Guard

Future retrieval, ranking, reranking, or LTR code must not use `candidate_id`, `job_id`, `label_id`, `archetype`, `data_origin`, `schema_version`, `split`, `annotation_source`, or a synthetic variant/project-name suffix or family pattern as a signal. These fields describe fixture identity, provenance, schema, evaluation partition, or construction strata; they are not evidence of fit.

`archetype` is allowed only for dataset construction, coverage analysis, split auditing, and documented error slicing. It is prohibited from retrieval text, embedding text, ranking/LTR features, and Cross-Encoder explicit input metadata. Future embedding-text builders must exclude all dataset-construction metadata listed above. Project names may be displayed or inspected as evidence metadata, but synthetic numeric, variant, or family naming patterns must not become model signals. Labels and pairwise outcomes remain evaluation/training targets and must never be copied into candidate or job features.

## Offline Evaluation Interpretation

The labels use `annotation_source = "synthetic_curated"`. Future Recall@K, NDCG@K, MRR, and Pairwise Accuracy values therefore mean only performance on the fixed synthetic sandbox evaluation set. They must not be interpreted as real hiring accuracy, production improvement, real-world user impact, or online lift.

The labels and some future feature signals intentionally share evidence, direction, and constraint concepts. Experiments on this dataset are consequently suited to engineering comparison, pipeline debugging, and strategy comparison—not proof of real recruitment effectiveness.

## Bias and Representation Limitations

The dataset intentionally oversamples difficult matching cases because its purpose is to stress later ranking stages. It does not represent the prevalence of occupations, skill combinations, seniority, cities, employers, or candidate backgrounds in a real recruitment market. It must not be used for fairness claims, hiring decisions, or demographic inference.

## Privacy

No real personal data is permitted. A future contribution containing a real name, resume, contact detail, private repository reference, or employer record must be removed before it enters the dataset.

## Future Expansion

Later versions may add independently reviewed annotations, more language styles, broader locations, uncertainty adjudication, and documented inter-annotator processes. Phase 2 may consume the seed manifest for database insertion. Retrieval, ranking, metrics, and database behavior remain outside Phase 1.
