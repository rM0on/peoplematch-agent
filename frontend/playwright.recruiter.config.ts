import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "recruiter-view-live.spec.ts",
  retries: 0,
  workers: 1,
  reporter: [["list"]],
  use: { ...devices["Desktop Chrome"], baseURL: process.env.RECRUITER_VIEW_URL ?? "http://localhost:3000", trace: "retain-on-failure" },
});
