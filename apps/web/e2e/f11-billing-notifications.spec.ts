import { expect, test, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";

const testPassword = "Secret123456789";

async function createAuthenticatedSession(page: Page) {
  const email = "e2e-f11-" + randomUUID() + "@gmail.com";

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

  const workspaceResponse = await page.request.post(
    "/api/v1/workspaces",
    {
      headers: { Origin: "http://localhost:3000" },
      data: { name: "F11 E2E Workspace " + Date.now() },
    },
  );
  expect(workspaceResponse.status(), await workspaceResponse.text()).toBe(201);
}

test("usage and billing reads live workspace data without demo metrics", async ({ page }) => {
  await createAuthenticatedSession(page);
  await page.goto("/usage-billing");

  await expect(page.getByRole("heading", { name: "Usage & billing" })).toBeVisible();
  await expect(page.getByLabel("Workspace")).toBeEnabled({ timeout: 10_000 });
  await expect(page.getByText("Available plans")).toBeVisible();

  await expect(page.getByText("$49")).toHaveCount(0);
  await expect(page.getByText("74%")).toHaveCount(0);
  await expect(page.getByText("INV-2026-09")).toHaveCount(0);

  const planCards = page.locator("article.card");
  await expect(planCards.first()).toBeVisible({ timeout: 10_000 });
});

test("notification center reads the authenticated notification API", async ({ page }) => {
  await createAuthenticatedSession(page);

  const response = await page.request.get("/api/v1/notifications?limit=10");
  expect(response.status(), await response.text()).toBe(200);

  await page.goto("/dashboard");
  await page.getByRole("button", { name: "Notifications" }).click();

  await expect(page.getByRole("heading", { name: "Notifications" })).toBeVisible();
  await expect(page.getByText("No notifications.")).toHaveCount(1);
});

test("email verification landing page exposes the resend workflow", async ({ page }) => {
  await page.goto("/email-verify");

  await expect(page.getByRole("heading", { name: "Verify your email" })).toBeVisible();
  await expect(page.getByLabel("Email")).toBeVisible();
  await expect(page.getByRole("button", { name: "Send verification email" })).toBeVisible();
});

test("login links to the real password reset request flow", async ({ page }) => {
  await page.goto("/login");

  await page.getByRole("link", { name: "Forgot password?" }).click();

  await expect(page).toHaveURL(/\/password-reset$/);
  await expect(page.getByRole("heading", { name: "Reset your password" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Send reset email" })).toBeVisible();
});

test("password reset confirmation rejects missing reset token", async ({ page }) => {
  await page.goto("/password-reset/confirm");

  await page.getByLabel("New password").fill(testPassword + "A");
  await page.getByLabel("Confirm password").fill(testPassword + "A");
  await page.getByRole("button", { name: "Update password" }).click();

  await expect(page.locator('p[role="alert"]')).toContainText("missing its token");
});
