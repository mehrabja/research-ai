import { expect, test, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";

const password = "Secret123456789";

async function createSession(page: Page): Promise<void> {
  const email = "e2e-phase56-" + randomUUID() + "@example.com";
  const register = await page.request.post("/api/v1/auth/register", {
    data: { email, password },
  });
  expect(register.status(), await register.text()).toBe(201);

  const login = await page.request.post("/api/v1/auth/login", {
    data: { email, password },
  });
  expect(login.status(), await login.text()).toBe(200);
}

test("F05 global search returns a real workspace project", async ({ page }) => {
  await createSession(page);

  const workspace = await page.request.post("/api/v1/workspaces", {
    headers: { Origin: "http://localhost:3000" },
    data: { name: "F05 Search " + randomUUID() },
  });
  expect(workspace.status(), await workspace.text()).toBe(201);
  const workspaceId = (await workspace.json()).id as string;

  const projectName = "F05 Search Project " + randomUUID();
  const project = await page.request.post(
    "/api/v1/projects?workspace_id=" + encodeURIComponent(workspaceId),
    { data: { name: projectName } },
  );
  expect(project.status(), await project.text()).toBe(201);

  const direct = await page.request.get(
    "/api/v1/search?q=" +
      encodeURIComponent(projectName) +
      "&workspace_id=" +
      encodeURIComponent(workspaceId) +
      "&limit=10",
  );
  expect(direct.status(), await direct.text()).toBe(200);
  const directPayload = (await direct.json()) as {
    items: Array<{
      id: string;
      resource_type: string;
      project_id: string | null;
    }>;
  };
  expect(
    directPayload.items.some(
      (item) =>
        item.resource_type === "project" &&
        item.project_id === item.id,
    ),
  ).toBe(true);

  await page.goto("/search?workspaceId=" + workspaceId);
  await expect(
    page.getByRole("heading", { name: "Global search", exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("Workspace search query", { exact: true })
    .fill(projectName);
  await page.getByRole("button", { name: "Search", exact: true }).click();

  await expect(page.getByText(projectName, { exact: true })).toBeVisible({
    timeout: 10_000,
  });
  await expect(page.getByText("Live API", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: projectName }).click();
  await expect(
    page.getByRole("heading", {
      name: "Projects and research context",
      exact: true,
    }),
  ).toBeVisible({ timeout: 10_000 });
});

test("F06 knowledge graph node browser and export use persisted graph contracts", async ({
  page,
}) => {
  await createSession(page);

  const workspace = await page.request.post("/api/v1/workspaces", {
    headers: { Origin: "http://localhost:3000" },
    data: { name: "F06 Graph " + randomUUID() },
  });
  expect(workspace.status(), await workspace.text()).toBe(201);
  const workspaceId = (await workspace.json()).id as string;

  const project = await page.request.post(
    "/api/v1/projects?workspace_id=" + encodeURIComponent(workspaceId),
    { data: { name: "F06 Graph Project " + randomUUID() } },
  );
  expect(project.status(), await project.text()).toBe(201);
  const projectId = (await project.json()).id as string;

  const generated = await page.request.post(
    "/api/v1/projects/" + projectId + "/knowledge-graph/generate",
    { data: { async: false } },
  );
  expect(generated.status(), await generated.text()).toBe(200);

  const nodes = await page.request.get(
    "/api/v1/projects/" + projectId + "/knowledge-graph/nodes?limit=100",
  );
  expect(nodes.status(), await nodes.text()).toBe(200);
  expect(Array.isArray(await nodes.json())).toBe(true);

  const exported = await page.request.get(
    "/api/v1/projects/" + projectId + "/knowledge-graph/export",
  );
  expect(exported.status(), await exported.text()).toBe(200);

  await page.goto("/knowledge?workspaceId=" + workspaceId + "&projectId=" + projectId);
  await expect(
    page.getByRole("heading", { name: "Knowledge graph", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Nodes", { exact: true })).toBeVisible();
  await expect(
    page.getByLabel("Knowledge graph node filter", { exact: true }),
  ).toBeVisible();
});
