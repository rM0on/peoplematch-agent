"""Provider-neutral, opaque-reference generation contracts.

This package is intentionally separate from the frozen evidence and persistence
contracts.  It projects only typed selection inputs for a provider and keeps
the reverse reference map in process memory.
"""

from app.services.explanation.generation.contracts import (
    ExplanationPlanV1,
    ProviderPromptEvidenceV1,
    ResolvedExplanationPlanV1,
)
from app.services.explanation.generation.reference_projection import (
    ProviderReferenceProjector,
    resolve_explanation_plan,
)

__all__ = [
    "ExplanationPlanV1",
    "ProviderPromptEvidenceV1",
    "ProviderReferenceProjector",
    "ResolvedExplanationPlanV1",
    "resolve_explanation_plan",
]
