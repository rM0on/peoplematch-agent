import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RecommendationHistoryScreen } from "./recommendation-history-screen";


vi.mock("@/features/phase10/historical-feedback-entry", () => ({
  HistoricalFeedbackEntry: () => <div>已持久化推荐复核组件</div>,
}));

afterEach(cleanup);

describe("RecommendationHistoryScreen", () => {
  it("exposes persisted MatchRun history as a working Chinese navigation destination", () => {
    render(<RecommendationHistoryScreen />);
    expect(screen.getByRole("heading", { name: "推荐记录" })).toBeTruthy();
    expect(screen.getByText("已完成 MatchRun")).toBeTruthy();
    expect(screen.getByText("已持久化推荐复核组件")).toBeTruthy();
    expect(screen.getByRole("link", { name: "推荐记录" }).getAttribute("href")).toBe("/runs");
  });
});
