import { expect, test, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";

const testPassword = "Secret123456789";

async function createAuthenticatedSession(page: Page, prefix = "f14") {
  const email =
    "e2e-" + prefix + "-" + randomUUID() + "@example.com";

  const registerResponse = await page.request.post(
    "/api/v1/auth/register",
    { data: { email, password: testPassword } },
  );
  expect(
    registerResponse.status(),
    await registerResponse.text(),
  ).toBe(201);

  const loginResponse = await page.request.post(
    "/api/v1/auth/login",
    { data: { email, password: testPassword } },
  );
  expect(
    loginResponse.status(),
    await loginResponse.text(),
  ).toBe(200);

  return email;
}

test("BFF refreshes an expired access token without losing the session", async ({
  page,
}) => {
  await createAuthenticatedSession(page);

  const before = await page.context().cookies();
  const refreshCookie = before.find(
    (cookie) => cookie.name === "research_ai_refresh",
  );
  const accessCookie = before.find(
    (cookie) => cookie.name === "research_ai_access",
  );

  expect(refreshCookie).toBeDefined();
  expect(accessCookie).toBeDefined();

  await page.context().addCookies([
    {
      name: "research_ai_access",
      value: "expired-access-token",
      url: "http://localhost:3000/",
      httpOnly: true,
      sameSite: "Lax",
    },
  ]);

  const response = await page.request.get("/api/v1/auth/me");
  expect(response.status(), await response.text()).toBe(200);

  const me = (await response.json()) as { id?: unknown };
  expect(typeof me.id).toBe("string");

  const after = await page.context().cookies();
  const refreshedAccess = after.find(
    (cookie) => cookie.name === "research_ai_access",
  );
  expect(refreshedAccess).toBeDefined();
  expect(refreshedAccess?.value).not.toBe(
    "expired-access-token",
  );
});

test("provider matrix is available through the authenticated BFF", async ({
  page,
}) => {
  await createAuthenticatedSession(page);

  const response = await page.request.get("/api/v1/providers/matrix");
  expect(response.status(), await response.text()).toBe(200);

  const body = (await response.json()) as {
    capabilities: Array<{
      capability: string;
      configured_preferred: string;
      available_providers: string[];
    }>;
  };

  const capabilities = new Map(
    body.capabilities.map((item) => [
      item.capability,
      item,
    ]),
  );

  for (const capability of [
    "generation",
    "embedding",
    "translation",
    "detection",
    "source_discovery",
    "billing",
    "email",
    "storage",
  ]) {
    expect(
      capabilities.has(capability),
      "missing capability: " + capability,
    ).toBe(true);
  }
});

test("workspace-scoped APIs do not cross tenant boundaries", async ({
  page,
}) => {
  await createAuthenticatedSession(page, "f14-a");

  const createWorkspaceResponse =
    await page.request.post("/api/v1/workspaces", {
      headers: {
        Origin: "http://localhost:3000",
      },
      data: {
        name: "F14 isolation " + randomUUID(),
      },
    });
  expect(
    createWorkspaceResponse.status(),
    await createWorkspaceResponse.text(),
  ).toBe(201);

  const workspace = (await createWorkspaceResponse.json()) as {
    id: string;
  };

  const logoutResponse = await page.request.post(
    "/api/v1/auth/logout",
    {
      headers: {
        Origin: "http://localhost:3000",
      },
    },
  );
  expect(logoutResponse.status(), await logoutResponse.text()).toBe(
    200,
  );

  await createAuthenticatedSession(page, "f14-b");

  for (const suffix of ["", "/usage", "/plan", "/subscription"]) {
    const response = await page.request.get(
      "/api/v1/workspaces/" + workspace.id + suffix,
    );

    expect(
      response.status(),
      "foreign workspace " + suffix,
    ).toBe(404);
  }
});

test("job center uses durable jobs instead of static demo metrics", async ({
  page,
}) => {
  await createAuthenticatedSession(page);

  const response = await page.request.get("/api/v1/jobs?limit=100");
  expect(response.status(), await response.text()).toBe(200);

  const jobs = (await response.json()) as Array<{
    id: string;
    status: string;
    attempt_count: number;
    max_attempts: number;
  }>;

  for (const job of jobs) {
    expect(job.id).toMatch(/^[0-9a-f-]{36}$/i);
    expect(job.attempt_count).toBeGreaterThanOrEqual(0);
    expect(job.max_attempts).toBeGreaterThanOrEqual(1);
  }

  await page.goto("/jobs");
  await expect(
    page.getByRole("heading", { name: "Job center" }),
  ).toBeVisible();
  await expect(
    page.getByText("Server-side processing"),
  ).toBeVisible();
  await expect(
    page.getByText("Next in ~2 min"),
  ).toHaveCount(0);
});
