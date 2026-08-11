import type { HealthResponse } from "@/types/api";


function getApiBaseUrl(): string {
  const configuredUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (!configuredUrl) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL is not configured");
  }
  return configuredUrl.replace(/\/$/, "");
}


export async function fetchBackendHealth(
  signal?: AbortSignal,
): Promise<HealthResponse> {
  const response = await fetch(`${getApiBaseUrl()}/health`, {
    cache: "no-store",
    headers: { Accept: "application/json" },
    signal,
  });

  if (!response.ok) {
    throw new Error(
      `Backend health request failed with status ${response.status}`,
    );
  }

  return (await response.json()) as HealthResponse;
}
