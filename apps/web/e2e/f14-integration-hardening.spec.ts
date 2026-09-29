import { expect, test, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";

const testPassword = "Secret123456789";

async function createAuthenticatedSession(page: Page, suffix = "default") {
  const email = "e2e-f14-" + suffix + "-" + randomUUID() + "@example.com";

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
}

test("BFF refreshes an expired access token from the refresh session", async ({
  page,
}) => {
  await createAuthenticatedSession(page);

  const meResponse = await page.request.get("/api/v1/auth/me");
  expect(meResponse.status(), await meResponse.text()).toBe(200);

  const cookies = await page.context().cookies();
  const accessCookie = cookies.find(
    (cookie) => cookie.name === "research_ai_access",
  );
  const refreshCookie = cookies.find(
    (cookie) => cookie.name === "research_ai_refresh",
  );
  expect(accessCookie).toBeTruthy();
  expect(refreshCookie).toBeTruthy();

  const tamperedAccess = accessCookie?.value
    ? accessCookie.value.replace(/.$/, "x")
    : "invalid";
  await page.context().addCookies([
    {
      ...(accessCookie as NonNullable<typeof accessCookie>),
      value: tamperedAccess,
    },
  ]);

  const refreshedResponse = await page.request.get("/api/v1/auth/me");
  expect(
    refreshedResponse.status(),
    await refreshedResponse.text(),
  ).toBe(200);

  const updatedCookies = await page.context().cookies();
  const updatedAccessCookie = updatedCookies.find(
    (cookie) => cookie.name === "research_ai_access",
  );
  expect(updatedAccessCookie?.value).not.toBe(tamperedAccess);
});

test("provider matrix exposes the backend capability registry", async ({
  page,
}) => {
  await createAuthenticatedSession(page);

  const response = await page.request.get("/api/v1/providers/matrix");
  expect(response.status(), await response.text()).toBe(200);

  const payload = (await response.json()) as {
    capabilities: Array<{
      capability: string;
      configured_preferred: string | null;
      available_providers: string[];
    }>;
  };

  expect(payload.capabilities.length).toBeGreaterThan(0);

  for (const item of payload.capabilities) {
    expect(item.capability).toBeTruthy();
    expect(item.available_providers).toEqual(
      expect.any(Array),
    );
  }
});

test("workspace-scoped API data does not cross tenant boundaries", async ({
  page,
}) => {
  await createAuthenticatedSession(page, "f14-a");

  const workspaceResponse = await page.request.post(
    "/api/v1/workspaces",
    {
      headers: {
        Origin: "http://localhost:3000",
      },
      data: {
        name: "F14 Workspace A " + randomUUID(),
      },
    },
  );
  expect(
    workspaceResponse.status(),
    await workspaceResponse.text(),
  ).toBe(201);
  const workspace = (await workspaceResponse.json()) as {
    id: string;
  };

  const logoutResponse = await page.request.post("/api/v1/auth/logout", {
    headers: {
      Origin: "http://localhost:3000",
    },
  });
  expect(logoutResponse.status(), await logoutResponse.text()).toBe(200);

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
    page.getByRole("heading", { name: "Job center", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Server-side processing"),
  ).toBeVisible({ timeout: 15_000 });
  await expect(
    page.getByText("Next in ~2 min"),
  ).toHaveCount(0);
});
