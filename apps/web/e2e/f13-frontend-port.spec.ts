import { expect, test, type Page } from "@playwright/test";

const testPassword = "Secret123456789";

const PROTECTED_ROUTES = [
  "/ai-studio",
  "/citations",
  "/collaboration",
  "/dashboard",
  "/evidence",
  "/files",
  "/final-review",
  "/generate",
  "/humanize",
  "/jobs",
  "/knowledge",
  "/literature",
  "/manuscript",
  "/pdf-workspace",
  "/plan",
  "/publication",
  "/research",
  "/research-canvas",
  "/settings",
  "/sources",
  "/team",
  "/translate",
  "/usage-billing",
  "/workspace",
];

async function createAuthenticatedSession(page: Page) {
  const email = `e2e-f13-${Date.now()}-${Math.random().toString(36).slice(2)}@example.com`;

  const registerResponse = await page.request.post(
    "/api/v1/auth/register",
    { data: { email, password: testPassword } },
  );
  expect(registerResponse.status(), await registerResponse.text()).toBe(201);

  const loginResponse = await page.request.post(
    "/api/v1/auth/login",
    { data: { email, password: testPassword } },
  );
  expect(loginResponse.status(), await loginResponse.text()).toBe(200);

  return email;
}

test("all production app routes require authentication", async ({ page }) => {
  await page.context().clearCookies();

  for (const route of PROTECTED_ROUTES) {
    await page.goto(route);
    await expect(page, `route ${route} should redirect to login`).toHaveURL(/\/login$/);
  }
});

test("all production app routes render for an authenticated session", async ({ page }) => {
  await createAuthenticatedSession(page);

  for (const route of PROTECTED_ROUTES) {
    const response = await page.goto(route, {
      waitUntil: "domcontentloaded",
    });

    expect(response, `route ${route} returned no response`).not.toBeNull();
    expect(response?.status(), `route ${route} did not render successfully`).toBe(200);
    await expect(page, `route ${route} navigated away unexpectedly`).toHaveURL(
      new RegExp(route.replaceAll("/", "\\/") + "$"),
    );
  }
});
