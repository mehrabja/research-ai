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
  "/search",
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
    const response = await page.request.get(route, { maxRedirects: 0 });

    expect(
      [307, 308],
      `route ${route} should return an auth redirect`,
    ).toContain(response.status());

    const location = response.headers()["location"] ?? "";
    expect(
      location,
      `route ${route} should redirect to login`,
    ).toMatch(/\/login(?:$|\?)/);
  }
});

test("all production app routes respond for an authenticated session", async ({ page }) => {
  test.setTimeout(120_000);
  await createAuthenticatedSession(page);

  for (const route of PROTECTED_ROUTES) {
    const response = await page.request.get(route, {
      timeout: 60_000,
    });

    expect(
      response.status(),
      `route ${route} did not respond successfully`,
    ).toBe(200);
    expect(
      new URL(response.url()).pathname,
      `route ${route} redirected unexpectedly`,
    ).toBe(route);

    const body = await response.text();
    expect(
      body.length,
      `route ${route} returned an empty document`,
    ).toBeGreaterThan(0);
  }
});