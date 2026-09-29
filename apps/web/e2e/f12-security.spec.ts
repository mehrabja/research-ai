import { expect, test, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";

const testPassword = "Secret123456789";

async function createAuthenticatedSession(page: Page) {
  const email = "e2e-f12-" + randomUUID() + "@example.com";

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

  return { email };
}

test("settings security surface reads live account and security state", async ({ page }) => {
  const { email } = await createAuthenticatedSession(page);

  await page.goto("/settings");

  await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
  await expect(page.getByText(email)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Two-factor authentication" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Connected accounts" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Active sessions" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Personal API tokens" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Security activity" })).toBeVisible();

  await expect(page.getByText("API tokens", { exact: true })).toHaveCount(0);
});

test("security APIs expose sessions, MFA, API tokens, OAuth accounts and activity", async ({ page }) => {
  await createAuthenticatedSession(page);

  const endpoints = [
    "/api/v1/auth/sessions",
    "/api/v1/auth/mfa",
    "/api/v1/auth/api-tokens",
    "/api/v1/auth/oauth/accounts",
    "/api/v1/auth/activity?limit=50",
  ];

  for (const endpoint of endpoints) {
    const response = await page.request.get(endpoint);
    expect(response.status(), endpoint + ": " + await response.text()).toBe(200);
  }
});

test("API tokens can be created and revoked through the live contract", async ({ page }) => {
  await createAuthenticatedSession(page);

  const name = "F12 E2E " + randomUUID();
  const createResponse = await page.request.post(
    "/api/v1/auth/api-tokens",
    { data: { name } },
  );
  expect(createResponse.status(), await createResponse.text()).toBe(201);

  const created = await createResponse.json() as {
    id: string;
    name: string;
    token: string;
    token_prefix: string;
  };

  expect(created.name).toBe(name);
  expect(created.token).toMatch(/^rai_/);
  expect(created.token_prefix).toBe(created.token.slice(0, 12));

  const revokeResponse = await page.request.delete(
    "/api/v1/auth/api-tokens/" + created.id,
  );
  expect(revokeResponse.status(), await revokeResponse.text()).toBe(204);
});

test("MFA setup returns a real authenticator secret and recovery codes", async ({ page }) => {
  await createAuthenticatedSession(page);

  const setupResponse = await page.request.post("/api/v1/auth/mfa/setup", {
    data: {},
  });
  expect(setupResponse.status(), await setupResponse.text()).toBe(200);

  const setup = await setupResponse.json() as {
    secret: string;
    provisioning_uri: string;
    recovery_codes: string[];
  };

  expect(setup.secret.length).toBeGreaterThan(10);
  expect(setup.provisioning_uri).toContain("otpauth://");
  expect(setup.recovery_codes.length).toBeGreaterThan(0);
});

test("OAuth start endpoints return signed-in provider authorization URLs", async ({ page }) => {
  await createAuthenticatedSession(page);

  for (const provider of ["google", "github"]) {
    const response = await page.request.get(
      "/api/v1/auth/oauth/" + provider + "/start",
    );
    expect(response.status(), provider + ": " + await response.text()).toBe(200);

    const payload = await response.json() as {
      provider: string;
      authorization_url: string;
      state: string;
      code_verifier: string;
    };

    expect(payload.provider).toBe(provider);
    expect(payload.authorization_url).toContain(
      provider === "google" ? "accounts.google.com" : "github.com",
    );
    expect(payload.authorization_url).toContain("code_challenge=");
    expect(payload.authorization_url).toContain("code_challenge_method=S256");
    expect(payload.state.startsWith(provider + ".")).toBe(true);
    expect(payload.code_verifier.length).toBeGreaterThanOrEqual(43);
  }
});


test("server oauth start route stores the verifier in an HttpOnly cookie", async ({ page }) => {
  const response = await page.request.get("/oauth/google/start", {
    maxRedirects: 0,
  });

  expect([302, 307]).toContain(response.status());
  expect(response.headers()["location"]).toMatch(/^https:\/\/accounts\.google\.com\/o\/oauth2/);

  const cookies = await page.context().cookies();
  const oauthCookie = cookies.find((cookie) => cookie.name === "research_ai_oauth_google");

  expect(oauthCookie).toBeDefined();
  expect(oauthCookie?.httpOnly).toBe(true);
  expect(oauthCookie?.path).toBe("/oauth/google/callback");
});

test("login buttons start the server OAuth route", async ({ page }) => {
  const startRequest = page.waitForRequest("**/oauth/google/start");

  await page.goto("/login");
  await page.getByRole("button", { name: "Continue with Google" }).click();

  await startRequest;
});


test("authenticated shell can sign out and clears the session", async ({ page }) => {
  await createAuthenticatedSession(page);
  await page.goto("/dashboard");

  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\\/login$/);

  const meAfterLogout = await page.request.get("/api/v1/auth/me");
  expect(meAfterLogout.status()).toBe(401);
});
