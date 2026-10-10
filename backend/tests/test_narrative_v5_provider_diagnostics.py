"""Diagnostic events expose only bounded provider metadata."""

from __future__ import annotations

import json

from app.services.explanation.generation.provider import (
    ExplanationProviderHttpError, ExplanationProviderRateLimitError,
    ExplanationProviderTimeoutError,
)


def test_http_failure_reports_status_and_allowlisted_code_without_body():
    from narrative_v5_three_candidates import safe_provider_failure

    error = ExplanationProviderHttpError(
        403, provider_error_code="insufficient_quota")
    event = safe_provider_failure(error, task="recruiter_narrative",
                                  model="qwen3.7-plus-2026-05-26",
                                  attempt=1, latency_seconds=0.25)
    assert event["http_status"] == 403
    assert event["provider_error_code"] == "insufficient_quota"
    assert event["safe_category"] == "http_status"
    assert event["received_response"] is True
    assert "Authorization" not in json.dumps(event)


def test_rate_limit_and_timeout_preserve_safe_retry_and_phase():
    from narrative_v5_three_candidates import safe_provider_failure

    limited = safe_provider_failure(
        ExplanationProviderRateLimitError(retry_after_seconds=60),
        task="recruiter_narrative", model="qwen3.7-plus-2026-05-26",
        attempt=1, latency_seconds=0.4)
    assert limited["http_status"] == 429
    assert limited["retry_after_seconds"] == 60
    timeout = safe_provider_failure(
        ExplanationProviderTimeoutError(phase="read", received_response=True, status_code=200),
        task="recruiter_narrative", model="qwen3.7-plus-2026-05-26",
        attempt=2, latency_seconds=120.0)
    assert timeout["safe_category"] == "timeout"
    assert timeout["timeout_phase"] == "read"
    assert timeout["received_response"] is True
    assert timeout["attempt_number"] == 2
