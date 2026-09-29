import { expect, test } from "@playwright/test";

test("frontend security headers are present", async ({ page }) => {
  const response = await page.goto("/");
  expect(response).not.toBeNull();

  const headers = response!.headers();
  expect(headers["x-content-type-options"]).toBe("nosniff");
  expect(headers["x-frame-options"]).toBe("DENY");
  expect(headers["referrer-policy"]).toBe(
    "strict-origin-when-cross-origin",
  );
  expect(headers["permissions-policy"]).toContain("camera=()");
});

test("frontend security audit route remains server-rendered without a secret-bearing response", async ({
  page,
}) => {
  const response = await page.goto("/login");
  expect(response).not.toBeNull();
  expect(response!.status()).toBe(200);

  const body = await page.locator("body").innerText();
  expect(body).not.toContain("BEGIN PRIVATE KEY");
  expect(body).not.toContain("sk-or-v1-");
  expect(body).not.toContain("whsec_");
});
