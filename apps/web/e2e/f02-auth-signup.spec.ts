import { expect, test } from "@playwright/test";
import { randomUUID } from "node:crypto";

test("signup creates an account and the requested workspace", async ({ page }) => {
  const email = "e2e-signup-" + randomUUID() + "@example.com";
  const workspaceName = "E2E Research Lab " + randomUUID().slice(0, 8);

  await page.goto("/signup");

  await page.getByLabel("First name").fill("Test");
  await page.getByLabel("Last name").fill("Researcher");
  await page.getByLabel("Work email").fill(email);
  await page.getByLabel("Password").fill("Secret123456789");
  await page.getByLabel("Workspace name").fill(workspaceName);
  await page.getByLabel("I agree to the terms").check();

  await page.getByRole("button", { name: "Create workspace" }).click();

  await expect(page).toHaveURL(/\/dashboard$/);

  const workspaceResponse = await page.request.get(
    "/api/v1/workspaces",
  );
  expect(
    workspaceResponse.status(),
    await workspaceResponse.text(),
  ).toBe(200);

  const payload = await workspaceResponse.json() as {
    items: Array<{ name: string }>;
  };
  expect(
    payload.items.some((item) => item.name === workspaceName),
  ).toBe(true);
});
