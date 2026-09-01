import path from "node:path";
import { defineConfig, devices } from "@playwright/test";

const frontendRoot = __dirname;
const repositoryRoot = path.resolve(frontendRoot, "..");
const backendRoot = path.join(repositoryRoot, "backend");
const databaseUrl = process.env.TEST_DATABASE_URL;
const backendUrl = process.env.PHASE12_BACKEND_URL ?? "http://127.0.0.1:18120";
const frontendUrl = process.env.PHASE12_FRONTEND_URL ?? "http://127.0.0.1:13120";

if (Number.parseInt(process.versions.node.split(".")[0], 10) !== 22) {
  throw new Error(`Node 22 LTS is required for Phase 12 E2E; received ${process.versions.node}`);
}

if (!databaseUrl?.startsWith("postgresql+asyncpg://") || !databaseUrl.includes("peoplematch_phase12_e2e_")) {
  throw new Error("TEST_DATABASE_URL must identify a disposable peoplematch_phase12_e2e_ database");
}

export default defineConfig({
  testDir: "./e2e",
  testMatch: "phase12.spec.ts",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 180_000,
  expect: { timeout: 30_000 },
  reporter: [["list"]],
  use: { ...devices["Desktop Chrome"], baseURL: frontendUrl, trace: "retain-on-failure", screenshot: "only-on-failure" },
  webServer: [
    {
      command: `"${path.join(backendRoot, ".venv", "Scripts", "python.exe")}" -m uvicorn app.main:app --host 127.0.0.1 --port 18120`,
      cwd: backendRoot,
      env: { ...process.env, APP_ENV: "test", DATABASE_URL: databaseUrl, TEST_DATABASE_URL: databaseUrl, CORS_ORIGINS: frontendUrl },
      url: `${backendUrl}/health`, reuseExistingServer: false, timeout: 120_000,
    },
    {
      command: "npm run dev -- --hostname 127.0.0.1 --port 13120",
      cwd: frontendRoot,
      env: { ...process.env, NEXT_PUBLIC_API_BASE_URL: backendUrl },
      url: frontendUrl, reuseExistingServer: false, timeout: 120_000,
    },
  ],
});
