import { expect, test, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";

const password = "Secret123456789";

async function createSession(page: Page): Promise<void> {
  const email = "e2e-phase34-" + randomUUID() + "@example.com";

  const register = await page.request.post("/api/v1/auth/register", {
    data: { email, password },
  });
  expect(register.status(), await register.text()).toBe(201);

  const login = await page.request.post("/api/v1/auth/login", {
    data: { email, password },
  });
  expect(login.status(), await login.text()).toBe(200);
}

async function createWorkspace(page: Page, name: string): Promise<string> {
  const response = await page.request.post("/api/v1/workspaces", {
    headers: { Origin: "http://localhost:3000" },
    data: { name },
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

test("F03 notification preferences persist through the authenticated UI", async ({
  page,
}) => {
  await createSession(page);
  await page.goto("/settings");

  const invitationPreference = page.getByLabel("Workspace invitations", {
    exact: true,
  });
  await expect(invitationPreference).toBeVisible({ timeout: 10_000 });
  await expect(invitationPreference).toBeEnabled({ timeout: 10_000 });
  await expect(invitationPreference).toBeChecked();

  const savedNotice = page.getByText("Notification preferences saved.", {
    exact: true,
  });
  const disableResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "PATCH" &&
      response.url().includes("/api/v1/notifications/preferences"),
  );
  await invitationPreference.uncheck();
  expect((await disableResponse).status()).toBe(200);
  await expect(savedNotice).toBeVisible({ timeout: 10_000 });

  const disabled = await page.request.get(
    "/api/v1/notifications/preferences",
  );
  expect(disabled.status(), await disabled.text()).toBe(200);
  const disabledPayload = (await disabled.json()) as {
    preferences: Record<string, boolean>;
  };
  expect(disabledPayload.preferences.member_invited).toBe(false);

  const enableResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "PATCH" &&
      response.url().includes("/api/v1/notifications/preferences"),
  );
  await invitationPreference.check();
  expect((await enableResponse).status()).toBe(200);
  await expect(savedNotice).toBeVisible({ timeout: 10_000 });

  const enabled = await page.request.get(
    "/api/v1/notifications/preferences",
  );
  expect(enabled.status(), await enabled.text()).toBe(200);
  const enabledPayload = (await enabled.json()) as {
    preferences: Record<string, boolean>;
  };
  expect(enabledPayload.preferences.member_invited).toBe(true);
});

test("F03 workspace lifecycle controls use the owner-only backend contract", async ({
  page,
}) => {
  await createSession(page);
  const workspaceId = await createWorkspace(
    page,
    "F03 Lifecycle " + randomUUID(),
  );

  await page.goto("/workspace?workspaceId=" + workspaceId);
  await expect(
    page.getByRole("heading", { name: "Workspace lifecycle" }),
  ).toBeVisible({ timeout: 10_000 });
  await expect(
    page.getByRole("button", { name: "Suspend workspace" }),
  ).toBeVisible({ timeout: 10_000 });

  await page.getByRole("button", { name: "Suspend workspace" }).click();
  await expect(page.getByText("suspended", { exact: true })).toBeVisible({
    timeout: 10_000,
  });
  await expect(
    page.getByRole("button", { name: "Reactivate workspace" }),
  ).toBeVisible({ timeout: 10_000 });

  await page
    .getByRole("button", { name: "Reactivate workspace" })
    .click();
  await expect(page.getByText("active", { exact: true })).toBeVisible({
    timeout: 10_000,
  });

  const response = await page.request.get(
    "/api/v1/workspaces/" + workspaceId,
  );
  expect(response.status(), await response.text()).toBe(200);
  expect((await response.json()).status).toBe("active");
});

test("F04 Files UI moves an uploaded project file between persistent folders", async ({
  page,
}) => {
  await createSession(page);
  const projectName = "F04 File Move " + randomUUID();
  const projectId = await createProject(page, projectName);

  const upload = await page.request.post(
    "/api/v1/projects/" + projectId + "/files",
    {
      multipart: {
        file: {
          name: "phase4-move.txt",
          mimeType: "text/plain",
          buffer: Buffer.from("Phase 4 file movement acceptance."),
        },
      },
    },
  );
  expect(upload.status(), await upload.text()).toBe(201);
  const file = (await upload.json()) as { id: string };

  const folder = await page.request.post(
    "/api/v1/projects/" + projectId + "/folders",
    {
      data: { name: "review-material" },
    },
  );
  expect(folder.status(), await folder.text()).toBe(201);
  const folderId = (await folder.json()).id as string;

  await page.goto("/files");
  const projectSelect = page.locator("#files-project");
  await expect(projectSelect).toBeEnabled({ timeout: 10_000 });
  await projectSelect.selectOption({ label: projectName });
  await expect(
    page.getByRole("heading", { name: "Files & intelligence", exact: true }).first(),
  ).toBeVisible({ timeout: 10_000 });
  await expect(
    page.getByText("phase4-move.txt", { exact: true }),
  ).toBeVisible({ timeout: 10_000 });

  const moveSelector = page.getByLabel("Move phase4-move.txt", {
    exact: true,
  });
  await expect(moveSelector).toBeVisible({ timeout: 10_000 });
  await expect(moveSelector.locator("option", { hasText: "review-material" })).toHaveCount(1);

  const moveResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "PATCH" &&
      response.url().includes("/api/v1/files/" + file.id),
  );
  await moveSelector.selectOption({ label: "review-material" });
  expect((await moveResponse).status()).toBe(200);

  const moved = await page.request.get(
    "/api/v1/projects/" +
      projectId +
      "/files?folder_id=" +
      encodeURIComponent(folderId),
  );
  expect(moved.status(), await moved.text()).toBe(200);
  const movedPayload = (await moved.json()) as {
    items: Array<{ id: string }>;
  };
  expect(movedPayload.items.some((item) => item.id === file.id)).toBe(true);
});
