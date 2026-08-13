class DomainError(Exception):
    code = "domain_error"
    status_code = 400


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


class ProviderOutputInvalidError(DomainError):
    code = "provider_output_invalid"
    status_code = 502
