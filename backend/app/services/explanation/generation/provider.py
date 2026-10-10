from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Protocol


_SAFE_PROVIDER_KIND = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
_SAFE_PROVIDER_NAME = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,79}$")
_SAFE_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}$")
_FINGERPRINT = re.compile(r"^[a-f0-9]{64}$")
MAX_PROVIDER_RESPONSE_BYTES = 65536


@dataclass(frozen=True)
class ExplanationProviderDescriptor:
    """Trusted, non-secret provider metadata available to orchestration."""

    kind: str
    name: str
    configured_model: str
    configuration_fingerprint: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.kind, str)
            or _SAFE_PROVIDER_KIND.fullmatch(self.kind) is None
            or not isinstance(self.name, str)
            or _SAFE_PROVIDER_NAME.fullmatch(self.name) is None
            or not isinstance(self.configured_model, str)
            or _SAFE_MODEL.fullmatch(self.configured_model) is None
            or not isinstance(self.configuration_fingerprint, str)
            or _FINGERPRINT.fullmatch(self.configuration_fingerprint) is None
        ):
            raise ExplanationProviderConfigurationError(
                "Explanation provider descriptor is invalid"
            )


@dataclass(frozen=True)
class ExplanationProviderRequest:
    """Transport-only request built from the closed opaque prompt projection."""

    system_instruction: str
    user_instruction: str
    output_contract_version: str
    max_output_tokens: int
    response_schema: dict[str, Any] | None = None


@dataclass(frozen=True)
class ExplanationProviderResponse:
    """Transient provider output; it must be parsed before any persistence."""

    content: str
    observed_model: str | None
    http_status_code: int | None = None
    finish_reason: str | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.content, str)
            or not self.content.strip()
            or len(self.content.encode("utf-8")) > MAX_PROVIDER_RESPONSE_BYTES
            or (self.http_status_code is not None
                and (type(self.http_status_code) is not int
                     or not 200 <= self.http_status_code <= 299))
            or (
                self.finish_reason is not None
                and (
                    not isinstance(self.finish_reason, str)
                    or self.finish_reason not in {
                        "stop", "length", "content_filter", "tool_calls",
                        "function_call", "other",
                    }
                )
            )
        ):
            raise ExplanationProviderMalformedResponseError()


class ExplanationProvider(Protocol):
    descriptor: ExplanationProviderDescriptor

    async def generate(
        self, request: ExplanationProviderRequest
    ) -> ExplanationProviderResponse:
        """Generate one untrusted structured response without retrying."""


class ExplanationProviderError(Exception):
    category = "provider_error"


class ExplanationProviderConfigurationError(ExplanationProviderError):
    category = "configuration"


class ExplanationProviderTimeoutError(ExplanationProviderError):
    category = "timeout"

    def __init__(self, *, phase: str = "unknown", received_response: bool = False,
                 status_code: int | None = None) -> None:
        self.phase = phase
        self.received_response = received_response
        self.status_code = status_code
        super().__init__("Explanation provider timed out")


class ExplanationProviderTransportError(ExplanationProviderError):
    category = "transport"

    def __init__(self) -> None:
        super().__init__("Explanation provider transport failed")


class ExplanationProviderRateLimitError(ExplanationProviderError):
    category = "rate_limited"

    def __init__(self, *, provider_error_code: str | None = None,
                 retry_after_seconds: int | None = None) -> None:
        self.status_code = 429
        self.provider_error_code = provider_error_code
        self.retry_after_seconds = retry_after_seconds
        self.received_response = True
        super().__init__("Explanation provider request rate limited")


class ExplanationProviderHttpError(ExplanationProviderError):
    category = "http_status"

    def __init__(self, status_code: int, *, provider_error_code: str | None = None,
                 retry_after_seconds: int | None = None) -> None:
        self.status_code = status_code
        self.provider_error_code = provider_error_code
        self.retry_after_seconds = retry_after_seconds
        self.received_response = True
        super().__init__(f"Explanation provider returned HTTP status {status_code}")


class ExplanationProviderMalformedResponseError(ExplanationProviderError):
    category = "malformed_response"

    def __init__(self) -> None:
        super().__init__("Explanation provider returned an invalid response envelope")


__all__ = [
    "ExplanationProvider",
    "ExplanationProviderConfigurationError",
    "ExplanationProviderDescriptor",
    "ExplanationProviderError",
    "ExplanationProviderHttpError",
    "ExplanationProviderMalformedResponseError",
    "ExplanationProviderRateLimitError",
    "ExplanationProviderRequest",
    "ExplanationProviderResponse",
    "ExplanationProviderTimeoutError",
    "ExplanationProviderTransportError",
    "MAX_PROVIDER_RESPONSE_BYTES",
]
