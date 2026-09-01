from __future__ import annotations

import json

from app.exceptions import (
    ProviderOutputInvalidError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.services.explanation.generation.provider import (
    ExplanationProviderHttpError,
    ExplanationProviderMalformedResponseError,
    ExplanationProviderRequest,
    ExplanationProviderTimeoutError,
    ExplanationProviderTransportError,
)
from app.services.profile_extraction.provider import (
    ProviderDescriptor,
    ProviderRequest,
    ProviderResponse,
)


class OpenAICompatibleStructuredOutputProvider:
    """Extraction adapter over the frozen OpenAI-compatible chat transport."""

    def __init__(
        self,
        *,
        transport,
        descriptor: ProviderDescriptor,
        max_output_tokens: int,
    ) -> None:
        self._transport = transport
        self.descriptor = descriptor
        self.max_output_tokens = max_output_tokens
        self.configuration_fingerprint = transport.descriptor.configuration_fingerprint

    def __repr__(self) -> str:
        return (
            "OpenAICompatibleStructuredOutputProvider("
            f"descriptor={self.descriptor!r}, max_output_tokens={self.max_output_tokens!r})"
        )

    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        contract = json.dumps(
            request.output_contract,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        user_instruction = (
            f"{request.user_message}\n\n"
            "The required JSON Schema follows. Return one object that validates exactly.\n"
            f"<json_schema>\n{contract}\n</json_schema>"
        )
        try:
            response = await self._transport.generate(
                ExplanationProviderRequest(
                    system_instruction=request.system_message,
                    user_instruction=user_instruction,
                    output_contract_version=f"phase12_{request.task.value}_extraction_v1",
                    max_output_tokens=self.max_output_tokens,
                )
            )
        except ExplanationProviderTimeoutError:
            raise ProviderTimeoutError("Structured output provider timed out") from None
        except (ExplanationProviderTransportError, ExplanationProviderHttpError):
            raise ProviderUnavailableError(
                "Structured output provider is unavailable"
            ) from None
        except ExplanationProviderMalformedResponseError:
            raise ProviderOutputInvalidError(
                "Structured output provider returned an invalid response"
            ) from None
        return ProviderResponse(raw_output=response.content)

    async def aclose(self) -> None:
        await self._transport.aclose()


__all__ = ["OpenAICompatibleStructuredOutputProvider"]
