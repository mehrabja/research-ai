import { expect, test, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";

const password = "Secret123456789";

async function createSession(page: Page): Promise<string> {
  const email = "e2e-phase34-" + randomUUID() + "@example.com";

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

async function upgradeWorkspaceToPro(
  page: Page,
  workspaceId: string,
): Promise<void> {
  const response = await page.request.post(
    "/api/v1/billing/workspaces/" + workspaceId + "/plan",
    { data: { plan_code: "pro" } },
  );
  expect(response.status(), await response.text()).toBe(200);
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
  await expect(
    moveSelector.locator("option", { hasText: "review-material" }),
  ).toHaveCount(1);

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


test("F03 workspace invitations create and accept a real membership", async ({
  page,
  browser,
}) => {
  await createSession(page);
  const workspaceId = await createWorkspace(
    page,
    "F03 Invitations " + randomUUID(),
  );
  await upgradeWorkspaceToPro(page, workspaceId);

  const inviteContext = await browser.newContext();
  const invitePage = await inviteContext.newPage();
  const invitedEmail = "e2e-invited-" + randomUUID() + "@example.com";

  try {
    const register = await invitePage.request.post(
      "/api/v1/auth/register",
      { data: { email: invitedEmail, password } },
    );
    expect(register.status(), await register.text()).toBe(201);

    const invitationResponse = await page.request.post(
      "/api/v1/workspaces/" +
        workspaceId +
        "/members/invitations",
      {
        data: {
          email: invitedEmail,
          role: "member",
        },
      },
    );
    expect(
      invitationResponse.status(),
      await invitationResponse.text(),
    ).toBe(201);

    const invitation = (await invitationResponse.json()) as {
      token: string;
    };
    expect(invitation.token).toBeTruthy();

    const login = await invitePage.request.post(
      "/api/v1/auth/login",
      { data: { email: invitedEmail, password } },
    );
    expect(login.status(), await login.text()).toBe(200);

    await invitePage.goto(
      "/invite?token=" + encodeURIComponent(invitation.token),
    );
    await expect(
      invitePage.getByRole("heading", {
        name: "Join a Research AI workspace",
      }),
    ).toBeVisible({ timeout: 10_000 });

    const acceptResponse = invitePage.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        response.url().includes("/api/v1/workspaces/invitations/accept"),
    );
    await invitePage
      .getByRole("button", { name: "Accept invitation" })
      .click();
    expect((await acceptResponse).status()).toBe(200);
    await expect(invitePage).toHaveURL(/\/team$/, { timeout: 10_000 });

    const membersResponse = await page.request.get(
      "/api/v1/workspaces/" + workspaceId + "/members",
    );
    expect(membersResponse.status(), await membersResponse.text()).toBe(200);

    const members = (await membersResponse.json()) as {
      items: Array<{ email: string | null; role: string }>;
    };
    expect(
      members.items.some(
        (member) =>
          member.email === invitedEmail &&
          member.role === "member",
      ),
    ).toBe(true);
  } finally {
    await inviteContext.close();
  }
});

test("F03 workspace owners can change and remove a real member", async ({
  page,
  browser,
}) => {
  await createSession(page);
  const workspaceId = await createWorkspace(
    page,
    "F03 Member Management " + randomUUID(),
  );
  await upgradeWorkspaceToPro(page, workspaceId);

  const inviteContext = await browser.newContext();
  const invitePage = await inviteContext.newPage();
  const invitedEmail = "e2e-member-" + randomUUID() + "@example.com";

  try {
    const register = await invitePage.request.post(
      "/api/v1/auth/register",
      { data: { email: invitedEmail, password } },
    );
    expect(register.status(), await register.text()).toBe(201);

    const invitationResponse = await page.request.post(
      "/api/v1/workspaces/" + workspaceId + "/members/invitations",
      {
        data: {
          email: invitedEmail,
          role: "member",
        },
      },
    );
    expect(invitationResponse.status(), await invitationResponse.text()).toBe(201);

    const invitation = (await invitationResponse.json()) as { token: string };
    const login = await invitePage.request.post("/api/v1/auth/login", {
      data: { email: invitedEmail, password },
    });
    expect(login.status(), await login.text()).toBe(200);

    await invitePage.goto(
      "/invite?token=" + encodeURIComponent(invitation.token),
    );
    await invitePage
      .getByRole("button", { name: "Accept invitation" })
      .click();
    await expect(invitePage).toHaveURL(/\/team$/, { timeout: 10_000 });

    await page.goto("/team?workspaceId=" + workspaceId);
    await expect(
      page.getByRole("heading", {
        name: /F03 Member Management/
      }),
    ).toBeVisible({ timeout: 10_000 });

    const roleSelector = page.getByLabel("Change role for " + invitedEmail, {
      exact: true,
    });
    await expect(roleSelector).toBeVisible({ timeout: 10_000 });

    const roleResponse = page.waitForResponse(
      (response) =>
        response.request().method() === "PATCH" &&
        response.url().includes(
          "/api/v1/workspaces/" + workspaceId + "/members/",
        ),
    );
    await roleSelector.selectOption("viewer");
    expect((await roleResponse).status()).toBe(200);

    const changedMembersResponse = await page.request.get(
      "/api/v1/workspaces/" + workspaceId + "/members",
    );
    expect(
      changedMembersResponse.status(),
      await changedMembersResponse.text(),
    ).toBe(200);
    const changedMembers = (await changedMembersResponse.json()) as {
      items: Array<{ email: string | null; role: string }>;
    };
    expect(
      changedMembers.items.some(
        (member) =>
          member.email === invitedEmail &&
          member.role === "viewer",
      ),
    ).toBe(true);

    await page.getByRole("button", { name: "Remove " + invitedEmail }).click();
    await expect(
      page.getByRole("button", { name: "Confirm removal" }),
    ).toBeVisible({ timeout: 10_000 });

    const removeResponse = page.waitForResponse(
      (response) =>
        response.request().method() === "DELETE" &&
        response.url().includes(
          "/api/v1/workspaces/" + workspaceId + "/members/",
        ),
    );
    await page.getByRole("button", { name: "Confirm removal" }).click();
    expect((await removeResponse).status()).toBe(204);

    const removedMembersResponse = await page.request.get(
      "/api/v1/workspaces/" + workspaceId + "/members",
    );
    expect(
      removedMembersResponse.status(),
      await removedMembersResponse.text(),
    ).toBe(200);
    const removedMembers = (await removedMembersResponse.json()) as {
      items: Array<{ email: string | null }>;
    };
    expect(
      removedMembers.items.some((member) => member.email === invitedEmail),
    ).toBe(false);
  } finally {
    await inviteContext.close();
  }
});


test("F03 workspace owners can transfer ownership to an active member", async ({
  page,
  browser,
}) => {
  const ownerEmail = await createSession(page);
  const workspaceId = await createWorkspace(
    page,
    "F03 Ownership Transfer " + randomUUID(),
  );
  await upgradeWorkspaceToPro(page, workspaceId);

  const inviteContext = await browser.newContext();
  const invitePage = await inviteContext.newPage();
  const invitedEmail = "e2e-owner-" + randomUUID() + "@example.com";

  try {
    const register = await invitePage.request.post(
      "/api/v1/auth/register",
      { data: { email: invitedEmail, password } },
    );
    expect(register.status(), await register.text()).toBe(201);

    const invitationResponse = await page.request.post(
      "/api/v1/workspaces/" + workspaceId + "/members/invitations",
      {
        data: {
          email: invitedEmail,
          role: "member",
        },
      },
    );
    expect(invitationResponse.status(), await invitationResponse.text()).toBe(201);

    const invitation = (await invitationResponse.json()) as { token: string };
    const login = await invitePage.request.post("/api/v1/auth/login", {
      data: { email: invitedEmail, password },
    });
    expect(login.status(), await login.text()).toBe(200);

    await invitePage.goto(
      "/invite?token=" + encodeURIComponent(invitation.token),
    );
    await invitePage
      .getByRole("button", { name: "Accept invitation" })
      .click();
    await expect(invitePage).toHaveURL(/\/team$/, { timeout: 10_000 });

    const invitedUserResponse = await invitePage.request.get(
      "/api/v1/auth/me",
      { maxRetries: 3 },
    );
    expect(
      invitedUserResponse.status(),
      await invitedUserResponse.text(),
    ).toBe(200);
    const invitedUser = (await invitedUserResponse.json()) as { id: string };

    await page.goto("/team?workspaceId=" + workspaceId);
    await expect(
      page.getByLabel("New owner", { exact: true }),
    ).toBeVisible({ timeout: 10_000 });

    await page
      .getByLabel("New owner", { exact: true })
      .selectOption({ label: invitedEmail });
    await expect(
      page.getByRole("button", { name: "Confirm transfer" }),
    ).toBeVisible({ timeout: 10_000 });

    const transferResponse = page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        response.url().includes(
          "/api/v1/workspaces/" + workspaceId + "/transfer-ownership",
        ),
    );
    await page.getByRole("button", { name: "Confirm transfer" }).click();
    expect((await transferResponse).status()).toBe(200);

    await expect(page.getByLabel("New owner", { exact: true })).toHaveCount(0);

    const membersResponse = await page.request.get(
      "/api/v1/workspaces/" + workspaceId + "/members",
    );
    expect(membersResponse.status(), await membersResponse.text()).toBe(200);
    const members = (await membersResponse.json()) as {
      items: Array<{ user_id: string; email: string | null; role: string }>;
    };

    expect(
      members.items.find((member) => member.email === ownerEmail)?.role,
    ).toBe("admin");
    expect(
      members.items.find((member) => member.email === invitedEmail)?.role,
    ).toBe("owner");
    expect(
      members.items.find((member) => member.user_id === invitedUser.id)?.role,
    ).toBe("owner");
  } finally {
    await inviteContext.close();
  }
});


test("F04 dashboard renders live workspace projects and usage", async ({ page }) => {
  await createSession(page);
  const workspaceId = await createWorkspace(
    page,
    "F04 Dashboard " + randomUUID(),
  );
  const projectName = "F04 Dashboard Project " + randomUUID();
  await createProject(page, projectName);

  await page.goto("/dashboard?workspaceId=" + workspaceId);
  await expect(
    page.getByRole("heading", { name: "Research overview", exact: true }),
  ).toBeVisible({ timeout: 10_000 });
  await expect(
    page.getByRole("article").getByText(projectName, { exact: true }),
  ).toBeVisible({ timeout: 10_000 });
  await expect(
    page.getByRole("heading", { name: "Projects", exact: true }),
  ).toBeVisible({ timeout: 10_000 });
  await expect(
    page.getByText("Good morning, Alex.", { exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByText("Current workspace usage", { exact: true }),
  ).toBeVisible({ timeout: 10_000 });
});
