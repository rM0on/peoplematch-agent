class DomainError(Exception):
    code = "domain_error"
    status_code = 400

    def __init__(self, message: str, *, details=None) -> None:
        super().__init__(message)
        self.details = details


class ProfileNotFoundError(DomainError):
    code = "profile_not_found"
    status_code = 404


class DuplicateProfileError(DomainError):
    code = "duplicate_profile"
    status_code = 409


class FrozenRecordError(DomainError):
    code = "frozen_record"
    status_code = 409


class DomainValidationError(DomainError):
    code = "domain_validation_error"
    status_code = 400


class MockInputNotSupportedError(DomainError):
    code = "mock_input_not_supported"
    status_code = 422


class ProviderUnavailableError(DomainError):
    code = "provider_unavailable"
    status_code = 503


class ProviderTimeoutError(DomainError):
    code = "provider_timeout"
    status_code = 503


class ProviderRateLimitError(DomainError):
    code = "provider_rate_limited"
    status_code = 503

    def __init__(self) -> None:
        super().__init__("AI provider request rate limited")


class ProviderOutputInvalidError(DomainError):
    code = "provider_output_invalid"
    status_code = 502


class EmbeddingProviderUnavailableError(DomainError):
    code = "embedding_provider_unavailable"
    status_code = 503


class EmbeddingDimensionMismatchError(DomainError):
    code = "embedding_dimension_mismatch"
    status_code = 503


class RetrievalIndexMissingError(DomainError):
    code = "retrieval_index_missing"
    status_code = 503


class RetrievalIndexStaleError(DomainError):
    code = "retrieval_index_stale"
    status_code = 409


class VectorStoreUnavailableError(DomainError):
    code = "vector_store_unavailable"
    status_code = 503


class FeatureContractViolationError(DomainError):
    code = "feature_contract_violation"
    status_code = 500


class InvalidProfileStateError(DomainError):
    code = "invalid_profile_state"
    status_code = 409


class RankingModelUnavailableError(DomainError):
    code = "ranking_model_unavailable"
    status_code = 503


class RankingContractMismatchError(DomainError):
    code = "ranking_contract_mismatch"
    status_code = 409


class CrossEncoderModelUnavailableError(DomainError):
    code = "cross_encoder_model_unavailable"
    status_code = 503


class CrossEncoderContractMismatchError(DomainError):
    code = "cross_encoder_contract_mismatch"
    status_code = 409


class MatchRunNotFoundError(DomainError):
    code = "match_run_not_found"
    status_code = 404


class MatchRunConflictError(DomainError):
    code = "match_run_conflict"
    status_code = 409


class MatchRunPersistenceError(DomainError):
    code = "match_run_persistence_failed"
    status_code = 500


class MatchRunExecutionError(DomainError):
    code = "match_run_execution_failed"
    status_code = 500

    def __init__(self, run_id: str, failure_code: str, status_code: int = 500) -> None:
        self.status_code = status_code
        super().__init__(
            "Match run execution failed",
            details={"run_id": run_id, "failure_code": failure_code},
        )


class ExplanationRunNotFoundError(DomainError):
    code = "explanation_run_not_found"
    status_code = 404


class ExplanationRunConflictError(DomainError):
    code = "explanation_run_conflict"
    status_code = 409


class ProfileHistoryConflictError(DomainError):
    code = "profile_history_conflict"
    status_code = 409


class EvaluationIntegrityError(RuntimeError):
    """Offline-only failure when frozen benchmark inputs do not match."""
