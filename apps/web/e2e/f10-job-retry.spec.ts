import { expect, test, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";

const password = "Secret123456789";

async function createSession(page: Page): Promise<void> {
  const email = "e2e-f10-" + randomUUID() + "@example.com";

  const register = await page.request.post("/api/v1/auth/register", {
    data: { email, password },
  });
  expect(register.status(), await register.text()).toBe(201);

  const login = await page.request.post("/api/v1/auth/login", {
    data: { email, password },
  });
  expect(login.status(), await login.text()).toBe(200);
}

test("F10 job center manually retries a cancelled durable job and reuses its identity", async ({
  page,
}) => {
  await createSession(page);

  const enqueue = await page.request.post("/api/v1/jobs", {
    data: {
      job_type: "test_noop",
      payload: { mode: "success" },
      idempotency_key: "f10-" + randomUUID(),
      max_attempts: 3,
    },
  });
  expect(enqueue.status(), await enqueue.text()).toBe(201);

  const job = (await enqueue.json()) as {
    id: string;
    attempt_count: number;
    max_attempts: number;
    status: string;
  };
  expect(job.status).toBe("queued");
  expect(job.attempt_count).toBe(0);

  const cancelled = await page.request.post(
    "/api/v1/jobs/" + job.id + "/cancel",
  );
  expect(cancelled.status(), await cancelled.text()).toBe(200);

  const jobsResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "GET" &&
      new URL(response.url()).pathname === "/api/v1/jobs",
  );
  await page.goto("/jobs");
  const listed = await jobsResponse;
  const listedText = await listed.text();
  expect(listed.status(), listedText).toBe(200);
  const listedJobs = JSON.parse(listedText) as Array<{ id: string }>;
  expect(listedJobs.some((item) => item.id === job.id)).toBe(true);

  await expect(
    page.getByRole("heading", { name: "Job center", exact: true }),
  ).toBeVisible({ timeout: 10_000 });
  const row = page.locator(`tr[data-job-id="${job.id}"]`);
  await expect(row).toHaveCount(1, { timeout: 10_000 });
  await row.getByRole("button", { name: "Retry", exact: true }).click();

  await expect(
    row.getByRole("button", { name: "Cancel", exact: true }),
  ).toBeVisible({ timeout: 10_000 });

  const retried = await page.request.get(
    "/api/v1/jobs/" + job.id,
  );
  expect(retried.status(), await retried.text()).toBe(200);
  const retriedBody = (await retried.json()) as typeof job;
  expect(retriedBody.id).toBe(job.id);
  expect(retriedBody.status).toBe("queued");
  expect(retriedBody.attempt_count).toBe(0);
  expect(retriedBody.max_attempts).toBe(job.max_attempts);

  // A client/network retry of the same action is safe while the job is queued.
  const retriedAgain = await page.request.post(
    "/api/v1/jobs/" + job.id + "/retry",
  );
  expect(retriedAgain.status(), await retriedAgain.text()).toBe(200);
  const retriedAgainBody = (await retriedAgain.json()) as typeof job;
  expect(retriedAgainBody.id).toBe(job.id);
  expect(retriedAgainBody.status).toBe("queued");
  await expect(
    page.getByRole("heading", { name: "Job center", exact: true }),
  ).toBeVisible();
  await expect(row.getByText("test_noop", { exact: true })).toBeVisible();
});

test("F10 rejects manual retry across tenant boundaries", async ({ page }) => {
  await createSession(page);
  const enqueue = await page.request.post("/api/v1/jobs", {
    data: {
      job_type: "test_noop",
      payload: { mode: "success" },
      idempotency_key: "f10-foreign-" + randomUUID(),
    },
  });
  expect(enqueue.status(), await enqueue.text()).toBe(201);
  const job = (await enqueue.json()) as { id: string };

  await page.request.post("/api/v1/auth/logout");

  await createSession(page);
  const retry = await page.request.post(
    "/api/v1/jobs/" + job.id + "/retry",
  );
  expect(retry.status(), await retry.text()).toBe(404);
});
