import path from "node:path";
import { defineConfig, devices } from "@playwright/test";

const localE2eBackendUrl = "http://127.0.0.1:8001";
const isCi = Boolean(process.env.CI);
const e2eBackendUrl =
  isCi
    ? process.env.BACKEND_URL ?? "http://127.0.0.1:8000"
    : localE2eBackendUrl;

// Pin the backend for local E2E in the Playwright process as well as the
// spawned Next server. This prevents a stale shell/.env value from routing
// requests to another backend instance.
if (!isCi) {
  process.env.BACKEND_URL = localE2eBackendUrl;
}

const backendServer = {
  command: "python -m uvicorn app.main:app --host 127.0.0.1 --port 8001",
  cwd: path.resolve(__dirname, "../api"),
  url: localE2eBackendUrl + "/api/v1/health/live",
  reuseExistingServer: false,
  timeout: 120_000,
  env: {
    ...process.env,
    APP_ENV: "test",
    RATE_LIMIT_ENABLED: "false",
  },
};

const frontendServer = {
  command:
    "node -e \"require('fs').rmSync('.next',{recursive:true,force:true})\" && npm run build && node .next/standalone/server.js",
  url: "http://localhost:3000",
  reuseExistingServer: false,
  timeout: 120_000,
  stdout: "pipe" as const,
  stderr: "pipe" as const,
  env: {
    ...process.env,
    RATE_LIMIT_ENABLED: "false",
    BACKEND_URL: e2eBackendUrl,
    E2E_HTTP_COOKIES: "1",
  },
};

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  reporter: "html",

  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
  },

  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
      },
    },
  ],

  webServer: isCi
    ? frontendServer
    : [backendServer, frontendServer],
});
