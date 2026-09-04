import path from "node:path";
import { expect, test } from "@playwright/test";

const screenshotRoot = path.resolve(__dirname, "..", "..", "screenshots");

test("runs the Job-query recommendation demo through persisted review", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
  await page.setViewportSize({ width: 1440, height: 1024 });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "AI 人岗匹配推荐工作台" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "从岗位 Query 到 Top-K 候选人" })).toBeVisible();
  await expect(page.getByText(/岗位 JD 是推荐查询 Query/)).toBeVisible();
  await expect(page.getByText("候选召回", { exact: true })).toBeVisible();
  await expect(page.getByText("LambdaMART 排序", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "推荐工作台" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Bad Case 复核" })).toBeVisible();
  await page.screenshot({ path: path.join(screenshotRoot, "phase13-product-home-1440x1024.png") });
  await page.getByRole("button", { name: "加载中文安全示例" }).click();
  await expect(page.getByText("示例数据为 synthetic sandbox，不包含真实个人信息。")).toBeVisible();
  await expect(page.getByLabel("候选人简历文本")).toHaveValue(/PeopleMatch 推荐系统沙箱/);
  await expect(page.getByLabel("岗位描述文本")).toHaveValue(/AI 算法工程师/);
  await page.screenshot({ path: path.join(screenshotRoot, "phase13-chinese-input-1440x1024.png") });
  const matchResponsePromise = page.waitForResponse((response) => response.url().endsWith("/api/v1/match-runs") && response.request().method() === "POST");
  await page.getByRole("button", { name: "开始完整匹配" }).click();
  await expect(page.getByText("岗位候选池 Top-K 推荐")).toBeVisible({ timeout: 150_000 });
  await expect(page.getByText(/基础候选池 48 人/)).toBeVisible();
  await expect(page.getByText(/该分值仅用于候选人排序，不是匹配概率、录用概率或推荐成功率。/)).toBeVisible();
  await expect(page.getByText(/候选人 00[1-9]/).first()).toBeVisible();
  await expect(page.getByText(/技术 ID · cand_/).first()).toBeVisible();
  const matchResponse = await matchResponsePromise;
  const created = await matchResponse.json();
  const backendOrigin = new URL(matchResponse.url()).origin;
  const historicalResponse = await page.request.get(`${backendOrigin}/api/v1/match-runs/${created.data.run_id}`);
  expect(historicalResponse.ok()).toBe(true);
  const historical = await historicalResponse.json();
  expect(historical.data.result_fingerprint).toBe(created.data.result_fingerprint);
  expect(historical.data.results).toEqual(created.data.results);
  await expect(page.getByRole("heading", { name: "为什么推荐该候选人" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "不可变运行轨迹" })).toBeVisible();
  await expect(page.getByText(/该解释基于候选人已有项目、技能和岗位需求证据生成/)).toBeVisible();
  await expect(page.getByText("该解释使用已记录的人岗匹配证据。")).toBeVisible();
  await expect(page.getByText("This explanation uses recorded matching evidence.")).toHaveCount(0);
  await page.setViewportSize({ width: 1440, height: 1280 });
  await page.getByText("岗位候选池 Top-K 推荐").scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(screenshotRoot, "phase13-top-k-ranking-1440x1280.png") });
  await page.setViewportSize({ width: 1440, height: 1024 });
  await page.getByRole("heading", { name: "为什么推荐该候选人" }).locator("..").screenshot({ path: path.join(screenshotRoot, "phase13-evidence-explanation.png") });
  await page.getByRole("heading", { name: "不可变运行轨迹" }).locator("..").screenshot({ path: path.join(screenshotRoot, "phase13-matchrun-trace.png") });
  await page.getByRole("button", { name: "复核历史结果" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText(/只针对已持久化的历史 MatchRun/)).toBeVisible();
  await expect(dialog.getByLabel("已持久化复核上下文")).toBeVisible();
  await expect(dialog.getByRole("heading", { name: "复核推荐结果" })).toBeVisible();
  await page.screenshot({ path: path.join(screenshotRoot, "phase13-historical-review-1440x1024.png") });
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  expect(errors).toEqual([]);
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("heading", { name: "AI 人岗匹配推荐工作台" }).scrollIntoViewIfNeeded();
  await expect(page.getByRole("heading", { name: "AI 人岗匹配推荐工作台" })).toBeVisible();
  await page.getByText(/该分值仅用于候选人排序/).scrollIntoViewIfNeeded();
  await expect(page.getByText(/该分值仅用于候选人排序/)).toBeVisible();
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
  await page.getByRole("button", { name: "加载中文安全示例" }).click();
  await page.getByRole("button", { name: "开始完整匹配" }).click();
  const alert = page.getByRole("alert").filter({ hasText: "模型服务" });
  await expect(alert).toContainText("模型服务暂不可用");
  await expect(alert).toContainText("phase12-provider-error");
  await expect(alert).not.toContainText("Bearer");
  await expect(page.getByRole("button", { name: "重新尝试" })).toBeVisible();
});
