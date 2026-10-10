import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import path from "node:path";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { EvaluationScreen } from "./evaluation-screen";
import { frozenEvaluation } from "./frozen-evaluation";

afterEach(cleanup);

it("projects every displayed mean from the frozen test report", () => {
  const source = readFileSync(path.resolve(process.cwd(), "../data/eval/phase11/runs/20260831T173246Z_test_corrected_final/report.json"));
  const report = JSON.parse(source.toString("utf8"));
  expect(createHash("sha256").update(source).digest("hex")).toBe(frozenEvaluation.sourceSha256);
  expect(report.quality.r2.cohort).toBe("controlled_full_pool_then_judged_condensation");
  for (const row of frozenEvaluation.ranking) {
    const actual = report.quality.r2.strategies[row.id];
    expect(row.ndcgAt5).toBe(actual.judged_condensed_ndcg_at_5.mean);
    expect(row.ndcgAt10).toBe(actual.judged_condensed_ndcg_at_10.mean);
    expect(row.mrrAt10).toBe(actual.judged_condensed_mrr_at_10.mean);
    expect(row.pairwise).toBe(actual.explicit_pairwise_accuracy.mean);
  }
  for (const row of frozenEvaluation.retrieval) {
    expect(row.recallAt10).toBe(report.quality.r1.strategies[row.id].retrieval_recall_at_10.mean);
  }
});

it("communicates the offline result and its limitations", () => {
  render(<EvaluationScreen />);
  expect(screen.getByRole("heading", { level: 1, name: /排序策略/ })).toBeTruthy();
  expect(screen.getByText(/Post-exposure/)).toBeTruthy();
  expect(screen.getByText(/未标注 ≠ 负例/)).toBeTruthy();
  expect(screen.getAllByText(/未采用|未优于/).length).toBeGreaterThan(0);
  expect(document.body.textContent).not.toMatch(/线上提升|生产准确率|匹配准确率 95/);
});
