import { expect, test, type Page } from "@playwright/test";

const testPassword = "Secret123456789";

async function createAuthenticatedSession(page: Page) {
  const email = "e2e-slice1-" + Date.now() + "@gmail.com";

  const registerResponse = await page.request.post(
    "/api/v1/auth/register",
    {
      data: {
        email,
        password: testPassword,
      },
    },
  );
  expect(registerResponse.status(), await registerResponse.text()).toBe(201);

  const loginResponse = await page.request.post(
    "/api/v1/auth/login",
    {
      data: {
        email,
        password: testPassword,
      },
    },
  );
  expect(loginResponse.status(), await loginResponse.text()).toBe(200);

  const workspaceResponse = await page.request.post(
    "/api/v1/workspaces",
    {
      headers: {
        Origin: "http://localhost:3000",
      },
      data: {
        name: "Slice 1 E2E Workspace " + Date.now(),
      },
    },
  );
  expect(
    workspaceResponse.status(),
    await workspaceResponse.text(),
  ).toBe(201);
}

test("workspace creates a real project and opens project-scoped research", async ({
  page,
}) => {
  await createAuthenticatedSession(page);

  await page.goto("/workspace");

  await expect(
    page.getByRole("heading", { name: "Projects and research context" }),
  ).toBeVisible();

  await expect(page.getByLabel("Workspace")).toBeEnabled({
    timeout: 10_000,
  });

  const projectName = "E2E Research " + Date.now();

  await page.getByLabel("Project name").fill(projectName);
  await page.getByLabel("Description").fill("Created by Slice 1 E2E.");
  await page.getByRole("button", { name: "Create project" }).click();

  await expect(
    page.getByText(projectName, { exact: true }),
  ).toBeVisible({ timeout: 10_000 });

  await page
    .getByText(projectName, { exact: true })
    .locator("xpath=ancestor::article")
    .getByRole("link", { name: "Research" })
    .click();

  await expect(page).toHaveURL(/\/research\?projectId=/);
  await expect(
    page.getByLabel("Research question"),
  ).toBeVisible();
  await expect(page.getByText("Project scoped")).toBeVisible();
});
