PHASE10_NON_TRUTH_TYPES = frozenset(
    {"FeedbackRecord", "SystemSignal", "BadCase", "BadCaseAnalysis", "ResolutionAction", "VERIFIED"}
)


def reject_phase10_truth_source(source_type: str) -> None:
    if source_type in PHASE10_NON_TRUTH_TYPES:
        raise ValueError(f"{source_type} cannot be used as evaluation truth")
