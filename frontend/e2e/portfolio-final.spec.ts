import path from "node:path";
import { expect, test } from "@playwright/test";

const runId = "22326fc2-1766-4c3c-a8f0-2cc81f70849c";
const destination = path.resolve(__dirname, "../../docs/images/portfolio-final");
const shot = (name: string) => path.join(destination, name);

test("captures persisted Fresh Top-3 recruiter hero, evidence, and engineering", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const before = (await (await page.request.get(`http://localhost:8000/api/v1/match-runs/${runId}`)).json()).data;
  await page.setViewportSize({ width: 1440, height: 1024 });
  await page.goto(`/?runId=${runId}`);
  await expect(page.getByRole("heading", { name: "Search Quality Platform Engineer" })).toBeVisible({ timeout: 30_000 });
  const cards = page.getByRole("navigation", { name: "Top 候选人" }).getByRole("button");
  await expect(cards).toHaveCount(3);
  expect((await cards.allTextContents()).map((value) => value.match(/Candidate \d{3}/)?.[0])).toEqual(["Candidate 019", "Candidate 033", "Candidate 006"]);
  await expect(page.getByText("优先人工技术复核").first()).toBeVisible();
  await expect(page.getByText("核心待确认").first()).toBeVisible();
  await page.screenshot({ path: shot("01-recruiter-view.png") });

  await page.getByText("查看依据").first().click();
  await page.getByText("查看依据").nth(2).click();
  await expect(page.getByText(/候选项目 ·|岗位要求 ·/).first()).toBeVisible();
  await page.setViewportSize({ width: 1440, height: 820 });
  await page.evaluate(() => window.scrollTo({ top: 260, behavior: "instant" }));
  await page.screenshot({ path: shot("02-evidence-provenance.png") });

  await page.setViewportSize({ width: 1440, height: 1024 });
  await page.getByText("Engineering View · 排序与来源轨迹").click();
  await expect(page.getByText("Ranking Model Raw Score：")).toBeVisible();
  await expect(cards.first()).toBeHidden();
  await page.getByText("Ranking Model Raw Score：").scrollIntoViewIfNeeded();
  await page.evaluate(() => window.scrollBy(0, -160));
  await page.screenshot({ path: shot("03-engineering-view.png") });

  const after = (await (await page.request.get(`http://localhost:8000/api/v1/match-runs/${runId}`)).json()).data;
  expect(after.result_fingerprint).toBe(before.result_fingerprint);
  expect(after.results.map((item: { candidate_id: string; ltr_score_raw: number }) => [item.candidate_id, item.ltr_score_raw]))
    .toEqual(before.results.map((item: { candidate_id: string; ltr_score_raw: number }) => [item.candidate_id, item.ltr_score_raw]));
  expect(errors).toEqual([]);
});

test("captures persisted and derived agent stages without fake AgentStep records", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1024 });
  await page.goto(`/agent-run?runId=${runId}`);
  await expect(page.getByText("Persisted Trace", { exact: true })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Derived Stage Metadata")).toBeVisible();
  await page.getByText("Engineering View · 运行身份与排序快照").click();
  await expect(page.getByText("Ranking fingerprint：")).toBeVisible();
  await page.screenshot({ path: shot("04-agent-run.png") });
});

test("captures the frozen post-exposure evaluation with strategy caveats", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1024 });
  await page.goto("/evaluation");
  await expect(page.getByRole("heading", { level: 1, name: /排序策略/ })).toBeVisible();
  await expect(page.getByLabel("LambdaMART 测试结果").getByText("0.9593")).toBeVisible();
  await expect(page.getByText(/Post-exposure/)).toBeVisible();
  await expect(page.getByText(/未优于 LambdaMART/)).toBeVisible();
  await page.screenshot({ path: shot("05-eval-dashboard.png") });
});

test("captures responsive proof without document overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/?runId=${runId}`);
  await expect(page.getByRole("heading", { name: "Search Quality Platform Engineer" })).toBeVisible({ timeout: 30_000 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 2)).toBe(true);
  expect(await page.evaluate(() => { const nav = document.querySelector('aside[aria-label="Primary navigation"] nav'); return nav !== null && nav.scrollWidth <= nav.clientWidth + 2; })).toBe(true);
  const candidates = page.getByRole("navigation", { name: "Top 候选人" }).getByRole("button");
  const first = await candidates.nth(0).boundingBox();
  const second = await candidates.nth(1).boundingBox();
  expect(first?.x).toBe(second?.x);
  await page.evaluate(() => window.scrollTo({ top: 470, behavior: "instant" }));
  await page.screenshot({ path: shot("responsive-recruiter-view-mobile.png") });
});
