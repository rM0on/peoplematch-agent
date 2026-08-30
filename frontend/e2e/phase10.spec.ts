import path from "node:path";

import { expect, type APIRequestContext, type Page, test } from "@playwright/test";


const apiBase = process.env.TASK6_BACKEND_URL ?? "http://127.0.0.1:18000";
const screenshots = path.resolve(__dirname, "..", "..", "screenshots");

type BrowserSignals = { consoleErrors: string[]; pageErrors: string[]; failedRequests: string[] };

function monitor(page: Page): BrowserSignals {
  const signals: BrowserSignals = { consoleErrors: [], pageErrors: [], failedRequests: [] };
  page.on("console", (message) => { if (message.type() === "error") signals.consoleErrors.push(message.text()); });
  page.on("pageerror", (error) => signals.pageErrors.push(error.message));
  page.on("requestfailed", (request) => signals.failedRequests.push(`${request.method()} ${request.url()} ${request.failure()?.errorText ?? "failed"}`));
  return signals;
}

async function expectNoBrowserErrors(signals: BrowserSignals, allowedStatuses: number[] = []) {
  const allowedConsoleErrors = signals.consoleErrors.filter((message) => (
    allowedStatuses.some((status) => message.includes(`status of ${status}`))
  ));
  const unexpectedConsoleErrors = signals.consoleErrors.filter((message) => (
    !allowedStatuses.some((status) => message.includes(`status of ${status}`))
  ));
  expect(allowedConsoleErrors).toHaveLength(allowedStatuses.length);
  expect(unexpectedConsoleErrors).toEqual([]);
  expect(signals.pageErrors).toEqual([]);
  expect(signals.failedRequests).toEqual([]);
}

async function expectNoHorizontalOverflow(page: Page) {
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
}

async function historicalContext(request: APIRequestContext) {
  const runsResponse = await request.get(`${apiBase}/api/v1/match-runs?limit=20&offset=0&status=COMPLETED`);
  expect(runsResponse.ok()).toBeTruthy();
  const runSummary = (await runsResponse.json()).data.items[0];
  const run = (await (await request.get(`${apiBase}/api/v1/match-runs/${runSummary.run_id}`)).json()).data;
  const explanationRuns = (await (await request.get(`${apiBase}/api/v1/match-runs/${run.run_id}/explanation-runs?limit=20&offset=0`)).json()).data.items;
  const explanation = (await (await request.get(`${apiBase}/api/v1/explanation-runs/${explanationRuns[0].explanation_run_id}`)).json()).data;
  return { run, explanation };
}

async function createExplanationCase(request: APIRequestContext) {
  const { run, explanation } = await historicalContext(request);
  const target = explanation.explanations[0];
  const evidenceReference = [
    ...target.summary.evidence_refs,
    ...target.match_reasons.flatMap((item: { evidence_refs: string[] }) => item.evidence_refs),
  ].find((reference) => reference.startsWith(`candidate:${target.result_rank}:`));
  expect(evidenceReference).toBeTruthy();
  const feedbackResponse = await request.post(`${apiBase}/api/v1/feedback`, { data: {
    feedback_type: "explanation",
    match_run_id: run.run_id,
    explanation_run_id: explanation.explanation_run_id,
    match_explanation_id: target.match_explanation_id,
    target_type: "summary",
    value: "unsupported",
    evidence_reference: evidenceReference,
  } });
  expect(feedbackResponse.status()).toBe(201);
  const feedback = (await feedbackResponse.json()).data;
  const caseResponse = await request.post(`${apiBase}/api/v1/bad-cases`, { data: {
    source_type: "feedback",
    feedback_id: feedback.feedback_id,
    symptom_code: "unsupported_explanation",
    severity: "HIGH",
  } });
  expect(caseResponse.status()).toBe(201);
  return (await caseResponse.json()).data;
}

test.describe.serial("Phase 10 product integration", () => {
  test("reviews a persisted recommendation through VERIFIED with append-only history", async ({ page }) => {
    const signals = monitor(page);
    await page.setViewportSize({ width: 1440, height: 1024 });
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Matching Results" })).toBeVisible();
    const reviewTrigger = page.getByRole("button", { name: "Review persisted history" });
    await reviewTrigger.click();
    const feedbackDialog = page.getByRole("dialog");
    const closeFeedbackDialog = feedbackDialog.getByRole("button", { name: "Close" });
    await expect(feedbackDialog).toBeVisible();
    await expect(closeFeedbackDialog).toBeFocused();
    await expect.poll(() => page.evaluate(() => document.querySelector('[role="dialog"]')?.contains(document.activeElement))).toBe(true);
    await expectNoHorizontalOverflow(page);
    await expect(page.getByText("Persisted historical context")).toBeVisible();
    await page.keyboard.press("Shift+Tab");
    await expect(feedbackDialog.getByRole("button", { name: "Submit feedback" })).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(closeFeedbackDialog).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(feedbackDialog).toBeHidden();
    await expect(reviewTrigger).toBeFocused();
    await reviewTrigger.click();
    await expect(feedbackDialog).toBeVisible();
    await expect(closeFeedbackDialog).toBeFocused();
    await expect(page.getByText("Persisted historical context")).toBeVisible();
    await page.getByRole("tab", { name: "Explanation" }).click();
    await page.getByLabel("Historical evidence reference").selectOption({ index: 1 });
    await page.getByLabel("Verdict").selectOption("unsupported");
    await page.screenshot({ path: path.join(screenshots, "phase10-task6-feedback-review-1440x1024.png") });
    await page.getByRole("button", { name: "Submit feedback" }).click();
    await expect(page.getByText("Feedback recorded")).toBeVisible();
    await page.getByRole("button", { name: "Create bad case" }).click();
    await page.getByRole("button", { name: "Confirm case creation" }).click();
    await page.getByRole("link", { name: "Open bad case" }).click();

    await expect(page).toHaveURL(/\/bad-cases\//);
    await expect(page.getByText("CREATED", { exact: true }).first()).toBeVisible();
    await page.getByRole("button", { name: "Mark reviewed" }).click();
    await expect(page.getByText("REVIEWED", { exact: true }).first()).toBeVisible();
    await page.getByRole("button", { name: "Add analysis" }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.getByLabel("Assessment", { exact: true }).selectOption("confirmed");
    await page.getByLabel("Supporting historical evidence").selectOption({ index: 1 });
    await page.getByLabel("Assessment description").fill("Confirmed against the frozen case evidence.");
    await page.getByRole("button", { name: "Save analysis" }).click();
    await expect(page.getByLabel("Current effective analysis")).toContainText("confirmed");
    await page.getByRole("button", { name: "Identify root cause" }).click();
    await expect(page.getByText("ROOT_CAUSE_IDENTIFIED", { exact: true }).first()).toBeVisible();
    await page.getByRole("button", { name: "Plan resolution" }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.getByLabel("Action status").selectOption("planned");
    await page.getByLabel("Action description").fill("Plan a bounded grounding integrity correction.");
    await page.getByRole("button", { name: "Save resolution action" }).click();
    await expect(page.getByText("planned", { exact: true }).first()).toBeVisible();
    await page.getByRole("button", { name: "Confirm action planned" }).click();
    await expect(page.getByText("ACTION_PLANNED", { exact: true }).first()).toBeVisible();
    await page.getByRole("button", { name: "Update resolution" }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.getByLabel("Action status").selectOption("completed");
    await page.getByLabel("Action description").fill("Case-specific grounding correction completed.");
    await page.getByLabel("Safe change reference").fill("commit:task6-case-change");
    await page.getByRole("button", { name: "Save resolution action" }).click();
    await expect(page.getByText("completed", { exact: true }).first()).toBeVisible();
    await page.getByRole("button", { name: "Resolve case" }).click();
    await expect(page.getByText("RESOLVED", { exact: true }).first()).toBeVisible();
    await page.getByRole("button", { name: "Verify case" }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.getByLabel("Immutable verification reference").fill("commit:task6-case-verification");
    await page.getByRole("dialog").getByRole("button", { name: "Verify case" }).click();

    await expect(page.getByText("VERIFIED", { exact: true }).first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "unsupported explanation" })).toBeFocused();
    await page.reload();
    await expect(page.getByText("Verification: commit:task6-case-verification")).toBeVisible();
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: path.join(screenshots, "phase10-task6-bad-case-detail-1440x1024.png") });
    await expectNoHorizontalOverflow(page);
    await page.setViewportSize({ width: 1024, height: 768 });
    await expectNoHorizontalOverflow(page);
    await page.setViewportSize({ width: 1440, height: 1024 });
    await page.getByRole("link", { name: "Bad Cases" }).click();
    await expect(page.getByRole("heading", { name: "Bad Case Review" })).toBeVisible();
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: path.join(screenshots, "phase10-task6-bad-case-list-1440x1024.png") });
    await expectNoHorizontalOverflow(page);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: path.join(screenshots, "phase10-task6-bad-case-list-390x844.png") });
    await expectNoHorizontalOverflow(page);
    await expectNoBrowserErrors(signals);
  });

  test("rejects a stale reviewer and exposes a safe semantic 422", async ({ page, request }) => {
    const signals = monitor(page);
    const createdCase = await createExplanationCase(request);
    await page.setViewportSize({ width: 1440, height: 1024 });
    await page.goto(`/bad-cases/${createdCase.bad_case_id}`);
    await expect(page.getByText("CREATED", { exact: true }).first()).toBeVisible();

    const competing = await request.post(`${apiBase}/api/v1/bad-cases/${createdCase.bad_case_id}/review`, { data: {
      command: "transition",
      expected_status: "CREATED",
      expected_revision: 0,
      status: "REVIEWED",
      transition_reason: "review_completed",
    } });
    expect(competing.status()).toBe(200);
    await page.getByRole("button", { name: "Mark reviewed" }).click();
    await expect(page.getByText("This case changed since you opened it.")).toBeVisible();
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: path.join(screenshots, "phase10-task6-stale-conflict-1440x1024.png") });
    await page.getByRole("button", { name: "Refresh latest case" }).click();
    await expect(page.getByText("REVIEWED", { exact: true }).first()).toBeVisible();

    const persisted = (await (await request.get(`${apiBase}/api/v1/bad-cases/${createdCase.bad_case_id}`)).json()).data;
    expect(persisted.revision).toBe(1);
    expect(persisted.transitions).toHaveLength(1);

    await page.getByRole("button", { name: "Add analysis" }).click();
    await page.getByLabel("Assessment", { exact: true }).selectOption("supported");
    await page.getByLabel("Root-cause type").selectOption("retrieval");
    await page.getByLabel("Supporting historical evidence").selectOption({ index: 1 });
    await page.getByLabel("Assessment description").fill("Adversarial incompatible historical evidence.");
    await page.getByRole("button", { name: "Save analysis" }).click();
    await expect(page.getByRole("dialog").getByRole("alert")).toContainText(/evidence|retrieval|support/i);
    await expectNoHorizontalOverflow(page);
    await expectNoBrowserErrors(signals, [409, 422]);
  });
});
