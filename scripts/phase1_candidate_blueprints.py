from __future__ import annotations

from typing import Any, Dict, List


CANDIDATE_BLUEPRINTS: List[Dict[str, Any]] = [
    {
        "archetype": "llm_application_agent_engineer",
        "discipline": "LLM application and agent workflow engineering",
        "skills": [
            ("Agent workflow", "llm_application"),
            ("Tool calling", "llm_application"),
            ("RAG", "retrieval_search"),
            ("Evaluation harness", "evaluation"),
            ("FastAPI", "backend"),
            ("Product delivery", "product_delivery"),
        ],
        "tools": ["structured outputs", "tool schemas", "prompt tracing"],
        "targets": ["LLM Agent Engineer", "AI Product Engineer"],
        "project_names": ["Orchid Workflow Lab", "Cedar Retrieval Assistant"],
        "project_summaries": [
            "A local multi-step assistant that calls typed tools and records failure paths for review.",
            "A sandbox knowledge assistant with retrieval citations and a small regression fixture set.",
        ],
        "technologies": ["Python", "FastAPI", "Pydantic"],
    },
    {
        "archetype": "recommendation_ranking_engineer",
        "discipline": "recommendation, ranking, and relevance engineering",
        "skills": [
            ("Candidate retrieval", "recommendation"),
            ("Feature engineering", "recommendation"),
            ("Learning to rank", "recommendation"),
            ("Offline evaluation", "evaluation"),
            ("Search relevance", "retrieval_search"),
            ("Experiment design", "product_delivery"),
        ],
        "tools": ["ranking notebooks", "label audits", "feature registries"],
        "targets": ["Recommendation Algorithm Engineer", "Ranking Engineer"],
        "project_names": ["Compass Ranking Bench", "Harbor Candidate Recall"],
        "project_summaries": [
            "A sandbox ranking benchmark that compares explicit feature sets on fixed relevance judgments.",
            "A local candidate-recall study separating lexical coverage from final ordering decisions.",
        ],
        "technologies": ["Python", "pandas", "scikit-learn"],
    },
    {
        "archetype": "ml_infra_mlops_engineer",
        "discipline": "ML infrastructure, serving, and operational reliability",
        "skills": [
            ("Kubernetes", "ml_infra"),
            ("Model serving", "ml_infra"),
            ("Observability", "ml_infra"),
            ("CI/CD", "ml_infra"),
            ("Python", "backend"),
            ("Load testing", "evaluation"),
        ],
        "tools": ["container runtimes", "metrics exporters", "deployment manifests"],
        "targets": ["ML Platform Engineer", "MLOps Engineer"],
        "project_names": ["Granite Serving Control", "Signal Model Runtime"],
        "project_summaries": [
            "A local model-serving control plane exercise with health probes and bounded rollout states.",
            "An observability sandbox for inference queues, resource saturation, and deployment rollback drills.",
        ],
        "technologies": ["Python", "Kubernetes", "Prometheus"],
    },
    {
        "archetype": "ai_product_engineer",
        "discipline": "full-stack AI product delivery and user workflow design",
        "skills": [
            ("LLM integration", "llm_application"),
            ("Full-stack delivery", "product_delivery"),
            ("User workflow", "product_delivery"),
            ("Evaluation harness", "evaluation"),
            ("FastAPI", "backend"),
            ("TypeScript", "frontend"),
        ],
        "tools": ["structured outputs", "AI coding tools", "product analytics fixtures"],
        "targets": ["AI Product Engineer", "Full-stack AI Engineer"],
        "project_names": ["Lantern Research Copilot", "Mosaic Review Workspace"],
        "project_summaries": [
            "A local research workflow that turns cited source notes into reviewable structured drafts.",
            "A sandbox review workspace connecting an AI-assisted form, API validation, and user corrections.",
        ],
        "technologies": ["Next.js", "TypeScript", "FastAPI"],
    },
    {
        "archetype": "rag_search_engineer",
        "discipline": "retrieval-augmented generation and search relevance",
        "skills": [
            ("Vector retrieval", "retrieval_search"),
            ("Lexical retrieval", "retrieval_search"),
            ("Reranking", "retrieval_search"),
            ("Embedding evaluation", "evaluation"),
            ("Knowledge systems", "llm_application"),
            ("Search relevance", "retrieval_search"),
            ("Python", "backend"),
        ],
        "tools": ["vector databases", "relevance judgments", "query analyzers"],
        "targets": ["RAG Engineer", "Search / Retrieval Engineer"],
        "project_names": ["Juniper Knowledge Search", "Tidal Retrieval Lab"],
        "project_summaries": [
            "A local knowledge-search prototype combining lexical candidates with vector retrieval and citations.",
            "A sandbox query suite for examining reranking changes and retrieval misses by query family.",
        ],
        "technologies": ["Python", "Qdrant", "FastAPI"],
    },
    {
        "archetype": "nlp_model_algorithm_engineer",
        "discipline": "NLP modeling, transformer training, and model evaluation",
        "skills": [
            ("PyTorch", "model_algorithm"),
            ("Transformers", "model_algorithm"),
            ("Fine-tuning", "model_algorithm"),
            ("Model evaluation", "evaluation"),
            ("NLP datasets", "data"),
            ("Python", "backend"),
        ],
        "tools": ["training loops", "tokenizers", "experiment tracking"],
        "targets": ["NLP Algorithm Engineer", "Applied ML Engineer"],
        "project_names": ["Sable Intent Model", "Pine Domain Adaptation"],
        "project_summaries": [
            "A sandbox transformer fine-tuning exercise with controlled splits and error slices.",
            "A local domain-adaptation study documenting training data, checkpoints, and evaluation caveats.",
        ],
        "technologies": ["Python", "PyTorch", "Transformers"],
    },
    {
        "archetype": "ai_security_engineer",
        "discipline": "AI security, robustness, and adversarial evaluation",
        "skills": [
            ("Adversarial ML", "security"),
            ("Model robustness", "security"),
            ("Security evaluation", "evaluation"),
            ("PyTorch", "model_algorithm"),
            ("Threat modeling", "security"),
            ("Python", "backend"),
        ],
        "tools": ["attack fixtures", "robustness suites", "threat models"],
        "targets": ["AI Security Engineer", "Model Robustness Engineer"],
        "project_names": ["Aegis Prompt Boundary", "Beacon Robustness Suite"],
        "project_summaries": [
            "A local adversarial test suite for prompt-boundary and tool-permission failures.",
            "A sandbox robustness study that records model failures across controlled perturbation families.",
        ],
        "technologies": ["Python", "PyTorch", "pytest"],
    },
    {
        "archetype": "backend_distributed_systems_engineer",
        "discipline": "backend APIs, databases, and distributed systems",
        "skills": [
            ("Distributed systems", "backend"),
            ("API design", "backend"),
            ("Databases", "backend"),
            ("Performance testing", "evaluation"),
            ("Model serving", "ml_infra"),
            ("Python", "backend"),
            ("Go", "backend"),
        ],
        "tools": ["profilers", "database tooling", "load generators"],
        "targets": ["Backend AI Engineer", "Distributed Systems Engineer"],
        "project_names": ["Quartz Event Gateway", "River Consistency Lab"],
        "project_summaries": [
            "A local event-gateway prototype with idempotency, typed APIs, and failure injection tests.",
            "A sandbox study of database consistency and back-pressure under repeatable request workloads.",
        ],
        "technologies": ["Python", "Go", "PostgreSQL"],
    },
    {
        "archetype": "data_engineer",
        "discipline": "data pipelines, warehousing, and streaming systems",
        "skills": [
            ("ETL", "data"),
            ("Data warehouse", "data"),
            ("Streaming", "data"),
            ("SQL", "data"),
            ("Data quality", "evaluation"),
            ("Python", "backend"),
        ],
        "tools": ["pipeline schedulers", "schema checks", "lineage manifests"],
        "targets": ["Data Engineer", "ML Data Engineer"],
        "project_names": ["Delta Stream Workshop", "Maple Warehouse Contract"],
        "project_summaries": [
            "A local streaming pipeline with schema evolution fixtures and replayable data-quality checks.",
            "A sandbox warehouse model documenting lineage, tests, and late-arriving record handling.",
        ],
        "technologies": ["Python", "SQL", "Kafka"],
    },
    {
        "archetype": "frontend_ai_product_engineer",
        "discipline": "frontend engineering for explainable AI product experiences",
        "skills": [
            ("React", "frontend"),
            ("Next.js", "frontend"),
            ("TypeScript", "frontend"),
            ("AI interaction design", "product_delivery"),
            ("Accessibility", "frontend"),
            ("User workflow", "product_delivery"),
        ],
        "tools": ["component systems", "browser testing", "AI response states"],
        "targets": ["Frontend AI Product Engineer", "Full-stack AI Engineer"],
        "project_names": ["Prism Evidence Interface", "Willow AI Review Flow"],
        "project_summaries": [
            "A responsive evidence interface for comparing cited AI output with its source records.",
            "A sandbox AI review flow covering loading, correction, empty, and failure states.",
        ],
        "technologies": ["React", "Next.js", "TypeScript"],
    },
    {
        "archetype": "early_career_strong_project",
        "discipline": "early-career AI engineering with unusually complete project artifacts",
        "skills": [
            ("Agent workflow", "llm_application"),
            ("Search relevance", "retrieval_search"),
            ("Evaluation harness", "evaluation"),
            ("Python", "backend"),
            ("Technical writing", "product_delivery"),
            ("Dataset curation", "data"),
        ],
        "tools": ["test fixtures", "evaluation reports", "architecture notes"],
        "targets": ["Applied AI Engineer", "LLM Agent Engineer"],
        "project_names": ["Kite Agent Notebook", "Elm Relevance Dataset"],
        "project_summaries": [
            "A self-directed agent prototype with typed tool calls, failure fixtures, and a documented demo.",
            "A curated sandbox relevance set with query groups and transparent labeling notes.",
        ],
        "technologies": ["Python", "FastAPI", "pytest"],
    },
    {
        "archetype": "overclaim_candidate",
        "discipline": "broadly claimed AI capabilities with limited supporting artifacts",
        "skills": [
            ("Agent workflow", "llm_application"),
            ("Learning to rank", "recommendation"),
            ("Vector retrieval", "retrieval_search"),
            ("Model serving", "ml_infra"),
            ("Python APIs", "backend"),
            ("Evaluation harness", "evaluation"),
            ("Model evaluation", "model_algorithm"),
        ],
        "tools": ["AI frameworks", "vector databases", "deployment tools"],
        "targets": ["AI Engineer", "Recommendation Engineer", "ML Platform Engineer"],
        "project_names": ["Atlas AI Survey", "Nova Prototype Notes"],
        "project_summaries": [
            "A broad technology survey describing agent, retrieval, and ranking concepts without executable comparisons.",
            "A short prototype narrative whose implementation and test artifacts were not included in the profile.",
        ],
        "technologies": ["Python", "Jupyter", "Markdown"],
    },
]


VARIANTS: List[Dict[str, Any]] = [
    {
        "descriptor": "evidence-led senior practitioner",
        "seniority": "senior",
        "level": "advanced",
        "location": ("Shanghai", "hybrid", True),
        "stages": ["zero_to_one", "growth", "mature"],
        "collaboration": "cross_functional",
        "missing": [],
    },
    {
        "descriptor": "mid-level specialist with an incomplete public profile",
        "seniority": "mid",
        "level": "practiced",
        "location": ("Beijing", "onsite", False),
        "stages": ["growth", "mature"],
        "collaboration": "structured_team",
        "missing": ["github_url"],
    },
    {
        "descriptor": "project-led practitioner transitioning into the specialty",
        "seniority": "senior",
        "level": "practiced",
        "location": ("Hangzhou", "flexible", True),
        "stages": ["zero_to_one", "growth", "mature"],
        "collaboration": "independent_with_frequent_review",
        "missing": [],
    },
    {
        "descriptor": "claim-heavy practitioner with sparse artifact detail",
        "seniority": "mid",
        "level": "advanced",
        "location": ("Shenzhen", "onsite", False),
        "stages": ["mature"],
        "collaboration": "platform_maintenance",
        "missing": ["github_url", "project_outcomes"],
    },
]


NARRATIVE_OPENERS = [
    "The profile describes an evidence-led builder working primarily in {discipline}.",
    "Recent work is centered on {discipline}, usually inside a structured delivery team.",
    "Most experience comes from self-contained projects in {discipline}, with careful written handoff.",
    "The summary claims broad ownership across {discipline}, although the attached artifacts are sparse.",
]


ALTERNATE_PROJECT_FAMILIES: Dict[str, Dict[str, List[str]]] = {
    "llm_application_agent_engineer": {
        "names": ["Marigold Tool Router", "Birch Evaluation Console"],
        "summaries": [
            "A typed tool-routing exercise that records permission failures and retry boundaries.",
            "A compact agent evaluation console grouping workflow traces by failure mode.",
        ],
    },
    "recommendation_ranking_engineer": {
        "names": ["Meridian Pairwise Study", "Signal Feature Ledger"],
        "summaries": [
            "A pairwise ranking study contrasting superficial similarity with evidence-backed preferences.",
            "A feature ledger tracing retrieval, direction, and constraint signals to fixed relevance labels.",
        ],
    },
    "ml_infra_mlops_engineer": {
        "names": ["Palisade Rollout Simulator", "Pulse Queue Observatory"],
        "summaries": [
            "A deployment simulator exercising readiness gates, rollback paths, and bounded rollout failures.",
            "An inference-queue observatory linking saturation symptoms to repeatable load scenarios.",
        ],
    },
    "ai_product_engineer": {
        "names": ["Threadline Intake Copilot", "Cobalt Correction Loop"],
        "summaries": [
            "A structured intake workflow joining an LLM-backed API to a reviewable product surface.",
            "A correction loop that preserves user edits and evaluates recurring response failures.",
        ],
    },
    "rag_search_engineer": {
        "names": ["Rook Query Diagnostics", "Estuary Citation Index"],
        "summaries": [
            "A query diagnostic workbench comparing lexical, vector, and reranked result sets.",
            "A citation index that exposes retrieval provenance and relevance-review fixtures.",
        ],
    },
    "nlp_model_algorithm_engineer": {
        "names": ["Ember Error Slice", "Linden Token Study"],
        "summaries": [
            "A model-error slicing study connecting controlled evaluation groups to fine-tuning changes.",
            "A tokenizer and domain-shift experiment with reproducible data partitions and checkpoints.",
        ],
    },
    "ai_security_engineer": {
        "names": ["Sentinel Tool Sandbox", "Harbor Attack Ledger"],
        "summaries": [
            "A permission-boundary sandbox for adversarial tool calls and unsafe state transitions.",
            "An attack ledger connecting threat scenarios to robustness fixtures and review outcomes.",
        ],
    },
    "backend_distributed_systems_engineer": {
        "names": ["Trestle Request Broker", "Canyon Backpressure Study"],
        "summaries": [
            "A typed request broker with idempotent writes, queue recovery, and service-level tests.",
            "A backpressure study comparing database and model-serving behavior under repeatable load.",
        ],
    },
    "data_engineer": {
        "names": ["Copper Lineage Pipeline", "Spruce Replay Warehouse"],
        "summaries": [
            "A lineage-aware batch pipeline with schema contracts and failed-record quarantine.",
            "A replayable warehouse exercise covering late data, SQL checks, and quality exceptions.",
        ],
    },
    "frontend_ai_product_engineer": {
        "names": ["Lumen Citation Workspace", "Frame AI State Lab"],
        "summaries": [
            "A citation workspace balancing source inspection, keyboard navigation, and AI response states.",
            "An interface-state lab for streaming, correction, failure, and accessible focus behavior.",
        ],
    },
    "early_career_strong_project": {
        "names": ["Pocket Tool Agent", "Seedling Query Set"],
        "summaries": [
            "A small typed-tool agent accompanied by tests, a workflow trace, and limitations notes.",
            "A grouped query set with relevance notes, evaluation scripts, and transparent curation rules.",
        ],
    },
    "overclaim_candidate": {
        "names": ["Omni AI Capability Map", "Summit Integration Outline"],
        "summaries": [
            "A wide capability map naming agent, ranking, retrieval, and serving patterns without comparative artifacts.",
            "An integration outline that claims broad coverage while leaving implementation and evaluation unavailable.",
        ],
    },
}


ADJACENT_SKILLS: Dict[str, List[tuple[str, str]]] = {
    "llm_application_agent_engineer": [
        ("Structured extraction", "llm_application"),
        ("Prompt evaluation", "evaluation"),
    ],
    "recommendation_ranking_engineer": [
        ("Pairwise ranking", "recommendation"),
        ("Label analysis", "evaluation"),
    ],
    "ml_infra_mlops_engineer": [
        ("Incident response", "ml_infra"),
        ("Deployment safety", "ml_infra"),
    ],
    "ai_product_engineer": [
        ("Structured extraction", "llm_application"),
        ("UX research", "product_delivery"),
    ],
    "rag_search_engineer": [
        ("Query analysis", "retrieval_search"),
        ("Citation grounding", "llm_application"),
    ],
    "nlp_model_algorithm_engineer": [
        ("Error analysis", "evaluation"),
        ("Data slicing", "data"),
    ],
    "ai_security_engineer": [
        ("Red teaming", "security"),
        ("Permission boundaries", "security"),
    ],
    "backend_distributed_systems_engineer": [
        ("Message queues", "backend"),
        ("Failure injection", "evaluation"),
    ],
    "data_engineer": [
        ("Batch orchestration", "data"),
        ("Data lineage", "data"),
    ],
    "frontend_ai_product_engineer": [
        ("Design systems", "frontend"),
        ("LLM integration", "llm_application"),
    ],
    "early_career_strong_project": [
        ("Retrieval evaluation", "evaluation"),
        ("Reproducibility", "product_delivery"),
    ],
    "overclaim_candidate": [
        ("Cross-Encoder", "recommendation"),
        ("Agent evaluation", "evaluation"),
    ],
}


VARIANT_PERMUTATIONS: Dict[str, List[int]] = {
    "llm_application_agent_engineer": [0, 1, 2, 3],
    "recommendation_ranking_engineer": [0, 1, 2, 3],
    "ml_infra_mlops_engineer": [1, 0, 3, 2],
    "ai_product_engineer": [2, 3, 0, 1],
    "rag_search_engineer": [3, 0, 1, 2],
    "nlp_model_algorithm_engineer": [1, 2, 3, 0],
    "ai_security_engineer": [2, 1, 0, 3],
    "backend_distributed_systems_engineer": [3, 2, 1, 0],
    "data_engineer": [1, 3, 2, 0],
    "frontend_ai_product_engineer": [2, 0, 3, 1],
    "early_career_strong_project": [0, 1, 2, 3],
    "overclaim_candidate": [0, 1, 2, 3],
}


PROJECT_SCOPE_NOTES = [
    "The reference build emphasizes reproducibility and reviewer-visible checks.",
    "The field study narrows the scope and records implementation trade-offs.",
    "The comparison study records alternatives, tests, and limitations for handoff.",
    "The integration study maps system boundaries and open questions for handoff.",
]


PROJECT_NAME_QUALIFIERS = [
    "Reference Build",
    "Field Study",
    "Comparison Track",
    "Integration Study",
]


TECHNOLOGY_EXTRAS = ["pytest", "Docker", "Jupyter", "Markdown"]
