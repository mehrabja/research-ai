import {expect,test} from "@playwright/test";

function uniqueEmail():string{
  return "e2e+"+Date.now()+"@example.com";
}

const password="Research-AI-E2E-password-2026";

test("creates project/report and uploads a research file through the browser",async({page})=>{
  test.setTimeout(90_000);
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
  const projectCreateResponsePromise=page.waitForResponse(response=>
    new URL(response.url()).pathname==="/api/backend/projects"&&response.request().method()==="POST"
  );
  await page.getByRole("button",{name:"Create project"}).click();
  const projectCreateResponse=await projectCreateResponsePromise;
  expect(projectCreateResponse.status(),await projectCreateResponse.text()).toBe(201);

  await expect(page).toHaveURL(/\/projects\/[0-9a-f-]+/i,{timeout:30_000});
  const projectId=(await page.url()).match(/\/projects\/([^?]+)/i)?.[1];
  expect(projectId).toBeTruthy();

  await page.getByLabel("Report topic").fill("End-to-end upload validation");
  await page.getByRole("button",{name:"Create report"}).click();
  await expect(page).toHaveURL(new RegExp("/projects/"+projectId+"\\?setup=research&reportId=", "i"));

  await page.goto("/files?projectId="+projectId);
  await expect(page.getByRole("heading",{name:"Upload"})).toBeVisible();

  const fileName="research-upload-"+Date.now()+".txt";
  const filePathPattern=/\/api\/backend\/projects\/[^/]+\/files(?:\?|$)/;
  page.on("requestfailed",request=>{
    if(filePathPattern.test(new URL(request.url()).pathname)){
      console.log(`[E2E] file request failed: ${request.failure()?.errorText??"unknown"} ${request.url()}`);
    }
  });
  page.on("response",response=>{
    if(filePathPattern.test(new URL(response.url()).pathname)){
      console.log(`[E2E] file response: ${response.request().method()} ${response.status()} ${response.url()}`);
    }
  });

  const uploadRequestPromise=page.waitForRequest(request=>
    filePathPattern.test(new URL(request.url()).pathname)&&request.method()==="POST"
  );
  const uploadResponsePromise=page.waitForResponse(response=>
    filePathPattern.test(new URL(response.url()).pathname)&&response.request().method()==="POST"
  );

  const fileChooserPromise=page.waitForEvent("filechooser");
  await page.getByRole("button",{name:"Choose a file"}).click();
  const fileChooser=await fileChooserPromise;
  const fileInput=page.locator('input[type="file"]');
  await fileChooser.setFiles({
    name:fileName,
    mimeType:"text/plain",
    buffer:Buffer.from("A browser-uploaded research source for end-to-end validation.\n"),
  });
  await expect.poll(async()=>fileInput.evaluate(element=>(element as HTMLInputElement).files?.[0]?.name??""))
    .toBe(fileName);

  const uploadRequest=await uploadRequestPromise;
  console.log(`[E2E] upload request started: ${uploadRequest.url()}`);
  const uploadResponse=await uploadResponsePromise;
  expect(uploadResponse.ok(),await uploadResponse.text()).toBeTruthy();

  await expect.poll(async()=>page.evaluate(async({projectId,fileName})=>{
    const response=await fetch("/api/backend/projects/"+projectId+"/files",{credentials:"same-origin",cache:"no-store"});
    if(!response.ok)return false;
    const body=await response.json().catch(()=>null) as {items?:Array<{original_filename?:string}>}|null;
    return body?.items?.some(item=>item.original_filename===fileName)===true;
  },{projectId,fileName}),{timeout:30_000,intervals:[1_000]}).toBe(true);
  await expect(page.getByText(fileName,{exact:true}).first()).toBeVisible({timeout:30_000});
  await page.reload();
  await expect(page.getByText(fileName,{exact:true}).first()).toBeVisible({timeout:30_000});
});
