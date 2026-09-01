import path from "node:path";
import { expect, test } from "@playwright/test";

const screenshotRoot = path.resolve(__dirname, "..", "..", "screenshots");

test("runs the evidence-aware matching demo through persisted review", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
  await page.setViewportSize({ width: 1440, height: 1024 });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Evidence-aware 人岗匹配" })).toBeVisible();
  await page.getByRole("button", { name: "加载安全示例" }).click();
  await expect(page.getByText("示例数据为 synthetic sandbox，不包含真实个人信息。")).toBeVisible();
  await page.screenshot({ path: path.join(screenshotRoot, "phase12-input-workbench-1440x1024.png"), fullPage: true });
  const matchResponsePromise = page.waitForResponse((response) => response.url().endsWith("/api/v1/match-runs") && response.request().method() === "POST");
  await page.getByRole("button", { name: "开始完整匹配" }).click();
  await expect(page.getByText("raw LTR margin，不是概率")).toBeVisible({ timeout: 150_000 });
  const matchResponse = await matchResponsePromise;
  const created = await matchResponse.json();
  const backendOrigin = new URL(matchResponse.url()).origin;
  const historicalResponse = await page.request.get(`${backendOrigin}/api/v1/match-runs/${created.data.run_id}`);
  expect(historicalResponse.ok()).toBe(true);
  const historical = await historicalResponse.json();
  expect(historical.data.result_fingerprint).toBe(created.data.result_fingerprint);
  expect(historical.data.results).toEqual(created.data.results);
  await expect(page.getByRole("heading", { name: "证据约束解释" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "MatchRun 决策轨迹" })).toBeVisible();
  await page.screenshot({ path: path.join(screenshotRoot, "phase12-hero-matching-results-1440x1280.png"), fullPage: true });
  await page.getByRole("button", { name: "复核历史结果" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText(/只针对已持久化的历史 MatchRun/)).toBeVisible();
  await expect(dialog.getByText("Persisted historical context")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  expect(errors).toEqual([]);
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("heading", { name: "Evidence-aware 人岗匹配" })).toBeVisible();
  await expect(page.getByText("raw LTR margin，不是概率")).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
});

test("shows a recoverable provider failure without leaking provider details", async ({ page }) => {
  await page.route("**/api/v1/candidates/parse", async (route) => {
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        success: false,
        data: null,
        error: { code: "provider_unavailable", message: "upstream Bearer demo-secret", details: null },
        request_id: "phase12-provider-error",
      }),
    });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "加载安全示例" }).click();
  await page.getByRole("button", { name: "开始完整匹配" }).click();
  const alert = page.getByRole("alert").filter({ hasText: "模型服务" });
  await expect(alert).toContainText("模型服务暂不可用");
  await expect(alert).toContainText("phase12-provider-error");
  await expect(alert).not.toContainText("Bearer");
  await expect(page.getByRole("button", { name: "重新尝试" })).toBeVisible();
});
