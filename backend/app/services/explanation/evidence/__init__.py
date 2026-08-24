from __future__ import annotations

from app.services.explanation.evidence.bundle_builder import (
    EvidenceBundleBuilder,
    build_evidence_bundle,
)
from app.services.explanation.evidence.comparison_builder import Top1ComparisonBuilder
from app.services.explanation.evidence.contracts import (
    CandidateFactSet,
    ComparisonItem,
    EVIDENCE_FACTS_VERSION,
    EvidenceFactsV1,
    MatchReasonFact,
    MissingRequirementFact,
    RankingContextFact,
    RiskFact,
    Top1ComparisonFact,
)
from app.services.explanation.evidence.normalization import NORMALIZER_VERSION
from app.services.explanation.evidence.fingerprints import evidence_content_fingerprint
from app.services.explanation.evidence.fact_builder import (
    EvidenceFactBuilder,
    build_evidence_facts,
)
from app.services.explanation.evidence.requirement_builder import MissingRequirementBuilder
from app.services.explanation.evidence.validation import (
    validate_evidence_facts,
    validate_fact_references,
)


__all__ = [
    "CandidateFactSet",
    "ComparisonItem",
    "EVIDENCE_FACTS_VERSION",
    "EvidenceBundleBuilder",
    "EvidenceFactBuilder",
    "EvidenceFactsV1",
    "MatchReasonFact",
    "MissingRequirementBuilder",
    "MissingRequirementFact",
    "NORMALIZER_VERSION",
    "RankingContextFact",
    "RiskFact",
    "Top1ComparisonBuilder",
    "Top1ComparisonFact",
    "build_evidence_bundle",
    "build_evidence_facts",
    "evidence_content_fingerprint",
    "validate_evidence_facts",
    "validate_fact_references",
]
