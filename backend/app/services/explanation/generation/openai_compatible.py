from __future__ import annotations

from typing import Any
import json
import re

import httpx

from app.services.explanation.generation.provider import (
    ExplanationProviderDescriptor,
    ExplanationProviderHttpError,
    MAX_PROVIDER_RESPONSE_BYTES,
    ExplanationProviderMalformedResponseError,
    ExplanationProviderRateLimitError,
    ExplanationProviderRequest,
    ExplanationProviderResponse,
    ExplanationProviderTimeoutError,
    ExplanationProviderTransportError,
)


_SAFE_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}$")


class OpenAICompatibleChatProvider:
    """One-shot transport adapter for the OpenAI chat-completions wire format."""

    def __init__(
        self,
        *,
        descriptor: ExplanationProviderDescriptor,
        base_url: str,
        api_key: str,
        timeout_seconds: float,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.descriptor = descriptor
        self._endpoint = f"{base_url.rstrip('/')}/chat/completions"
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)

    def __repr__(self) -> str:
        return (
            "OpenAICompatibleChatProvider("
            f"descriptor={self.descriptor!r}, timeout_seconds={self._timeout_seconds!r})"
        )

    async def generate(
        self, request: ExplanationProviderRequest
    ) -> ExplanationProviderResponse:
        payload = {
            "model": self.descriptor.configured_model,
            "messages": [
                {"role": "system", "content": request.system_instruction},
                {"role": "user", "content": request.user_instruction},
            ],
            "response_format": {"type": "json_object"},
            "stream": False,
            "temperature": 0,
            "max_tokens": request.max_output_tokens,
        }
        try:
            async with self._client.stream(
                "POST",
                self._endpoint,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self._timeout_seconds,
            ) as response:
                if response.status_code == 429:
                    raise ExplanationProviderRateLimitError
                if not response.is_success:
                    raise ExplanationProviderHttpError(response.status_code)
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(body) + len(chunk) > MAX_PROVIDER_RESPONSE_BYTES:
                        raise ExplanationProviderMalformedResponseError
                    body.extend(chunk)
        except httpx.TimeoutException:
            raise ExplanationProviderTimeoutError from None
        except httpx.TransportError:
            raise ExplanationProviderTransportError from None

        return _parse_chat_completion(bytes(body))

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()


def _parse_chat_completion(body: bytes) -> ExplanationProviderResponse:
    """Read only the single content field allowed to leave the transport layer."""

    try:
        envelope: Any = json.loads(body)
    except (UnicodeDecodeError, ValueError):
        raise ExplanationProviderMalformedResponseError from None
    if not isinstance(envelope, dict):
        raise ExplanationProviderMalformedResponseError
    choices = envelope.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ExplanationProviderMalformedResponseError
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise ExplanationProviderMalformedResponseError
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ExplanationProviderMalformedResponseError
    observed_model = envelope.get("model")
    if not isinstance(observed_model, str) or _SAFE_MODEL.fullmatch(observed_model) is None:
        observed_model = None
    return ExplanationProviderResponse(content=content, observed_model=observed_model)


__all__ = ["OpenAICompatibleChatProvider"]
