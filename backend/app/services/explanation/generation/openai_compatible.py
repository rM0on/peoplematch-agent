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
_KNOWN_ERROR_CODES = frozenset({
    "insufficient_quota", "quota_exceeded", "insufficient_balance",
    "rate_limit_exceeded", "rate_limited", "throttling",
    "invalid_api_key", "invalid_model", "model_not_found",
    "permission_denied", "service_unavailable", "internal_error",
})
_MAX_ERROR_DIAGNOSTIC_BYTES = 4096


async def _safe_error_code(response: httpx.Response) -> str | None:
    """Inspect a bounded body, retaining only a known non-secret error code."""
    body = bytearray()
    async for chunk in response.aiter_bytes():
        if len(body) + len(chunk) > _MAX_ERROR_DIAGNOSTIC_BYTES:
            return None
        body.extend(chunk)
    try:
        envelope: Any = json.loads(body)
    except (UnicodeDecodeError, ValueError):
        return None
    if not isinstance(envelope, dict):
        return None
    error = envelope.get("error")
    code = error.get("code") if isinstance(error, dict) else envelope.get("code")
    if not isinstance(code, str):
        return None
    normalized = code.casefold()
    return normalized if normalized in _KNOWN_ERROR_CODES else None


def _safe_retry_after(response: httpx.Response) -> int | None:
    value = response.headers.get("retry-after", "")
    if not value.isascii() or not value.isdecimal() or len(value) > 6:
        return None
    seconds = int(value)
    return seconds if 0 <= seconds <= 86400 else None


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
            "response_format": (
                {"type": "json_schema", "json_schema": {
                    "name": request.response_schema["title"],
                    "strict": True,
                    "schema": request.response_schema,
                }} if request.response_schema is not None else {"type": "json_object"}
            ),
            "stream": False,
            "temperature": 0,
            "max_tokens": request.max_output_tokens,
        }
        received_response = False
        response_status: int | None = None
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
                received_response = True
                response_status = response.status_code
                if response.status_code == 429:
                    raise ExplanationProviderRateLimitError(
                        provider_error_code=await _safe_error_code(response),
                        retry_after_seconds=_safe_retry_after(response),
                    )
                if not response.is_success:
                    raise ExplanationProviderHttpError(
                        response.status_code,
                        provider_error_code=await _safe_error_code(response),
                        retry_after_seconds=_safe_retry_after(response),
                    )
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(body) + len(chunk) > MAX_PROVIDER_RESPONSE_BYTES:
                        raise ExplanationProviderMalformedResponseError
                    body.extend(chunk)
        except httpx.TimeoutException as error:
            phase = (
                "connect" if isinstance(error, httpx.ConnectTimeout) else
                "read" if isinstance(error, httpx.ReadTimeout) else
                "write" if isinstance(error, httpx.WriteTimeout) else
                "pool" if isinstance(error, httpx.PoolTimeout) else "unknown"
            )
            raise ExplanationProviderTimeoutError(
                phase=phase, received_response=received_response,
                status_code=response_status,
            ) from None
        except httpx.TransportError:
            raise ExplanationProviderTransportError from None

        return _parse_chat_completion(bytes(body), status_code=response_status)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()


def _parse_chat_completion(body: bytes, *, status_code: int | None = None) -> ExplanationProviderResponse:
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
    finish_reason = choices[0].get("finish_reason")
    if finish_reason is not None and (
        not isinstance(finish_reason, str)
        or finish_reason not in {
            "stop", "length", "content_filter", "tool_calls", "function_call"
        }
    ):
        finish_reason = "other"
    return ExplanationProviderResponse(
        content=content, observed_model=observed_model,
        http_status_code=status_code,
        finish_reason=finish_reason,
    )


__all__ = ["OpenAICompatibleChatProvider"]
