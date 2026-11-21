import{defineConfig,devices}from"@playwright/test";

const backendPython=process.env.PYTHON_EXECUTABLE??"python";

export default defineConfig({
  testDir:"./tests/e2e",
  use:{
    baseURL:process.env.PLAYWRIGHT_BASE_URL??"http://127.0.0.1:3000",
    trace:"retain-on-failure",
  },
  webServer:[
    {
      command:`${backendPython} -m uvicorn app.main:app --host 127.0.0.1 --port 8000`,
      cwd:"../api",
      url:"http://127.0.0.1:8000/api/v1/health/live",
      reuseExistingServer:Boolean(process.env.PLAYWRIGHT_API_SERVER_PRESTARTED)||!process.env.CI,
      env:{
        ...process.env,
        APP_ENV:"test",
        AUTH_REQUIRE_EMAIL_VERIFICATION:"false",
      },
    },
    {
      command:"npm run dev",
      url:"http://127.0.0.1:3000",
      reuseExistingServer:!process.env.CI,
      env:{
        ...process.env,
        BACKEND_API_URL:"http://127.0.0.1:8000",
      },
    },
  ],
  projects:[{name:"chromium",use:{...devices["Desktop Chrome"]}}],
});
