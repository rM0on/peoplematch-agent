import { DemoApiError } from "@/lib/demo-api";
import type {
  AIProviderStatus,
  AIProviderTaskStatus,
} from "@/types/provider-status";


const taskKeys = [
  "task",
  "mode",
  "configured",
  "provider_name",
  "configured_model",
  "arbitrary_input_supported",
] as const;

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function hasExactKeys(value: Record<string, unknown>, keys: readonly string[]): boolean {
  const actual = Object.keys(value).sort();
  const expected = [...keys].sort();
  return actual.length === expected.length
    && actual.every((key, index) => key === expected[index]);
}

function isTaskStatus(
  value: unknown,
  expectedTask: AIProviderTaskStatus["task"],
): value is AIProviderTaskStatus {
  if (!isObject(value) || !hasExactKeys(value, taskKeys)) return false;
  if (value.task !== expectedTask) return false;
  if (value.mode !== "mock" && value.mode !== "openai_compatible") return false;
  if (typeof value.configured !== "boolean") return false;
  if (
    value.provider_name !== "deterministic_mock"
    && value.provider_name !== "openai_compatible"
    && value.provider_name !== "deepseek"
  ) return false;
  if (value.configured_model !== null && typeof value.configured_model !== "string") return false;
  if (typeof value.arbitrary_input_supported !== "boolean") return false;
  if (value.mode === "mock") {
    return value.configured
      && value.provider_name === "deterministic_mock"
      && value.configured_model === null
      && !value.arbitrary_input_supported;
  }
  return value.provider_name !== "deterministic_mock"
    && value.arbitrary_input_supported === value.configured
    && (value.configured ? typeof value.configured_model === "string" : value.configured_model === null);
}

function isProviderStatus(value: unknown): value is AIProviderStatus {
  return isObject(value)
    && hasExactKeys(value, ["extraction", "explanation"])
    && isTaskStatus(value.extraction, "extraction")
    && isTaskStatus(value.explanation, "explanation");
}

function apiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (!configured) {
    throw new DemoApiError("后端 API 尚未配置。", 0, "api_unconfigured", null);
  }
  return configured.replace(/\/$/, "");
}

export async function fetchAIProviderStatus(): Promise<AIProviderStatus> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}/api/v1/system/ai-provider-status`, {
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
  } catch {
    throw new DemoApiError("无法读取 Provider 状态。", 0, "network_error", null);
  }

  let decoded: unknown;
  try {
    decoded = await response.json();
  } catch {
    throw new DemoApiError("Provider 状态响应无法读取。", response.status, "invalid_response", null);
  }
  if (
    !response.ok
    || !isObject(decoded)
    || decoded.success !== true
    || decoded.error !== null
    || typeof decoded.request_id !== "string"
    || !isProviderStatus(decoded.data)
  ) {
    throw new DemoApiError(
      "Provider 状态响应不符合契约。",
      response.status,
      "invalid_response",
      isObject(decoded) && typeof decoded.request_id === "string" ? decoded.request_id : null,
    );
  }
  return decoded.data;
}
