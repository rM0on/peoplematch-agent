import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchAIProviderStatus } from "./provider-status-api";


function envelope(data: unknown) {
  return new Response(JSON.stringify({
    success: true,
    data,
    error: null,
    request_id: "provider-status-request",
  }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

const mixedStatus = {
  extraction: {
    task: "extraction",
    mode: "openai_compatible",
    configured: true,
    provider_name: "openai_compatible",
    configured_model: "provider-model-v1",
    arbitrary_input_supported: true,
  },
  explanation: {
    task: "explanation",
    mode: "mock",
    configured: true,
    provider_name: "deterministic_mock",
    configured_model: null,
    arbitrary_input_supported: false,
  },
} as const;

describe("fetchAIProviderStatus", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("accepts independently reported extraction and explanation status", async () => {
    const fetchMock = vi.fn().mockResolvedValue(envelope(mixedStatus));
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000/");
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchAIProviderStatus()).resolves.toEqual(mixedStatus);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/system/ai-provider-status",
      expect.objectContaining({ cache: "no-store" }),
    );
  });

  it("rejects an unknown provider mode instead of trusting the payload", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(envelope({
      ...mixedStatus,
      extraction: { ...mixedStatus.extraction, mode: "auto" },
    })));

    await expect(fetchAIProviderStatus()).rejects.toMatchObject({
      code: "invalid_response",
    });
  });

  it("rejects status fields outside the closed public contract", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(envelope({
      ...mixedStatus,
      extraction: { ...mixedStatus.extraction, api_key: "must-not-enter-ui" },
    })));

    await expect(fetchAIProviderStatus()).rejects.toMatchObject({
      code: "invalid_response",
    });
  });
});
