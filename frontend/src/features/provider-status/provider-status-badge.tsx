"use client";

import { useEffect, useState } from "react";

import { fetchAIProviderStatus } from "@/lib/provider-status-api";
import type { AIProviderStatus } from "@/types/provider-status";


type ProviderStatusBadgeProps = {
  className?: string;
};

type BadgeCopy = {
  label: string;
  detail: string;
  tone: "loading" | "mock" | "ready" | "warning" | "unavailable";
};

function statusCopy(status: AIProviderStatus): BadgeCopy {
  const tasks = [status.extraction, status.explanation];
  if (tasks.some((task) => !task.configured)) {
    return {
      label: "Real Provider 配置不完整",
      detail: "请在后端本地环境补全 Provider 配置",
      tone: "warning",
    };
  }
  if (tasks.every((task) => task.mode === "mock")) {
    return {
      label: "Deterministic Mock",
      detail: "仅支持已注册安全示例",
      tone: "mock",
    };
  }
  return {
    label: "OpenAI-compatible 已配置",
    detail: status.extraction.arbitrary_input_supported
      ? "支持任意岗位 JD"
      : "岗位理解仍使用 Mock 安全示例",
    tone: "ready",
  };
}

export function ProviderStatusBadge({ className }: ProviderStatusBadgeProps) {
  const [copy, setCopy] = useState<BadgeCopy>({
    label: "正在读取 Provider 状态",
    detail: "只读配置检查",
    tone: "loading",
  });

  useEffect(() => {
    let active = true;
    fetchAIProviderStatus()
      .then((status) => {
        if (active) setCopy(statusCopy(status));
      })
      .catch(() => {
        if (active) {
          setCopy({
            label: "Provider 状态不可用",
            detail: "不阻止推荐请求，以实际调用结果为准",
            tone: "unavailable",
          });
        }
      });
    return () => { active = false; };
  }, []);

  return <aside className={className} aria-label="AI Provider 状态" data-tone={copy.tone}>
    <span aria-hidden="true" />
    <div><strong>{copy.label}</strong><small>{copy.detail}</small></div>
  </aside>;
}
