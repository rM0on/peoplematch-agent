import { expect, test } from "@playwright/test";

const runId = "22326fc2-1766-4c3c-a8f0-2cc81f70849c";

test("persisted trusted recruiter demo remains readable without recapturing frozen screenshots", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const beforeResponse = await page.request.get(`http://localhost:8000/api/v1/match-runs/${runId}`);
  expect(beforeResponse.ok()).toBe(true);
  const before = (await beforeResponse.json()).data;

  await page.setViewportSize({ width: 1440, height: 1024 });
  await page.goto(`/?runId=${runId}`);
  await expect(page.getByRole("heading", { name: "Search Quality Platform Engineer" })).toBeVisible();
  const cards = page.getByRole("navigation", { name: "Top 候选人" }).getByRole("button");
  await expect(cards).toHaveCount(3);
  expect((await cards.allTextContents()).map((value) => value.match(/Candidate \d{3}/)?.[0])).toEqual([
    "Candidate 019", "Candidate 033", "Candidate 006",
  ]);
  await expect(page.getByText("优先人工技术复核").first()).toBeVisible();
  await expect(page.getByText("核心待确认").first()).toBeVisible();
  await page.getByText("查看依据").first().click();
  await expect(page.getByText(/候选项目 ·|岗位要求 ·/).first()).toBeVisible();
  await page.getByText("Engineering View · 排序与来源轨迹").click();
  await expect(page.getByText(/Ranking Model Raw Score/)).toBeVisible();

  const afterResponse = await page.request.get(`http://localhost:8000/api/v1/match-runs/${runId}`);
  expect(afterResponse.ok()).toBe(true);
  const after = (await afterResponse.json()).data;
  expect(after.result_fingerprint).toBe(before.result_fingerprint);
  expect(after.results.map((item: { candidate_id: string; ltr_score_raw: number }) => [item.candidate_id, item.ltr_score_raw]))
    .toEqual(before.results.map((item: { candidate_id: string; ltr_score_raw: number }) => [item.candidate_id, item.ltr_score_raw]));
  expect(errors).toEqual([]);
});

test("trace, evaluation and bad-case routes render their honest boundaries", async ({ page }) => {
  await page.goto(`/agent-run?runId=${runId}`);
  await expect(page.getByText("Persisted Trace", { exact: true })).toBeVisible();
  await expect(page.getByText("Derived Stage Metadata")).toBeVisible();
  await page.goto("/evaluation");
  await expect(page.getByText(/post-exposure/i).first()).toBeVisible();
  await page.goto("/bad-cases");
  await expect(page.getByRole("heading").first()).toBeVisible();
});

test("mobile recruiter view has no page-level horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/?runId=${runId}`);
  await expect(page.getByRole("heading", { name: "Search Quality Platform Engineer" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Top 候选人" }).getByRole("button")).toHaveCount(3);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 2)).toBe(false);
});
