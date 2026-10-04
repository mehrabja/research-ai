import {expect,test} from "@playwright/test";

function uniqueEmail():string{
  return "surface+"+Date.now()+"@example.test";
}

const password="Research-AI-E2E-password-2026";

test("renders completed protected capability surfaces",async({page})=>{
  const email=uniqueEmail();
  await page.goto("/register");
  await page.getByLabel("Work email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByLabel("Workspace name").fill("Surface E2E Workspace");
  await page.getByRole("checkbox").check();
  await page.getByRole("button",{name:/Create workspace/}).click();

  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button",{name:"Log in"}).click();
  await expect(page).toHaveURL(/\/dashboard/);

  const routes=[
    ["/manuscript","Manuscript"],
    ["/evidence","Evidence matrix"],
    ["/rag","Research retrieval"],
    ["/knowledge","Knowledge graph"],
    ["/collaboration","Review queue"],
    ["/team","Workspace team"],
    ["/usage-billing","Usage & billing"],
    ["/settings","Workspace settings"],
  ] as const;

  for(const [path,heading] of routes){
    await page.goto(path);
    await expect(page.getByRole("heading",{name:heading})).toBeVisible();
  }

  await page.goto("/accept-invitation");
  await expect(page.getByRole("heading",{name:"Accept invitation"})).toBeVisible();
  await expect(page.getByLabel("Invitation token")).toBeVisible();
});
