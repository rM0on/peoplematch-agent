import path from "node:path";
import { expect, test } from "@playwright/test";

const screenshotRoot = path.resolve(__dirname, "..", "..", "screenshots");

test("adds a Resume to the talent library and runs the JD-query recommendation flow", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
  await page.setViewportSize({ width: 1440, height: 1024 });

  await page.goto("/candidates");
  await expect(page.getByRole("heading", { name: "人才库管理" })).toBeVisible();
  await expect(page.getByText("48 位候选人")).toBeVisible();
  await expect(page.getByText(/Resume 先经过 Structured Profile Extraction/)).toBeVisible();
  await page.screenshot({ path: path.join(screenshotRoot, "phase14-talent-library-1440x1024.png") });
  await page.getByRole("button", { name: "加载中文 Resume 示例" }).click();
  await expect(page.getByLabel("候选人简历文本")).toHaveValue(/PeopleMatch 推荐系统沙箱/);
  await page.getByRole("button", { name: "解析候选人" }).click();
  await expect(page.getByRole("heading", { name: "Structured Profile 预览" })).toBeVisible();
  await expect(page.getByText("候选人演示 001", { exact: true })).toBeVisible();
  await page.screenshot({ path: path.join(screenshotRoot, "phase14-candidate-preview-1440x1024.png") });
  await page.getByRole("button", { name: "确认加入人才库" }).click();
  await expect(page.getByText(/候选人已加入人才库/)).toBeVisible({ timeout: 150_000 });
  await expect(page.getByText(/派生检索索引已刷新：49 位候选人/)).toBeVisible();

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "AI 人才推荐工作台" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "从岗位 Query 到 Top-K 候选人" })).toBeVisible();
  await expect(page.getByText(/岗位 JD 是推荐查询 Query/)).toBeVisible();
  await expect(page.getByText("候选召回", { exact: true })).toBeVisible();
  await expect(page.getByText("LambdaMART 排序", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "推荐工作台" })).toBeVisible();
  await expect(page.getByRole("link", { name: "人才库管理" })).toBeVisible();
  await expect(page.getByRole("link", { name: "推荐记录" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Bad Case 复核" })).toBeVisible();
  await page.screenshot({ path: path.join(screenshotRoot, "phase14-jd-workbench-1440x1024.png") });
  await page.getByRole("button", { name: "加载中文 JD 示例" }).click();
  await expect(page.getByText("示例数据为 synthetic sandbox，不包含真实个人信息。")).toBeVisible();
  await expect(page.getByLabel("岗位描述文本")).toHaveValue(/AI 算法工程师/);
  await expect(page.getByLabel("候选人简历文本")).toHaveCount(0);
  await page.screenshot({ path: path.join(screenshotRoot, "phase14-jd-query-1440x1024.png") });
  const matchResponsePromise = page.waitForResponse((response) => response.url().endsWith("/api/v1/match-runs") && response.request().method() === "POST");
  await page.getByRole("button", { name: "开始推荐" }).click();
  await expect(page.getByText("岗位候选池 Top-K 推荐")).toBeVisible({ timeout: 150_000 });
  await expect(page.getByText(/基础候选池 48 人/)).toBeVisible();
  await expect(page.getByText(/当前索引 49 人/)).toBeVisible();
  await expect(page.getByText(/该分值仅用于候选人排序，不是匹配概率、录用概率或推荐成功率。/)).toBeVisible();
  await expect(page.getByText("高度推荐", { exact: true }).first()).toBeVisible();
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
  await expect(page.getByRole("heading", { name: "推荐优势" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "风险提示" })).toBeVisible();
  await expect(page.getByText("技术证据", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "不可变运行轨迹" })).toBeVisible();
  await expect(page.getByText(/该解释基于候选人 Profile、岗位需求与已持久化 Evidence 生成/)).toBeVisible();
  await expect(page.getByText("该解释使用已记录的人岗匹配证据。")).toBeVisible();
  await expect(page.getByText("This explanation uses recorded matching evidence.")).toHaveCount(0);
  await expect(page.getByText("Recorded candidate and requirement evidence is available.")).toHaveCount(0);
  await expect(page.getByText("A required recorded requirement has no available evidence.")).toHaveCount(0);
  await page.setViewportSize({ width: 1440, height: 1280 });
  await page.getByText("岗位候选池 Top-K 推荐").scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(screenshotRoot, "phase14-top-k-ranking-1440x1280.png") });
  await page.setViewportSize({ width: 1440, height: 1024 });
  await page.getByRole("heading", { name: "为什么推荐该候选人" }).locator("..").screenshot({ path: path.join(screenshotRoot, "phase14-evidence-explanation.png") });
  await page.getByRole("heading", { name: "不可变运行轨迹" }).locator("..").screenshot({ path: path.join(screenshotRoot, "phase14-matchrun-trace.png") });
  await page.getByRole("button", { name: "复核历史结果" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText(/只针对已持久化的历史 MatchRun/)).toBeVisible();
  await expect(dialog.getByLabel("已持久化复核上下文")).toBeVisible();
  await expect(dialog.getByRole("heading", { name: "复核推荐结果" })).toBeVisible();
  await page.screenshot({ path: path.join(screenshotRoot, "phase14-historical-review-1440x1024.png") });
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  expect(errors).toEqual([]);
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("heading", { name: "AI 人才推荐工作台" }).scrollIntoViewIfNeeded();
  await expect(page.getByRole("heading", { name: "AI 人才推荐工作台" })).toBeVisible();
  await page.getByText(/该分值仅用于候选人排序/).scrollIntoViewIfNeeded();
  await expect(page.getByText(/该分值仅用于候选人排序/)).toBeVisible();
  const mobileLayout = await page.evaluate(() => ({
    viewportWidth: document.documentElement.clientWidth,
    documentWidth: document.documentElement.scrollWidth,
    offenders: Array.from(document.querySelectorAll<HTMLElement>("body *")).map((element) => {
      const bounds = element.getBoundingClientRect();
      return { tag: element.tagName, className: element.className, left: bounds.left, right: bounds.right, scrollWidth: element.scrollWidth, clientWidth: element.clientWidth };
    }).filter((item) => item.right > document.documentElement.clientWidth + 1 || item.left < -1 || item.scrollWidth > item.clientWidth + 1).slice(0, 12),
  }));
  expect(mobileLayout.documentWidth, JSON.stringify(mobileLayout.offenders)).toBeLessThanOrEqual(mobileLayout.viewportWidth);
  await page.getByRole("link", { name: "推荐记录" }).click();
  await expect(page).toHaveURL(/\/runs$/);
  await expect(page.getByRole("heading", { name: "推荐记录", exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});

test("shows a recoverable provider failure without leaking provider details", async ({ page }) => {
  await page.route("**/api/v1/jobs/parse", async (route) => {
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
  await page.getByRole("button", { name: "加载中文 JD 示例" }).click();
  await page.getByRole("button", { name: "开始推荐" }).click();
  const alert = page.getByRole("alert").filter({ hasText: "模型服务" });
  await expect(alert).toContainText("模型服务暂不可用");
  await expect(alert).toContainText("phase12-provider-error");
  await expect(alert).not.toContainText("Bearer");
  await expect(page.getByRole("button", { name: "重新尝试" })).toBeVisible();
});
