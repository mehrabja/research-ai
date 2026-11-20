import { expect, test, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";

const password = "Secret123456789";

async function createSession(page: Page): Promise<string> {
  const email = "e2e-phase5-" + randomUUID() + "@example.com";
  const register = await page.request.post("/api/v1/auth/register", {
    data: { email, password },
  });
  expect(register.status(), await register.text()).toBe(201);

  const login = await page.request.post("/api/v1/auth/login", {
    data: { email, password },
  });
  expect(login.status(), await login.text()).toBe(200);
  return email;
}

async function createWorkspace(page: Page): Promise<string> {
  const response = await page.request.post("/api/v1/workspaces", {
    headers: { Origin: "http://localhost:3000" },
    data: { name: "F05 Workspace " + randomUUID() },
  });
  expect(response.status(), await response.text()).toBe(201);
  return (await response.json()).id as string;
}

async function createProject(page: Page, name: string): Promise<string> {
  const response = await page.request.post("/api/v1/projects", {
    data: { name },
  });
  expect(response.status(), await response.text()).toBe(201);
  return (await response.json()).id as string;
}

async function createReport(
  page: Page,
  projectId: string,
  topic: string,
): Promise<string> {
  const response = await page.request.post("/api/v1/reports", {
    data: {
      topic,
      output_language: "en",
      domain: "academic research",
      project_id: projectId,
      tone: "academic",
      length: "medium",
      audience_level: "researcher",
    },
  });
  expect(response.status(), await response.text()).toBe(201);
  return (await response.json()).id as string;
}

test("F05 Sources lists real saved sources and exposes source details", async ({ page }) => {
  await createSession(page);
  const workspaceId = await createWorkspace(page);
  const projectName = "F05 Sources Project " + randomUUID();
  const projectId = await createProject(page, projectName);
  const reportId = await createReport(page, projectId, "F05 Source detail acceptance");
  const sourceTitle = "F05 Real Source " + randomUUID();

  const sourceResponse = await page.request.post(
    "/api/v1/reports/" + reportId + "/sources",
    {
      data: {
        source_api: "e2e",
        external_source_id: randomUUID(),
        title: sourceTitle,
        authors: ["Research AI Test"],
        year: 2026,
        doi: "10.1234/" + randomUUID(),
        url: "https://example.com/research-ai-test",
        abstract: "Persistent source detail acceptance fixture.",
        citation_count: 7,
        source_meta: { fixture: true },
      },
    },
  );
  expect(sourceResponse.status(), await sourceResponse.text()).toBe(201);

  await page.goto(
    "/sources?workspaceId=" +
      workspaceId +
      "&projectId=" +
      projectId +
      "&reportId=" +
      reportId,
  );

  await expect(page.getByText(sourceTitle, { exact: true })).toBeVisible({
    timeout: 10_000,
  });
  await page.getByRole("button", { name: "Details", exact: true }).click();
  await expect(page.getByText("Authors:", { exact: false })).toBeVisible();
  await expect(
    page
      .locator("p.muted.small")
      .filter({ hasText: "Persistent source detail acceptance fixture." }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Open source", exact: true })).toHaveAttribute(
    "href",
    "https://example.com/research-ai-test",
  );
});

test("F05 Files uploads, renames folders, inspects metadata and deletes a real file", async ({ page }) => {
  await createSession(page);
  const workspaceId = await createWorkspace(page);
  const projectName = "F05 Files Project " + randomUUID();
  const projectId = await createProject(page, projectName);
  const folderName = "review-" + randomUUID().slice(0, 8);
  const renamedFolder = "final-" + randomUUID().slice(0, 8);
  const filename = "phase5-" + randomUUID() + ".txt";

  await page.goto(
    "/files?workspaceId=" + workspaceId + "&projectId=" + projectId,
  );

  await page.getByLabel("New folder name", { exact: true }).fill(folderName);
  await page.getByRole("button", { name: "Create folder", exact: true }).click();
  const folderSelect = page.getByLabel("Folder", { exact: true });
  await expect(
    folderSelect.locator("option", { hasText: folderName }),
  ).toHaveCount(1, { timeout: 10_000 });
  await folderSelect.selectOption({ label: folderName });

  await page.getByLabel("Rename folder", { exact: true }).selectOption({
    label: folderName,
  });
  await page.getByLabel("Renamed folder name", { exact: true }).fill(renamedFolder);
  await page.getByRole("button", { name: "Rename", exact: true }).click();
  await expect(
    page
      .getByLabel("Rename folder", { exact: true })
      .locator("option", { hasText: renamedFolder }),
  ).toHaveCount(1, { timeout: 10_000 });

  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles({
    name: filename,
    mimeType: "text/plain",
    buffer: Buffer.from("Phase 5 file intelligence acceptance content."),
  });

  await expect(page.getByText(filename, { exact: true })).toBeVisible({
    timeout: 10_000,
  });
  await page.getByRole("button", { name: "Inspect " + filename, exact: true }).click();
  await expect(
    page.getByRole("region", { name: "Intelligence for " + filename }),
  ).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText("Selected file", { exact: true })).toBeVisible();
  await expect(
    page.locator("p.muted.small").filter({ hasText: "text/plain" }),
  ).toHaveCount(1);

  await page.getByRole("button", { name: "Delete", exact: true }).click();
  await expect(page.getByText(filename, { exact: true })).toHaveCount(0, {
    timeout: 10_000,
  });
});
