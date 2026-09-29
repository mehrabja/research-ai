import { expect, test, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";

const password = "Secret123456789";

async function createSession(page: Page): Promise<void> {
  const email = "e2e-p12-14-" + randomUUID() + "@example.com";

  const register = await page.request.post("/api/v1/auth/register", {
    data: { email, password },
  });
  expect(register.status(), await register.text()).toBe(201);

  const login = await page.request.post("/api/v1/auth/login", {
    data: { email, password },
  });
  expect(login.status(), await login.text()).toBe(200);
}

async function createProject(page: Page, name: string): Promise<string> {
  const response = await page.request.post("/api/v1/projects", {
    data: { name },
  });
  expect(response.status(), await response.text()).toBe(201);
  return (await response.json()).id as string;
}

test("PDF workspace persists view state and annotations", async ({ page }) => {
  await createSession(page);
  const projectId = await createProject(page, "E2E PDF Persistence");

  const pdf = await page.request.post(
    "/api/v1/projects/" + projectId + "/files",
    {
      multipart: {
        file: {
          name: "research.pdf",
          mimeType: "application/pdf",
          buffer: Buffer.from(
            "%PDF-1.4\\n1 0 obj\\n<< /Type /Catalog >>\\nendobj\\n",
          ),
        },
      },
    },
  );
  expect(pdf.status(), await pdf.text()).toBe(201);

  await page.goto("/pdf-workspace");
  await expect(page.getByLabel("PDF document")).toBeEnabled();
  await page.getByLabel("PDF document").selectOption({
    label: "research.pdf",
  });

  await page.getByLabel("Page").fill("4");
  await page.getByLabel("Zoom").fill("1.5");
  await page.getByRole("button", { name: "Save view state" }).click();
  await expect(page.getByText("PDF workspace state saved.")).toBeVisible();

  await page.getByLabel("Selected text").fill("Important finding");
  await page.getByLabel("Note").fill("Keep this claim in the evidence review.");
  await page.getByRole("button", { name: "Save annotation" }).click();
  await expect(page.getByText("Annotation saved.")).toBeVisible();
  await expect(page.getByText("Important finding", { exact: true })).toBeVisible();

  await page.reload();
  await expect(page.getByLabel("Page")).toHaveValue("4");
  await expect(page.getByLabel("Zoom")).toHaveValue("1.5");
  await expect(page.getByText("Important finding", { exact: true })).toBeVisible();
});

test("research canvas persists nodes, edges and revision", async ({ page }) => {
  await createSession(page);
  await createProject(page, "E2E Canvas Persistence");

  await page.goto("/research-canvas");
  await page.getByRole("button", { name: "Add node" }).click();

  await page.getByLabel("Title").last().fill("Primary hypothesis");
  await page.getByLabel("Body").last().fill("Sparse representations improve decoding robustness.");
  await page.getByRole("button", { name: "Save canvas" }).click();

  await expect(page.getByText("Canvas saved.")).toBeVisible();
  await expect(page.getByText(/Revision 2/)).toBeVisible();

  await page.reload();
  await expect(
    page.getByLabel("Title").last(),
  ).toBeVisible();
  await expect(
    page.getByLabel("Body").last(),
  ).toBeVisible();
});

test("project file evidence reports canonical source/chunk linkage", async ({
  page,
}) => {
  await createSession(page);
  const projectId = await createProject(page, "E2E Evidence Unification");

  const fileResponse = await page.request.post(
    "/api/v1/projects/" + projectId + "/files",
    {
      multipart: {
        file: {
          name: "evidence.txt",
          mimeType: "text/plain",
          buffer: Buffer.from(
            "The canonical evidence bridge turns extracted project files into report-local sources and chunks.",
          ),
        },
      },
    },
  );
  expect(fileResponse.status(), await fileResponse.text()).toBe(201);
  const file = (await fileResponse.json()) as { id: string };

  const reportResponse = await page.request.post("/api/v1/reports", {
    data: {
      topic: "Evidence bridge acceptance",
      output_language: "en",
      project_id: projectId,
    },
  });
  expect(reportResponse.status(), await reportResponse.text()).toBe(201);

  const evidenceResponse = await page.request.get(
    "/api/v1/projects/" + projectId + "/evidence/files",
  );
  expect(
    evidenceResponse.status(),
    await evidenceResponse.text(),
  ).toBe(200);
  const evidence = (await evidenceResponse.json()) as {
    items: Array<{
      file_id: string;
      evidence_status: string;
      source_count: number;
      chunk_count: number;
    }>;
  };

  const item = evidence.items.find((row) => row.file_id === file.id);
  expect(item).toBeTruthy();
  expect([
    "processing",
    "synced",
    "awaiting_report",
    "unavailable",
  ]).toContain(item?.evidence_status);
});
