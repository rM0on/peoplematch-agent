import path from "node:path";

import { expect, test } from "@playwright/test";

const arbitraryJd = `招聘 AI 应用算法工程师，负责企业知识库与智能招聘场景的 RAG、Embedding 检索和 LLM Agent 工作流。候选人需要熟悉 Python、FastAPI、PostgreSQL 与 Qdrant，并能解释 Retrieval、Feature Engineering 和 LambdaMART Ranking 的设计边界。`;
const screenshotRoot = path.resolve(__dirname, "..", "..", "screenshots");

test("runs an arbitrary JD through the OpenAI-compatible adapters without changing ranking history", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });

  await page.setViewportSize({ width: 1440, height: 1024 });
  await page.goto("/workbench");
  await expect(page.getByText("OpenAI-compatible 已配置")).toBeVisible();
  await page.screenshot({ path: path.join(screenshotRoot, "phase15-jd-provider-status-1440x1024.png") });
  await page.getByLabel("岗位描述文本").fill(arbitraryJd);
  const jobResponsePromise = page.waitForResponse((response) => response.url().endsWith("/api/v1/jobs/parse") && response.request().method() === "POST");
  const matchResponsePromise = page.waitForResponse((response) => response.url().endsWith("/api/v1/match-runs") && response.request().method() === "POST");
  const explanationResponsePromise = page.waitForResponse((response) => /\/api\/v1\/match-runs\/[^/]+\/explanations$/.test(response.url()) && response.request().method() === "POST");
  await page.getByRole("button", { name: "开始推荐" }).click();

  const jobResponse = await jobResponsePromise;
  const jobEnvelope = await jobResponse.json();
  expect(jobEnvelope.data.extraction.provider_kind).toBe("openai_compatible");
  expect(jobEnvelope.data.extraction.prompt_version).toBe("job_extraction_prompt_v1");
  expect(jobEnvelope.data.draft.role_title).toContain("AI");

  const matchResponse = await matchResponsePromise;
  const created = await matchResponse.json();
  await explanationResponsePromise;
  await expect(page.getByText("岗位候选池 Top-K 推荐")).toBeVisible({ timeout: 150_000 });

  const backendOrigin = new URL(matchResponse.url()).origin;
  const historicalResponse = await page.request.get(`${backendOrigin}/api/v1/match-runs/${created.data.run_id}`);
  expect(historicalResponse.ok()).toBe(true);
  const historical = await historicalResponse.json();
  expect(historical.data.result_fingerprint).toBe(created.data.result_fingerprint);
  expect(historical.data.results).toEqual(created.data.results);

  const explanationResponse = await page.request.get(`${backendOrigin}/api/v1/match-runs/${created.data.run_id}/explanation-runs`);
  expect(explanationResponse.ok()).toBe(true);
  const explanationList = await explanationResponse.json();
  expect(explanationList.data.total).toBe(1);
  const detailResponse = await page.request.get(`${backendOrigin}/api/v1/explanation-runs/${explanationList.data.items[0].explanation_run_id}`);
  const detail = await detailResponse.json();
  expect(detail.data.provider_kind).toBe("openai_compatible");
  expect(detail.data.explanations).toHaveLength(5);
  const signatures = detail.data.explanations.map((item: { match_reasons: unknown; risk_points: unknown; missing_skills: unknown; summary: unknown }) =>
    JSON.stringify([item.summary, item.match_reasons, item.risk_points, item.missing_skills]));
  expect(new Set(signatures).size).toBe(5);
  for (const item of detail.data.explanations) {
    expect(item.match_reasons.length).toBeGreaterThan(0);
    expect(item.summary.evidence_refs.length).toBeGreaterThan(0);
    expect(item.risk_points.length + item.missing_skills.length).toBeGreaterThan(0);
  }
  await page.screenshot({ path: path.join(screenshotRoot, "phase15-top-k-recommendation.png"), fullPage: true });
  await page.locator("article[aria-live='polite']").screenshot({ path: path.join(screenshotRoot, "phase15-candidate-detail.png") });
  await page.getByRole("heading", { name: "为什么推荐该候选人" }).locator("..").screenshot({ path: path.join(screenshotRoot, "phase15-evidence-explanation.png") });
  await page.getByRole("heading", { name: "不可变运行轨迹" }).locator("..").screenshot({ path: path.join(screenshotRoot, "phase15-matchrun-trace.png") });
  expect(errors).toEqual([]);
});

test("renders a safe recoverable rate-limit error from the provider workflow", async ({ page }) => {
  await page.goto("/workbench");
  await page.getByLabel("岗位描述文本").fill(`${arbitraryJd} PHASE15_RATE_LIMIT`);
  await page.getByRole("button", { name: "开始推荐" }).click();
  const alert = page.getByRole("alert").filter({ hasText: "AI 服务请求过于频繁" });
  await expect(alert).toContainText("AI 服务请求过于频繁，请稍后重试。");
  await expect(alert).not.toContainText("Bearer");
  await expect(alert).not.toContainText("phase15-private-test-key");
  await expect(page.getByRole("button", { name: "重新尝试" })).toBeVisible();
});
