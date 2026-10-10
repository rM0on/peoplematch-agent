import { expect, test } from "@playwright/test";

const runId = process.env.RECRUITER_VIEW_RUN_ID ?? "22326fc2-1766-4c3c-a8f0-2cc81f70849c";

test("fresh trusted Top-3 is readable and matches persisted identity", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const before = (await (await page.request.get(`http://localhost:8000/api/v1/match-runs/${runId}`)).json()).data;
  await page.setViewportSize({ width: 1440, height: 1024 });
  await page.goto(`/?runId=${encodeURIComponent(runId)}`);
  await expect(page.getByRole("heading", { name: "Search Quality Platform Engineer" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("navigation", { name: "Top 候选人" }).getByRole("button")).toHaveCount(3);
  const order = await page.getByRole("navigation", { name: "Top 候选人" }).getByRole("button").allTextContents();
  expect(order.map((text) => text.match(/Candidate \d{3}/)?.[0])).toEqual(["Candidate 019", "Candidate 033", "Candidate 006"]);
  await expect(page.getByText("Candidate 019").first()).toBeVisible();
  await expect(page.getByText("优先人工技术复核").first()).toBeVisible();
  await expect(page.getByText("核心待确认").first()).toBeVisible();
  await expect(page.getByText(/先确认是否有与「evaluation」相关、可说明的证据/)).toBeVisible();
  await expect(page.getByText("高度推荐")).toHaveCount(0);
  await page.screenshot({ path: "../output/recruiter-view-final-1440x1024.png" });
  await page.getByRole("button", { name: /Candidate 033/ }).click();
  await expect(page.getByRole("heading", { name: "Candidate 033" })).toBeVisible();
  await page.getByRole("button", { name: /Candidate 006/ }).click();
  await expect(page.getByRole("heading", { name: "Candidate 006" })).toBeVisible();
  await page.getByText("查看依据").first().click();
  await expect(page.getByText(/候选项目|技能档案|岗位要求/).first()).toBeVisible();
  await page.getByText(/Engineering View · 排序与来源轨迹/).click();
  await expect(page.getByText(/Ranking Model Raw Score/)).toBeVisible();
  const after = (await (await page.request.get(`http://localhost:8000/api/v1/match-runs/${runId}`)).json()).data;
  expect(after.result_fingerprint).toBe(before.result_fingerprint);
  expect(after.results.map((item: { candidate_id: string; ltr_score_raw: number }) => [item.candidate_id, item.ltr_score_raw]))
    .toEqual(before.results.map((item: { candidate_id: string; ltr_score_raw: number }) => [item.candidate_id, item.ltr_score_raw]));
  expect(errors).toEqual([]);
});

test("missing trusted result fails closed without showing a candidate briefing", async ({ page }) => {
  await page.goto("/?runId=missing-run-for-ui-check");
  await expect(page.getByRole("alert").filter({ hasText: "此记录缺少完整的可信结构化结果" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Top 候选人" })).toHaveCount(0);
});

test("agent run separates persisted steps from derived explanation metadata", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1024 });
  await page.goto(`/agent-run?runId=${encodeURIComponent(runId)}`);
  await expect(page.getByText("Persisted Trace", { exact: true })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Derived Stage Metadata")).toBeVisible();
  await expect(page.getByText(/ExplanationRun/).first()).toBeVisible();
  await page.screenshot({ path: "../output/agent-run-final-1440x1024.png" });
});

test("mobile recruiter view remains usable", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/?runId=${encodeURIComponent(runId)}`);
  await expect(page.getByRole("heading", { name: "Search Quality Platform Engineer" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("navigation", { name: "Top 候选人" }).getByRole("button")).toHaveCount(3);
  const hasHorizontalOverflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 2);
  expect(hasHorizontalOverflow).toBe(false);
  await page.screenshot({ path: "../output/recruiter-view-final-mobile-390x844.png" });
});
