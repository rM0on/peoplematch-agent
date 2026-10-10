import path from "node:path";
import { defineConfig, devices } from "@playwright/test";

const root = path.resolve(__dirname, "..");
const backend = path.join(root, "backend");
const databaseUrl = process.env.TEST_DATABASE_URL;
const backendUrl = "http://127.0.0.1:18000";
const frontendUrl = "http://127.0.0.1:13000";

if (!databaseUrl?.endsWith("/peoplematch_task6_portfolio_20261009")) {
  throw new Error("Portfolio review capture requires its exact disposable database");
}

export default defineConfig({
  testDir: "./e2e",
  testMatch: "portfolio-bad-case.spec.ts",
  retries: 0,
  workers: 1,
  reporter: [["list"]],
  use: { ...devices["Desktop Chrome"], baseURL: frontendUrl, trace: "retain-on-failure" },
  webServer: [
    {
      command: `"${path.join(backend, ".venv", "Scripts", "python.exe")}" -m uvicorn app.main:app --host 127.0.0.1 --port 18000`,
      cwd: backend,
      env: { ...process.env, APP_ENV: "test", DATABASE_URL: databaseUrl, TEST_DATABASE_URL: databaseUrl, CORS_ORIGINS: frontendUrl },
      url: `${backendUrl}/health`, reuseExistingServer: false, timeout: 60_000,
    },
    {
      command: "npm run dev -- --hostname 127.0.0.1 --port 13000",
      cwd: __dirname,
      env: { ...process.env, NEXT_PUBLIC_API_BASE_URL: backendUrl },
      url: frontendUrl, reuseExistingServer: false, timeout: 90_000,
    },
  ],
});
