import path from "node:path";
import { defineConfig, devices } from "@playwright/test";

const localE2eBackendUrl = "http://127.0.0.1:8001";

const backendServer = {
  command: "python -m uvicorn app.main:app --host 127.0.0.1 --port 8001",
  cwd: path.resolve(__dirname, "../api"),
  url: localE2eBackendUrl + "/api/v1/health/live",
  reuseExistingServer: false,
  timeout: 120_000,
};

const frontendServer = {
  command: "npm run build && node .next/standalone/server.js",
  url: "http://localhost:3000",
  reuseExistingServer: true,
  timeout: 120_000,
  ...(process.env.CI
    ? {}
    : {
        env: {
          BACKEND_URL: localE2eBackendUrl,
        },
      }),
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

  webServer: process.env.CI
    ? frontendServer
    : [backendServer, frontendServer],
});