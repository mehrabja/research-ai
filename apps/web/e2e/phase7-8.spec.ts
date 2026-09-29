import { expect, test, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";

const password = "Secret123456789";

async function createSession(page: Page) {
  const email = "e2e-phase78-" + randomUUID() + "@example.com";

  const register = await page.request.post("/api/v1/auth/register", {
    data: { email, password },
  });
  expect(register.status(), await register.text()).toBe(201);

  const login = await page.request.post("/api/v1/auth/login", {
    data: { email, password },
  });
  expect(login.status(), await login.text()).toBe(200);

  const workspace = await page.request.post("/api/v1/workspaces", {
    headers: { Origin: "http://localhost:3000" },
    data: { name: "F07/F08 E2E Workspace " + randomUUID() },
  });
  expect(workspace.status(), await workspace.text()).toBe(201);

  const workspaceId = (await workspace.json()).id as string;
  return workspaceId;
}

async function createProject(
  page: Page,
  workspaceId: string,
  name: string,
): Promise<string> {
  const project = await page.request.post(
    "/api/v1/projects?workspace_id=" +
      encodeURIComponent(workspaceId),
    { data: { name } },
  );
  expect(project.status(), await project.text()).toBe(201);
  return (await project.json()).id as string;
}

test("F07 plan revision history saves an immutable revision and restores a prior version", async ({
  page,
}) => {
  const workspaceId = await createSession(page);
  const projectId = await createProject(
    page,
    workspaceId,
    "F07 Plan Project " + randomUUID(),
  );

  const generated = await page.request.post(
    "/api/v1/projects/" + projectId + "/research-plan/generate",
    { data: { async: false } },
  );
  expect(generated.status(), await generated.text()).toBe(200);
  const originalPlan = (await generated.json()).plan as {
    version: number;
    research_objective_snapshot: string | null;
  };

  await page.goto(
    "/plan?workspaceId=" +
      encodeURIComponent(workspaceId) +
      "&projectId=" +
      encodeURIComponent(projectId),
    { waitUntil: "domcontentloaded" },
  );

  await expect(
    page.getByRole("heading", { name: "Research plan", exact: true, level: 1 }),
  ).toBeVisible();
  const objective = page.getByLabel("Research objective", { exact: true });
  await expect(objective).toBeVisible();
  await expect(objective).toHaveValue(
    originalPlan.research_objective_snapshot ?? "",
  );

  await objective.fill("F07 revised objective " + randomUUID());
  await page.getByRole("button", { name: "Save revision", exact: true }).click();

  const revised = page
    .locator(".list-item")
    .filter({ hasText: "Version " + (originalPlan.version + 1) })
    .first();
  await expect(revised).toBeVisible({ timeout: 10_000 });

  const original = page
    .locator(".list-item")
    .filter({ hasText: "Version " + originalPlan.version })
    .first();
  await expect(original).toBeVisible({ timeout: 10_000 });
  await original
    .getByRole("button", { name: "Restore this version", exact: true })
    .click();

  const restoredVersion = originalPlan.version + 2;
  await expect(
    page
      .locator(".list-item")
      .filter({ hasText: "Version " + restoredVersion })
      .first(),
  ).toBeVisible({ timeout: 10_000 });

  await expect(
    page.getByLabel("Research objective", { exact: true }),
  ).toHaveValue(originalPlan.research_objective_snapshot ?? "");

  const currentVersion = page
    .locator(".list-item")
    .filter({ hasText: "Version " + restoredVersion })
    .first();
  await expect(currentVersion.getByText("Current", { exact: true })).toBeVisible();
});

test("F08 manuscript editor autosaves a draft, exposes revision state, and commits an immutable version", async ({
  page,
}) => {
  const workspaceId = await createSession(page);
  const projectId = await createProject(
    page,
    workspaceId,
    "F08 Manuscript Project " + randomUUID(),
  );

  const report = await page.request.post(
    "/api/v1/reports?workspace_id=" +
      encodeURIComponent(workspaceId),
    {
      data: {
        project_id: projectId,
        topic: "F08 autosave manuscript " + randomUUID(),
        output_language: "en",
      },
    },
  );
  expect(report.status(), await report.text()).toBe(201);
  const reportId = (await report.json()).id as string;

  const plan = await page.request.post(
    "/api/v1/projects/" + projectId + "/research-plan/generate",
    { data: { async: false } },
  );
  expect(plan.status(), await plan.text()).toBe(200);

  const manuscript = await page.request.post(
    "/api/v1/reports/" + reportId + "/manuscript/generate",
    { data: { async: false } },
  );
  expect(manuscript.status(), await manuscript.text()).toBe(200);
  const generatedManuscript = await manuscript.json() as {
    version_id: string | null;
  };

  await page.goto(
    "/manuscript?workspaceId=" +
      encodeURIComponent(workspaceId) +
      "&projectId=" +
      encodeURIComponent(projectId) +
      "&reportId=" +
      encodeURIComponent(reportId),
    { waitUntil: "domcontentloaded" },
  );

  await expect(
    page.getByRole("heading", { name: "Manuscript", exact: true, level: 1 }),
  ).toBeVisible();

  const draftTitle = page.getByLabel("Draft title", { exact: true });
  await expect(draftTitle).toBeVisible({ timeout: 10_000 });

  const changedTitle = "Autosaved title " + randomUUID();
  await draftTitle.fill(changedTitle);

  await expect(
    page.getByText(/Draft autosaved|Draft autosaved · revision \d+/, {
      exact: false,
    }),
  ).toBeVisible({ timeout: 10_000 });

  await expect(
    page.getByText(/Draft revision/, { exact: false }).first(),
  ).toBeVisible();

  await page
    .getByRole("button", { name: "Commit as version", exact: true })
    .click();

  expect(generatedManuscript.version_id).toBeTruthy();
  const nextVersion = 2;
  await expect(
    page.getByText(
      "Draft committed as manuscript version " + nextVersion + ".",
      { exact: true },
    ),
  ).toBeVisible({ timeout: 10_000 });

  await expect(
    page
      .locator(".list-item")
      .filter({ hasText: "v" + nextVersion + " · " + changedTitle })
      .first(),
  ).toBeVisible({ timeout: 10_000 });

  const persistedDraft = await page.request.get(
    "/api/v1/reports/" + reportId + "/manuscript/draft",
  );
  expect(persistedDraft.status(), await persistedDraft.text()).toBe(404);
});
