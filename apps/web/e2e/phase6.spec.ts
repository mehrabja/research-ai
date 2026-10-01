import { expect, test, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";

const password = "Secret123456789";

async function createSession(page: Page): Promise<{
  workspaceId: string;
  projectId: string;
  reportId: string;
}> {
  const email = "e2e-phase6-" + randomUUID() + "@example.com";

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
    data: { name: "F06 Evidence " + randomUUID() },
  });
  expect(workspace.status(), await workspace.text()).toBe(201);
  const workspaceId = (await workspace.json()).id as string;

  const project = await page.request.post(
    "/api/v1/projects?workspace_id=" + encodeURIComponent(workspaceId),
    { data: { name: "F06 Evidence Project " + randomUUID() } },
  );
  expect(project.status(), await project.text()).toBe(201);
  const projectId = (await project.json()).id as string;

  const report = await page.request.post(
    "/api/v1/reports?workspace_id=" + encodeURIComponent(workspaceId),
    {
      data: {
        project_id: projectId,
        topic: "F06 evidence matrix " + randomUUID(),
        output_language: "en",
      },
    },
  );
  expect(report.status(), await report.text()).toBe(201);

  return {
    workspaceId,
    projectId,
    reportId: (await report.json()).id as string,
  };
}

test("F06 evidence matrix treats a missing citation run as an empty state", async ({
  page,
}) => {
  const { workspaceId, projectId, reportId } = await createSession(page);

  const direct = await page.request.get(
    "/api/v1/reports/" + reportId + "/evidence/matrix",
  );
  expect(direct.status(), await direct.text()).toBe(404);

  await page.goto(
    "/evidence?workspaceId=" +
      encodeURIComponent(workspaceId) +
      "&projectId=" +
      encodeURIComponent(projectId) +
      "&reportId=" +
      encodeURIComponent(reportId),
    { waitUntil: "domcontentloaded" },
  );

  await expect(page.locator("#evidence-workspace")).toHaveValue(workspaceId);
  await expect(page.locator("#evidence-project")).toHaveValue(projectId);
  await expect(page.locator("#evidence-report")).toHaveValue(reportId);

  await expect(
    page.getByRole("heading", { name: "Evidence", exact: true, level: 1 }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Evidence matrix", exact: true, level: 2 }),
  ).toBeVisible();
  await expect(
    page.getByText("No citation run is available yet.", { exact: false }),
  ).toBeVisible({ timeout: 10_000 });
  await expect(
    page.getByText("Evidence unavailable", { exact: true }),
  ).toHaveCount(0);
});
