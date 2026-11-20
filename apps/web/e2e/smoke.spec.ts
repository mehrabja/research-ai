import { expect, test, type Page } from "@playwright/test";

const testPassword = "Secret123456789";

async function createAuthenticatedSession(page: Page) {
  const email = `e2e-shell-${Date.now()}@gmail.com`;

  const registerResponse = await page.request.post(
    "/api/v1/auth/register",
    {
      data: {
        email,
        password: testPassword,
      },
    },
  );

  const registerBody = await registerResponse.text();

  expect(registerResponse.status(), registerBody).toBe(201);

  const loginResponse = await page.request.post(
    "/api/v1/auth/login",
    {
      data: {
        email,
        password: testPassword,
      },
    },
  );

  const loginBody = await loginResponse.text();

  expect(loginResponse.status(), loginBody).toBe(200);

  const meResponse = await page.request.get(
    "/api/v1/auth/me",
  );

  const meBody = await meResponse.text();

  expect(meResponse.status(), meBody).toBe(200);

  return email;
}

test("landing page opens", async ({ page }) => {
  await page.goto("/");

  await expect(page).toHaveTitle(/Research AI/i);
  await expect(
    page.getByRole("link", { name: "Create free workspace →" }),
  ).toBeVisible();
});

test("login validates required fields", async ({ page }) => {
  await page.goto("/login");

  const email = page.getByLabel(/email/i);
  const password = page.getByLabel(/password/i);
  const submit = page.getByRole("button", { name: /^log in$/i });

  await submit.click();

  await expect(email).toHaveAttribute("aria-invalid", "true");
  await expect(password).toHaveAttribute("aria-invalid", "true");
});

test("signup creates account and workspace", async ({ page }) => {
  const email = `e2e-${Date.now()}@gmail.com`;
  const apiFailures: string[] = [];

  page.on("response", async (response) => {
    const url = response.url();

    if (
      url.includes("/api/v1/auth/") ||
      url.includes("/api/v1/workspaces")
    ) {
      if (response.status() >= 400) {
        let body = "";

        try {
          body = await response.text();
        } catch {
          body = "<unable to read response body>";
        }

        apiFailures.push(
          `${response.request().method()} ${url} -> ${response.status()} ${body}`,
        );
      }
    }
  });

  await page.goto("/signup");

  await page.getByLabel(/first name/i).fill("E2E");
  await page.getByLabel(/last name/i).fill("Test");
  await page.getByLabel(/work email/i).fill(email);
  await page.getByLabel(/^password$/i).fill(testPassword);
  await page.getByLabel(/workspace name/i).fill("E2E Workspace");
  await page.getByRole("checkbox").check();

  await page.getByRole("button", { name: /create workspace/i }).click();

  try {
    await expect(page).toHaveURL(/\/dashboard$/, {
      timeout: 10_000,
    });
  } catch (error) {
    if (apiFailures.length > 0) {
      throw new Error(
        `Signup API failure:\n${apiFailures.join("\n")}`,
      );
    }

    throw new Error(
      `Signup did not reach dashboard.\nOriginal error: ${String(error)}`,
    );
  }
});

test("protected routes redirect unauthenticated users to login", async ({
  page,
}) => {
  await page.context().clearCookies();

  await page.goto("/dashboard");

  await expect(page).toHaveURL(/\/login$/);
});

test("authenticated app shell exposes main navigation and a working CSP nonce", async ({
  page,
}) => {
  await createAuthenticatedSession(page);

  const response = await page.goto("/dashboard");
  expect(response).not.toBeNull();
  expect(response?.status()).toBe(200);

  const csp = response?.headers()["content-security-policy"] ?? "";
  const nonce = csp.match(/'nonce-([^']+)'/)?.[1];
  expect(nonce).toBeTruthy();

  const executableScriptNonces = await page.locator("script").evaluateAll((scripts) =>
    scripts
      .filter((script) => {
        const type = (script.getAttribute("type") ?? "").trim().toLowerCase();
        return (
          type === "" ||
          type === "text/javascript" ||
          type === "application/javascript" ||
          type === "module"
        );
      })
      .map((script) => (script as HTMLScriptElement).nonce),
  );
  expect(executableScriptNonces.length).toBeGreaterThan(0);
  expect(executableScriptNonces.every(Boolean)).toBe(true);
  expect(new Set(executableScriptNonces)).toEqual(new Set([nonce]));

  await expect(
    page.locator('a[href="/dashboard"]').first(),
  ).toBeVisible();

  await expect(
    page.locator('a[href="/research"]').first(),
  ).toBeVisible();

  await expect(
    page.locator('a[href="/sources"]').first(),
  ).toBeVisible();
});

test("BFF rejects cross-origin state-changing requests", async ({
  page,
}) => {
  await createAuthenticatedSession(page);

  const response = await page.request.post(
    "/api/v1/workspaces",
    {
      headers: {
        Origin: "https://evil.example",
      },
      data: {
        name: `CSRF Test ${Date.now()}`,
      },
    },
  );

  expect(response.status()).toBe(403);

  const body = await response.json();

  expect(body).toMatchObject({
    error: "CSRF validation failed",
  });
});

test("logout invalidates the browser session", async ({
  page,
}) => {
  await createAuthenticatedSession(page);

  const authenticatedResponse =
    await page.request.get("/api/v1/auth/me");

  expect(authenticatedResponse.status()).toBe(200);

  const logoutResponse = await page.request.post(
    "/api/v1/auth/logout",
    {
      headers: {
        Origin: "http://localhost:3000",
      },
      data: {},
    },
  );

  expect(logoutResponse.status()).toBe(200);

  const meAfterLogout =
    await page.request.get("/api/v1/auth/me");

  expect(meAfterLogout.status()).toBe(401);

  await page.goto("/dashboard");

  await expect(page).toHaveURL(/\/login$/);
});