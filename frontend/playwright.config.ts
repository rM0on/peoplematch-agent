import path from "node:path";

import { defineConfig, devices } from "@playwright/test";


const frontendRoot = __dirname;
const repositoryRoot = path.resolve(frontendRoot, "..");
const backendRoot = path.join(repositoryRoot, "backend");
const databaseUrl = process.env.TEST_DATABASE_URL;
const backendUrl = process.env.TASK6_BACKEND_URL ?? "http://127.0.0.1:18000";
const frontendUrl = process.env.TASK6_FRONTEND_URL ?? "http://127.0.0.1:13000";

if (!databaseUrl?.startsWith("postgresql+asyncpg://") || !databaseUrl.includes("peoplematch_task6_")) {
  throw new Error("TEST_DATABASE_URL must identify a disposable peoplematch_task6_ PostgreSQL database");
}

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 90_000,
  expect: { timeout: 10_000 },
  reporter: [["list"]],
  use: {
    ...devices["Desktop Chrome"],
    baseURL: frontendUrl,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: [
    {
      command: `"${path.join(backendRoot, ".venv", "Scripts", "python.exe")}" -m uvicorn app.main:app --host 127.0.0.1 --port 18000`,
      cwd: backendRoot,
      env: {
        ...process.env,
        APP_ENV: "test",
        DATABASE_URL: databaseUrl,
        TEST_DATABASE_URL: databaseUrl,
        CORS_ORIGINS: frontendUrl,
      },
      url: `${backendUrl}/health`,
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: "npm run dev -- --hostname 127.0.0.1 --port 13000",
      cwd: frontendRoot,
      env: { ...process.env, NEXT_PUBLIC_API_BASE_URL: backendUrl },
      url: frontendUrl,
      reuseExistingServer: false,
      timeout: 90_000,
    },
  ],
});
