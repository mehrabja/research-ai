import { expect, test, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";

const testPassword = "Secret123456789";

async function createAuthenticatedSession(page: Page) {
  const email = "e2e-slice1-" + randomUUID() + "@gmail.com";

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

test("literature page reads the selected project corpus from the backend", async ({
  page,
}) => {
  await createAuthenticatedSession(page);

  await page.goto("/workspace");
  await expect(page.getByLabel("Workspace")).toBeEnabled({
    timeout: 10_000,
  });

  const projectName = "E2E Literature " + Date.now();
  await page.getByLabel("Project name").fill(projectName);
  await page.getByRole("button", { name: "Create project" }).click();

  await expect(page.getByText(projectName, { exact: true })).toBeVisible({
    timeout: 10_000,
  });

  await page.goto("/literature");

  await expect(
    page.getByRole("heading", { name: "Literature map" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Literature corpus" }),
  ).toBeVisible();
  await expect(
    page.getByText("Current project corpus"),
  ).toBeVisible();
  await expect(
    page.getByText("No literature items exist for this project yet."),
  ).toBeVisible();

  await expect(page.getByText("248", { exact: true })).toHaveCount(0);
  await expect(page.getByText("1,931", { exact: true })).toHaveCount(0);
});

test("files page creates a real folder and uploads a real file", async ({
  page,
}) => {
  await createAuthenticatedSession(page);

  await page.goto("/workspace");
  await expect(page.getByLabel("Project name")).toBeEnabled({
    timeout: 10_000,
  });

  const projectName = "E2E Files " + Date.now();
  await page.getByLabel("Project name").fill(projectName);
  await page.getByRole("button", { name: "Create project" }).click();

  await expect(page.getByText(projectName, { exact: true })).toBeVisible({
    timeout: 10_000,
  });

  await page.goto("/files");
  await expect(
    page.getByRole("heading", { name: "Files & intelligence", exact: true }).first(),
  ).toBeVisible();

  await page.getByLabel("Folder name").fill("e2e-data");
  await page.getByRole("button", { name: "Create folder" }).click();
  await expect(
    page.getByLabel("Folder").locator("option", { hasText: "e2e-data" }),
  ).toHaveCount(1, { timeout: 10_000 });

  await page.getByLabel("Folder", { exact: true }).selectOption({
    label: "e2e-data",
  });

  await page.locator('input[type="file"]').setInputFiles({
    name: "slice3-check.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("Slice 3 integration file."),
  });

  await expect(page.getByText("slice3-check.txt", { exact: true })).toBeVisible({
    timeout: 10_000,
  });

  await expect(page.getByText("248", { exact: true })).toHaveCount(0);
  await expect(page.getByText("36 files", { exact: false })).toHaveCount(0);
});

test("evidence page uses the real citation matrix and has no synthetic counters", async ({
  page,
}) => {
  await createAuthenticatedSession(page);

  await page.goto("/evidence");

  await expect(
    page.getByRole("heading", { name: "Evidence", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Evidence matrix")).toBeVisible();

  await expect(page.getByText("86", { exact: true })).toHaveCount(0);
  await expect(page.getByText("312", { exact: true })).toHaveCount(0);
  await expect(page.getByText("7", { exact: true })).toHaveCount(0);
});

test("plan page reads real project plan state without synthetic metrics", async ({
  page,
}) => {
  await createAuthenticatedSession(page);

  await page.goto("/workspace");
  await expect(page.getByLabel("Project name")).toBeEnabled({
    timeout: 10_000,
  });

  const projectName = "E2E Plan " + Date.now();
  await page.getByLabel("Project name").fill(projectName);
  await page.getByRole("button", { name: "Create project" }).click();

  await expect(page.getByText(projectName, { exact: true })).toBeVisible({
    timeout: 10_000,
  });

  await page.goto("/plan");

  await expect(
    page.getByRole("heading", { name: "Research plan", exact: true }).first(),
  ).toBeVisible();
  await expect(
    page.getByText("No research plan exists for this project yet."),
  ).toBeVisible();

  await expect(page.getByText("91%", { exact: true })).toHaveCount(0);
  await expect(page.getByText("6 sections", { exact: true })).toHaveCount(0);
});

test("knowledge graph page reads real project graph state without synthetic metrics", async ({
  page,
}) => {
  await createAuthenticatedSession(page);

  await page.goto("/workspace");
  await expect(page.getByLabel("Project name")).toBeEnabled({
    timeout: 10_000,
  });

  const projectName = "E2E Knowledge " + Date.now();
  await page.getByLabel("Project name").fill(projectName);
  await page.getByRole("button", { name: "Create project" }).click();

  await expect(page.getByText(projectName, { exact: true })).toBeVisible({
    timeout: 10_000,
  });

  await page.goto("/knowledge");

  await expect(
    page.getByRole("heading", { name: "Knowledge graph", exact: true }).first().first(),
  ).toBeVisible();
  const graphEmptyState = page.getByText(
    "No knowledge graph exists for this project yet.",
  );
  const nodesMetric = page.getByText("Nodes", { exact: true });
  await expect(graphEmptyState.or(nodesMetric).first()).toBeVisible();

  await expect(page.getByText("164", { exact: true })).toHaveCount(0);
  await expect(page.getByText("482", { exact: true })).toHaveCount(0);
  await expect(page.getByText("11", { exact: true })).toHaveCount(0);
});

test("manuscript page uses real report-scoped state", async ({ page }) => {
  await createAuthenticatedSession(page);

  await page.goto("/workspace");
  await expect(page.getByLabel("Project name")).toBeEnabled({ timeout: 10_000 });

  const projectName = "E2E Manuscript " + Date.now();
  await page.getByLabel("Project name").fill(projectName);
  await page.getByRole("button", { name: "Create project" }).click();
  await expect(page.getByText(projectName, { exact: true })).toBeVisible({
    timeout: 10_000,
  });

  await page.goto("/manuscript");
  await expect(
    page.getByRole("heading", { name: "Manuscript", exact: true }).first(),
  ).toBeVisible();
  await expect(
    page.getByText("No research report exists in this project yet."),
  ).toBeVisible();
  await expect(
    page.getByText("Neural decoding in sparse fMRI", { exact: true }),
  ).toHaveCount(0);
  await expect(page.getByText("91 cited claims", { exact: false })).toHaveCount(0);
});

test("generation studio exposes real manuscript pipeline state", async ({ page }) => {
  await createAuthenticatedSession(page);

  await page.goto("/generate");
  await expect(
    page.getByRole("heading", { name: "Generate with evidence", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("No research report exists in the selected project."),
  ).toHaveCount(0);

  await expect(page.getByText("18 items", { exact: true })).toHaveCount(0);
  await expect(page.getByText("86 claims", { exact: false })).toHaveCount(0);
});

test("humanization studio is driven by manuscript state", async ({ page }) => {
  await createAuthenticatedSession(page);

  await page.goto("/humanize");
  await expect(
    page.getByRole("heading", { name: "Humanize manuscript", exact: true }).first(),
  ).toBeVisible();
  await expect(
    page.getByText("No research report exists in the selected project."),
  ).toHaveCount(0);
  await expect(page.getByText("412 words", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Claim integrity 100%", { exact: true })).toHaveCount(0);
});

test("translation studio follows the real pre-translation state machine", async ({
  page,
}) => {
  await createAuthenticatedSession(page);

  await page.goto("/translate");
  await expect(
    page.getByRole("heading", { name: "Translate research content", exact: true }).first(),
  ).toBeVisible();
  await expect(
    page.getByText("No research report exists in the selected project."),
  ).toHaveCount(0);
  await expect(page.getByText("18 / 18 citations preserved", { exact: true })).toHaveCount(0);
  await expect(page.getByText("26 / 26 key terms mapped", { exact: true })).toHaveCount(0);
});
