import {expect,test} from "@playwright/test";

function uniqueEmail():string{
  return "surface+"+Date.now()+"@example.com";
}

const password="Research-AI-E2E-password-2026";

test("renders completed protected capability surfaces",async({page})=>{
  const email=uniqueEmail();
  await page.goto("/register");
  await page.getByLabel("Work email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByLabel("Workspace name").fill("Surface E2E Workspace");
  await page.getByRole("checkbox").check();
  const registerResponsePromise=page.waitForResponse(response=>
    response.url().endsWith("/api/auth/register")&&response.request().method()==="POST"
  );
  await page.getByRole("button",{name:/Create workspace/}).click();
  const registerResponse=await registerResponsePromise;
  expect(registerResponse.ok(),await registerResponse.text()).toBeTruthy();

  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  const loginResponsePromise=page.waitForResponse(response=>
    response.url().endsWith("/api/auth/login")&&response.request().method()==="POST"
  );
  await page.getByRole("button",{name:"Log in"}).click();
  const loginResponse=await loginResponsePromise;
  expect(loginResponse.ok(),await loginResponse.text()).toBeTruthy();
  await expect(page).toHaveURL(/\/dashboard/,{timeout:30_000});

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
