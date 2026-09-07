import path from "node:path";

import { expect, test } from "@playwright/test";

const screenshotRoot = path.resolve(__dirname, "..", "..", "screenshots");

test("preserves the deterministic mock provider product workflow", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });

  await page.setViewportSize({ width: 1440, height: 1024 });
  await page.goto("/candidates");
  await expect(page.getByRole("heading", { name: "人才库管理" })).toBeVisible();
  await expect(page.getByText("48 位候选人")).toBeVisible();
  await expect(page.getByText("候选人 001")).toBeVisible();
  await page.screenshot({ path: path.join(screenshotRoot, "phase15-talent-library-1440x1024.png") });

  await page.goto("/");
  await expect(page.getByText("Deterministic Mock")).toBeVisible();
  await page.getByRole("button", { name: "加载中文 JD 示例" }).click();
  const matchResponsePromise = page.waitForResponse((response) => response.url().endsWith("/api/v1/match-runs") && response.request().method() === "POST");
  await page.getByRole("button", { name: "开始推荐" }).click();
  await expect(page.getByText("岗位候选池 Top-K 推荐")).toBeVisible({ timeout: 150_000 });
  await expect(page.getByRole("heading", { name: "为什么推荐该候选人" })).toBeVisible();

  const matchResponse = await matchResponsePromise;
  const created = await matchResponse.json();
  const historicalResponse = await page.request.get(`${new URL(matchResponse.url()).origin}/api/v1/match-runs/${created.data.run_id}`);
  const historical = await historicalResponse.json();
  expect(historical.data.result_fingerprint).toBe(created.data.result_fingerprint);
  expect(historical.data.results).toEqual(created.data.results);
  expect(errors).toEqual([]);
});
