import {expect,test} from "@playwright/test";

function uniqueEmail():string{
  return "e2e+"+Date.now()+"@example.test";
}

const password="Research-AI-E2E-password-2026";

test("creates project/report and uploads a research file through the browser",async({page})=>{
  const email=uniqueEmail();

  await page.goto("/register");
  await page.getByLabel("Work email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByLabel("Workspace name").fill("E2E Research Workspace");
  await page.getByRole("checkbox").check();
  const registerResponsePromise=page.waitForResponse(response=>
    response.url().endsWith("/api/auth/register")&&response.request().method()==="POST"
  );
  await page.getByRole("button",{name:/Create workspace/}).click();
  const registerResponse=await registerResponsePromise;
  expect(registerResponse.ok(),await registerResponse.text()).toBeTruthy();
  await expect(page).toHaveURL(/\/verify-email\?pending=1/,{timeout:30_000});

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

  await page.goto("/projects");
  await page.getByLabel("Project name").fill("Browser research upload");
  await page.getByLabel("Domain").fill("Research engineering");
  await page.getByLabel("Research objective").fill("Validate the end-to-end research intake workflow.");
  await page.getByRole("button",{name:"Continue"}).click();
  await page.getByLabel(/Research questions/).fill("Does browser upload persist?");
  await page.getByRole("button",{name:"Create project"}).click();

  await expect(page).toHaveURL(/\/projects\/[0-9a-f-]+/i);
  const projectId=(await page.url()).match(/\/projects\/([^?]+)/i)?.[1];
  expect(projectId).toBeTruthy();

  await page.getByLabel("Report topic").fill("End-to-end upload validation");
  await page.getByRole("button",{name:"Create report"}).click();
  await expect(page).toHaveURL(new RegExp("/projects/"+projectId+"\\?setup=research&reportId=", "i"));

  await page.goto("/files?projectId="+projectId);
  await expect(page.getByRole("heading",{name:"Upload"})).toBeVisible();

  const fileName="research-upload-"+Date.now()+".txt";
  await page.locator('input[type="file"]').setInputFiles({
    name:fileName,
    mimeType:"text/plain",
    buffer:Buffer.from("A browser-uploaded research source for end-to-end validation.\n"),
  });

  await expect(page.getByText(new RegExp(`Uploaded "${fileName}"`)).first()).toBeVisible({timeout:30_000});
  await expect(page.getByText(fileName,{exact:true}).first()).toBeVisible({timeout:30_000});
  await page.reload();
  await expect(page.getByText(fileName,{exact:true}).first()).toBeVisible({timeout:30_000});
});
