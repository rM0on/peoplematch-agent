import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProviderStatusBadge } from "./provider-status-badge";


const statusMocks = vi.hoisted(() => ({ fetchAIProviderStatus: vi.fn() }));

vi.mock("@/lib/provider-status-api", () => ({
  fetchAIProviderStatus: statusMocks.fetchAIProviderStatus,
}));

const task = (overrides: Record<string, unknown> = {}) => ({
  task: "extraction",
  mode: "mock",
  configured: true,
  provider_name: "deterministic_mock",
  configured_model: null,
  arbitrary_input_supported: false,
  ...overrides,
});

afterEach(() => {
  cleanup();
  statusMocks.fetchAIProviderStatus.mockReset();
});

describe("ProviderStatusBadge", () => {
  it("labels configured OpenAI-compatible mode without claiming connectivity", async () => {
    statusMocks.fetchAIProviderStatus.mockResolvedValue({
      extraction: task({
        mode: "openai_compatible",
        provider_name: "openai_compatible",
        configured_model: "provider-model",
        arbitrary_input_supported: true,
      }),
      explanation: task({
        task: "explanation",
        mode: "openai_compatible",
        provider_name: "openai_compatible",
        configured_model: "provider-model",
        arbitrary_input_supported: true,
      }),
    });

    render(<ProviderStatusBadge />);

    expect(await screen.findByText("OpenAI-compatible 已配置")).toBeTruthy();
    expect(screen.getByText("支持任意岗位 JD")).toBeTruthy();
    expect(document.body.textContent).not.toContain("已连接");
  });

  it("discloses deterministic Mock input limitations", async () => {
    statusMocks.fetchAIProviderStatus.mockResolvedValue({
      extraction: task(),
      explanation: task({ task: "explanation" }),
    });

    render(<ProviderStatusBadge />);

    expect(await screen.findByText("Deterministic Mock")).toBeTruthy();
    expect(screen.getByText("仅支持已注册安全示例")).toBeTruthy();
  });

  it("reports incomplete real configuration without naming missing secrets", async () => {
    statusMocks.fetchAIProviderStatus.mockResolvedValue({
      extraction: task({
        mode: "openai_compatible",
        configured: false,
        provider_name: "openai_compatible",
      }),
      explanation: task({ task: "explanation" }),
    });

    render(<ProviderStatusBadge />);

    expect(await screen.findByText("Real Provider 配置不完整")).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/api[_ -]?key|authorization|secret/i);
  });

  it("degrades to a read-only unavailable state when status cannot be loaded", async () => {
    statusMocks.fetchAIProviderStatus.mockRejectedValue(new Error("offline"));

    render(<ProviderStatusBadge />);

    expect(await screen.findByText("Provider 状态不可用")).toBeTruthy();
  });
});
