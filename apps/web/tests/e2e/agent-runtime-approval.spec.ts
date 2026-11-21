import {expect,test} from "@playwright/test";

function uniqueEmail():string {
  return "agent-runtime+"+Date.now()+"@example.com";
}

const password="Research-AI-E2E-password-2026";
const userId="11111111-1111-4111-8111-111111111111";
const sessionIds=[
  "22222222-2222-4222-8222-222222222221",
  "22222222-2222-4222-8222-222222222222",
];
const toolCallIds=[
  "33333333-3333-4333-8333-333333333331",
  "33333333-3333-4333-8333-333333333332",
];
const jobId="44444444-4444-4444-8444-444444444444";
const createdAt="2026-11-21T12:00:00Z";

test("requires an explicit decision before Agent Runtime registry tools execute",async({page})=>{
  test.setTimeout(120_000);
  const email=uniqueEmail();

  await page.goto("/register");
  await page.getByLabel("Work email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByLabel("Workspace name").fill("Agent Runtime E2E Workspace");
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

  await page.goto("/projects");
  await page.getByLabel("Project name").fill("Agent Runtime approval workflow");
  await page.getByLabel("Domain").fill("Research engineering");
  await page.getByLabel("Research objective").fill("Validate explicit Agent Runtime tool approval.");
  await page.getByRole("button",{name:"Continue"}).click();
  await page.getByLabel(/Research questions/).fill("Can a registry tool execute only after explicit approval?");
  const projectCreateResponsePromise=page.waitForResponse(response=>
    new URL(response.url()).pathname==="/api/backend/projects"&&response.request().method()==="POST"
  );
  await page.getByRole("button",{name:"Create project"}).click();
  const projectCreateResponse=await projectCreateResponsePromise;
  expect(projectCreateResponse.status(),await projectCreateResponse.text()).toBe(201);
  await expect(page).toHaveURL(/\/projects\/[0-9a-f-]+/i,{timeout:30_000});
  const projectId=(await page.url()).match(/\/projects\/([^?]+)/i)?.[1];
  expect(projectId).toBeTruthy();

  await page.getByLabel("Report topic").fill("Agent Runtime explicit-approval report");
  await page.getByRole("button",{name:"Create report"}).click();
  await expect(page).toHaveURL(/\/projects\/[0-9a-f-]+\?setup=research&reportId=[0-9a-f-]+/i,{timeout:30_000});
  const reportId=new URL(page.url()).searchParams.get("reportId");
  expect(reportId).toBeTruthy();

  const sessionStatus:Record<string,string>={
    [sessionIds[0]]:"awaiting_approval",
    [sessionIds[1]]:"awaiting_approval",
  };
  const toolStatus:Record<string,string>={
    [toolCallIds[0]]:"pending",
    [toolCallIds[1]]:"pending",
  };
  const decisions:string[]=[];
  let eventStreamRequests=0;

  await page.route("**/agent-runtime/**",async route=>{
    const request=route.request();
    const path=new URL(request.url()).pathname;
    const method=request.method();
    console.log("[Agent Runtime E2E] "+method+" "+path);
    const sessionListPath="/agent-runtime/sessions";
    const sessionIdFromPath=path.match(/\/agent-runtime\/sessions\/([^/]+)$/)?.[1];
    const decision=path.match(/\/agent-runtime\/sessions\/([^/]+)\/tool-calls\/([^/]+)\/(approve|reject)$/);

    if(method==="GET"&&path.endsWith(sessionListPath)){
      const items=sessionIds.map((id,index)=>({
        id,user_id:userId,project_id:projectId,report_id:reportId,
        title:index===0?"Approval review":"Rejection review",status:sessionStatus[id],
        active_job_id:null,next_sequence:1,revision:1,last_message_at:createdAt,
        last_error_code:null,created_at:createdAt,updated_at:createdAt,
      }));
      await route.fulfill({status:200,contentType:"application/json",body:JSON.stringify(items)});
      return;
    }

    if(method==="GET"&&path.endsWith("/events")){
      eventStreamRequests+=1;
      const events="data: "+JSON.stringify({
        id:2,
        type:"text_delta",
        payload:{text:"Streaming response from mocked model."},
      })+"\n\n";
      await route.fulfill({
        status:200,
        headers:{
          "content-type":"text/event-stream; charset=utf-8",
          "cache-control":"no-cache, no-transform",
          "x-accel-buffering":"no",
        },
        body:events,
      });
      return;
    }

    if(method==="GET"&&sessionIdFromPath&&sessionIds.includes(sessionIdFromPath)){
      const session={
        id:sessionIdFromPath,user_id:userId,project_id:projectId,report_id:reportId,
        title:sessionIdFromPath===sessionIds[0]?"Approval review":"Rejection review",
        status:sessionStatus[sessionIdFromPath],active_job_id:null,next_sequence:1,revision:1,
        last_message_at:createdAt,last_error_code:null,created_at:createdAt,updated_at:createdAt,
      };
      await route.fulfill({status:200,contentType:"application/json",body:JSON.stringify(session)});
      return;
    }

    const messagesSession=path.match(/\/agent-runtime\/sessions\/([^/]+)\/messages$/)?.[1];
    if(method==="GET"&&messagesSession&&sessionIds.includes(messagesSession)){
      await route.fulfill({status:200,contentType:"application/json",body:JSON.stringify({items:[],total:0,limit:50})});
      return;
    }

    const callsSession=path.match(/\/agent-runtime\/sessions\/([^/]+)\/tool-calls$/)?.[1];
    if(method==="GET"&&callsSession&&sessionIds.includes(callsSession)){
      const index=sessionIds.indexOf(callsSession);
      const item={
        id:toolCallIds[index],session_id:callsSession,user_message_id:"55555555-5555-4555-8555-555555555555",
        tool_key:"generate_citations",tool_version:"m39-tools-v2",
        tool_description:"Generate and validate citations for the current manuscript version.",
        reason:"The report has a manuscript version that needs citation generation.",
        arguments:{manuscript_version_id:"66666666-6666-4666-8666-666666666666"},
        status:toolStatus[toolCallIds[index]],output_preview:null,error_code:null,
        created_at:createdAt,approved_at:null,rejected_at:null,completed_at:null,
      };
      await route.fulfill({status:200,contentType:"application/json",body:JSON.stringify({items:[item],limit:20})});
      return;
    }

    if(method==="POST"&&decision){
      const [,sessionId,toolCallId,action]=decision;
      expect(sessionIds).toContain(sessionId);
      expect(toolCallIds).toContain(toolCallId);
      decisions.push(action);
      toolStatus[toolCallId]=action==="approve"?"queued":"rejected";
      sessionStatus[sessionId]=action==="approve"?"queued":"idle";
      const result={
        status:action==="approve"?"queued":"rejected",
        tool_call_id:toolCallId,session_id:sessionId,job_id:action==="approve"?jobId:null,
      };
      await route.fulfill({status:action==="approve"?202:200,contentType:"application/json",body:JSON.stringify(result)});
      return;
    }

    await route.fallback();
  });

  await page.goto("/workbench?projectId="+projectId+"&reportId="+reportId);
  await expect(page.getByRole("heading",{name:"Agent Runtime"})).toBeVisible({timeout:30_000});
  await expect(page.locator(".wb-agent-tool-card")).toHaveCount(1,{timeout:30_000});
  const firstCard=page.locator(".wb-agent-tool-card").first();
  await expect(firstCard.getByText("pending",{exact:true})).toBeVisible();
  await expect(firstCard.getByText("The report has a manuscript version that needs citation generation.")).toBeVisible();
  await firstCard.getByText("Review arguments").click();
  await expect(firstCard.locator("pre")).toContainText("manuscript_version_id");

  await firstCard.getByRole("button",{name:"Approve and run"}).click();
  await expect.poll(async()=>firstCard.locator(".wb-status").textContent()).toContain("queued");
  await expect(page.getByText("Streaming response from mocked model.",{exact:false})).toBeVisible({timeout:15_000});
  expect(eventStreamRequests).toBeGreaterThan(0);

  await page.getByLabel("Conversation").selectOption(sessionIds[1]);
  const secondCard=page.locator(".wb-agent-tool-card").first();
  await expect(secondCard.getByText("pending",{exact:true})).toBeVisible();
  await secondCard.getByRole("button",{name:"Reject"}).click();
  await expect.poll(async()=>secondCard.locator(".wb-status").textContent()).toContain("rejected");
  expect(decisions).toEqual(["approve","reject"]);
});
