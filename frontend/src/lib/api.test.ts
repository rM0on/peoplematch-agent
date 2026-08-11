import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchBackendHealth } from "./api";


describe("fetchBackendHealth", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("returns the typed health response from the backend", async () => {
    const payload = {
      success: true,
      data: {
        status: "ok",
        service: "peoplematch-backend",
        version: "0.1.0",
        environment: "development",
      },
      error: null,
      request_id: "health-request-id",
    } as const;
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000/");
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchBackendHealth()).resolves.toEqual(payload);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/health",
      expect.objectContaining({ cache: "no-store" }),
    );
  });

  it("rejects non-successful HTTP responses", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(null, { status: 503 })),
    );

    await expect(fetchBackendHealth()).rejects.toThrow(
      "Backend health request failed with status 503",
    );
  });

  it("rejects when the public API base URL is missing", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "");

    await expect(fetchBackendHealth()).rejects.toThrow(
      "NEXT_PUBLIC_API_BASE_URL is not configured",
    );
  });
});
