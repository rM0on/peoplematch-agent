import path from "node:path";
import { expect, test } from "@playwright/test";

const api = "http://127.0.0.1:18000/api/v1";
const output = path.resolve(__dirname, "../../docs/images/portfolio-final/06-bad-case-review.png");

test("captures an honest synthetic incomplete-explanation review workflow", async ({ page, request }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const runs = (await (await request.get(`${api}/match-runs?limit=20&offset=0&status=COMPLETED`)).json()).data.items;
  expect(runs).toHaveLength(1);
  const runId = runs[0].run_id;
  const explanationRuns = (await (await request.get(`${api}/match-runs/${runId}/explanation-runs?limit=20&offset=0`)).json()).data.items;
  const explanation = (await (await request.get(`${api}/explanation-runs/${explanationRuns[0].explanation_run_id}`)).json()).data;
  const target = explanation.explanations[0];
  const evidenceReference = target.match_reasons.flatMap((item: { evidence_refs: string[] }) => item.evidence_refs)
    .find((ref: string) => ref.startsWith(`candidate:${target.result_rank}:`));
  expect(evidenceReference).toBeTruthy();

  const feedbackResponse = await request.post(`${api}/feedback`, { data: {
    feedback_type: "explanation", match_run_id: runId, explanation_run_id: explanation.explanation_run_id,
    match_explanation_id: target.match_explanation_id, target_type: "summary", value: "incomplete",
    evidence_reference: evidenceReference,
    comment: "Synthetic review example: the generic summary does not expose the specific evidence source.",
  } });
  expect(feedbackResponse.status()).toBe(201);
  const feedback = (await feedbackResponse.json()).data;
  const createResponse = await request.post(`${api}/bad-cases`, { data: {
    source_type: "feedback", feedback_id: feedback.feedback_id, symptom_code: "incomplete_explanation", severity: "MEDIUM",
  } });
  expect(createResponse.status()).toBe(201);
  let detail = (await createResponse.json()).data;
  expect(detail.evidence_links).toHaveLength(1);
  const commands = [
    { command: "transition", expected_status: "CREATED", expected_revision: 0, status: "REVIEWED", transition_reason: "review_completed" },
    { command: "analysis", expected_status: "REVIEWED", expected_revision: 1, status: "ROOT_CAUSE_IDENTIFIED", transition_reason: "root_cause_supported", analysis: {
      assessment: "supported", root_cause_type: "explanation", root_cause_code: "explanation_incomplete_selection",
      description: "合成样例：摘要只有通用匹配结论，未把已记录的技能来源与岗位要求说明清楚。后续应复核解释选择与展示，而不是改变历史排名。",
      supporting_evidence_link_id: detail.evidence_links[0].evidence_link_id,
    } },
    { command: "resolution", expected_status: "ROOT_CAUSE_IDENTIFIED", expected_revision: 2, status: "ACTION_PLANNED", transition_reason: "action_created", resolution: {
      action_type: "planning_policy_hypothesis", description: "计划检查 summary 的证据选择与呈现；先在独立 synthetic case 验证，再决定是否修改解释策略。", status: "planned",
    } },
  ];
  for (const command of commands) {
    const response = await request.post(`${api}/bad-cases/${detail.bad_case_id}/review`, { data: command });
    expect(response.status(), await response.text()).toBe(200);
    detail = (await response.json()).data;
  }
  expect(detail.status).toBe("ACTION_PLANNED");
  await page.setViewportSize({ width: 1440, height: 1100 });
  await page.goto(`/bad-cases/${detail.bad_case_id}`);
  await expect(page.getByRole("heading", { name: "推荐解释不完整" })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText(/摘要只有通用匹配结论/).first()).toBeVisible();
  await expect(page.getByText(/计划检查 summary 的证据选择与呈现/)).toBeVisible();
  await page.evaluate(() => window.scrollTo({ top: 80, behavior: "instant" }));
  await page.screenshot({ path: output });
  expect(errors).toEqual([]);
});
