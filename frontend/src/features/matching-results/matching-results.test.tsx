import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { MatchingResultsScreen } from "./matching-results-screen";


afterEach(cleanup);

describe("MatchingResultsScreen", () => {
  it("opens on the evidence-first ranking state", () => {
    render(<MatchingResultsScreen />);

    expect(
      screen.getByRole("heading", { name: "Matching Results" }),
    ).toBeTruthy();
    expect(screen.getByText("Design Mock")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Why this rank" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Project evidence" })).toBeTruthy();
    expect(screen.getByText("Grounded explanation")).toBeTruthy();
    expect(screen.getAllByText("Demonstrated").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Partial").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Claim only").length).toBeGreaterThan(0);
  });

  it("updates the evidence detail when a shortlist candidate is selected", async () => {
    const user = userEvent.setup();
    render(<MatchingResultsScreen />);

    await user.click(screen.getByRole("button", { name: /select candidate b/i }));

    expect(screen.getByRole("heading", { name: "Candidate B" })).toBeTruthy();
    expect(screen.getByText("74", { selector: ".overall-score__value" })).toBeTruthy();
    expect(screen.getByText(/workflow automation studio/i)).toBeTruthy();
  });

  it("reveals a compact adjacent-rank comparison", async () => {
    const user = userEvent.setup();
    render(<MatchingResultsScreen />);

    const comparison = screen.getByRole("button", {
      name: /why candidate a ranks above candidate b/i,
    });
    expect(comparison.getAttribute("aria-expanded")).toBe("false");

    await user.click(comparison);

    expect(comparison.getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByText(/stronger project evidence/i)).toBeTruthy();
  });

  it("lets the user inspect a pipeline stage without leaving matching results", async () => {
    const user = userEvent.setup();
    render(<MatchingResultsScreen />);

    const pipeline = screen.getByLabelText("Matching pipeline stages");
    await user.click(within(pipeline).getByRole("button", { name: "LTR" }));

    expect(within(pipeline).getByRole("button", { name: "LTR" }).getAttribute("aria-pressed")).toBe(
      "true",
    );
    expect(screen.getByText(/learned ranking stage/i)).toBeTruthy();
  });

  it("keeps the design-mock context visible outside the desktop sidebar", () => {
    render(<MatchingResultsScreen />);

    expect(screen.getByText("Illustrative data · Design Mock")).toBeTruthy();
  });

  it("keeps the decision trace consistent with each candidate's rerank impact", async () => {
    const user = userEvent.setup();
    render(<MatchingResultsScreen />);

    let trace = screen.getByLabelText("Illustrative rerank transition");
    expect(within(trace).getByText("Retrieved #3")).toBeTruthy();
    expect(within(trace).getByText("Final #1")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: /select candidate b/i }));
    trace = screen.getByLabelText("Illustrative rerank transition");
    expect(within(trace).getByText("Retrieved #2")).toBeTruthy();
    expect(within(trace).getByText("Final #2")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: /select candidate c/i }));
    trace = screen.getByLabelText("Illustrative rerank transition");
    expect(within(trace).getByText("Retrieved #2")).toBeTruthy();
    expect(within(trace).getByText("Final #3")).toBeTruthy();
  });

  it("describes adjacent-rank comparison in the actual ranking direction", async () => {
    const user = userEvent.setup();
    render(<MatchingResultsScreen />);

    await user.click(screen.getByRole("button", { name: /select candidate c/i }));

    expect(
      screen.getByRole("button", { name: /why candidate b ranks above candidate c/i }),
    ).toBeTruthy();
  });

  it("offers a skip link and does not expose an inert job-context control", () => {
    render(<MatchingResultsScreen />);

    expect(
      screen.getByRole("link", { name: "Skip to matching results" }).getAttribute("href"),
    ).toBe("#matching-results");
    expect(screen.queryByRole("button", { name: "Open job context menu" })).toBeNull();
  });

  it("does not present production or performance-impact claims in design-mock content", () => {
    render(<MatchingResultsScreen />);

    expect(document.body.textContent).not.toMatch(/production|high-scale|10x|p95|traffic growth/i);
  });
});
