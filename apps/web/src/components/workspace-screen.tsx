"use client";
import Link from "next/link";
import {useEffect,useMemo,useRef,useState} from "react";
import {useMutation,useQuery,useQueryClient} from "@tanstack/react-query";
import {useRouter,useSearchParams} from "next/navigation";
import {AppShell,useWorkspace} from "./app-shell";
import {api} from "@/lib/api/client";
import type {FileFolder,RAGResponse,SourceCandidate,TwoFactorEnrollment} from "@/lib/api/generated";

type Obj=Record<string,unknown>;
const META:Record<string,{eyebrow:string;title:string;description:string}>={
  dashboard:{eyebrow:"Workspace",title:"Research control plane",description:"Projects, evidence, jobs and usage from the selected workspace."},
  workspace:{eyebrow:"Workspace",title:"Research workspace",description:"Tenant context, project inventory and workspace lifecycle."},
  research:{eyebrow:"Discovery",title:"Research discovery",description:"Workspace-scoped research search with real API results."},
  sources:{eyebrow:"Corpus",title:"Source library",description:"Saved sources and discovery candidates for the active report."},
  literature:{eyebrow:"Synthesis",title:"Literature intelligence",description:"Analysis, clusters, themes, screening and gaps."},
  evidence:{eyebrow:"Evidence",title:"Evidence matrix",description:"Claims, support, conflict, confidence and provenance."},
  knowledge:{eyebrow:"Knowledge",title:"Knowledge graph",description:"Concepts and relationships with JSON/CSV export."},
  rag:{eyebrow:"Retrieval",title:"Research retrieval",description:"Lexical, semantic and hybrid retrieval over research-ready sources."},
  files:{eyebrow:"Files & intelligence",title:"Project files",description:"Files, folders and intelligence lifecycle."},
  plan:{eyebrow:"Planning",title:"Research plan",description:"Versioned objectives, evidence requirements and dependencies."},
  manuscript:{eyebrow:"Writing",title:"Manuscript",description:"Versioned manuscript content and autosave state."},
  generate:{eyebrow:"AI Studio",title:"Generate",description:"Queue evidence-grounded generation as a durable job."},
  humanize:{eyebrow:"Rewrite",title:"Humanize",description:"Version-aware rewriting with preservation checks."},
  translate:{eyebrow:"Language",title:"Translate",description:"Version-locked translation with citation preservation."},
  collaboration:{eyebrow:"Collaboration",title:"Review queue",description:"Members, invitations and review coordination."},
  jobs:{eyebrow:"Operations",title:"Jobs",description:"Durable jobs, retry, cancellation and failure state."},
  team:{eyebrow:"Team",title:"Workspace team",description:"Membership and role management."},
  "usage-billing":{eyebrow:"SaaS",title:"Usage & billing",description:"Usage, entitlements, subscription and invoices."},
  settings:{eyebrow:"Settings",title:"Workspace settings",description:"Notifications, sessions, 2FA and API access."},
};
function row(v:unknown):Obj{ return v&&typeof v==="object"&&!Array.isArray(v)?v as Obj:{}; }
function rows(v:unknown):Obj[]{ return Array.isArray(v)?v.filter(x=>x&&typeof x==="object") as Obj[]:[]; }
function value(v:unknown,fallback="—"):string{ if(typeof v==="string"&&v.trim())return v; if(typeof v==="number"||typeof v==="boolean")return String(v); return fallback; }
function Head({route,actions}:{route:string;actions?:React.ReactNode}){const m=META[route]??{eyebrow:"Research AI",title:"Page",description:""};return <div className="page-head"><div><div className="eyebrow">{m.eyebrow}</div><h1>{m.title}</h1><p>{m.description}</p></div>{actions&&<div className="actions">{actions}</div>}</div>}
function Card({children,style,id}:{children:React.ReactNode;style?:React.CSSProperties;id?:string}){return <section className="card pad" style={style} id={id}>{children}</section>}
function State({title,description,error=false,children}:{title:string;description:string;error?:boolean;children?:React.ReactNode}){return <div className={"state"+(error?" error":"")}><h3>{title}</h3><p>{description}</p>{children&&<div className="actions" style={{justifyContent:"center",marginTop:14}}>{children}</div>}</div>}
function Table({data}:{data:Obj[]}){return <div className="table-wrap"><table className="table"><thead><tr><th>Record</th><th>Status</th><th>Identifier</th></tr></thead><tbody>{data.slice(0,30).map((x,i)=><tr key={i}><td>{value(x.title??x.name??x.claim??x.type,"Record")}</td><td>{value(x.status??x.state)}</td><td className="mono">{value(x.id)}</td></tr>)}</tbody></table></div>}

export function WorkspaceScreen({route}:{route:string}){return <Screen route={route}/>;}

function Screen({route}:{route:string}){
 switch(route){
 case "dashboard":return <Dashboard/>;case "rag":return <RAG/>;case "workspace":return <Workspace/>;case "research":return <Research/>;case "sources":return <Sources/>;case "literature":return <Literature/>;case "evidence":return <Evidence/>;case "notifications":return <Notifications/>;case "jobs":return <Jobs/>;case "team":return <Team/>;case "settings":return <Settings/>;case "usage-billing":return <Billing/>;case "knowledge":return <Knowledge/>;case "files":return <Files/>;case "plan":return <Plan/>;case "manuscript":return <Manuscript/>;case "generate":return <Generate/>;case "humanize":return <Humanize/>;case "translate":return <Translate/>;case "collaboration":return <Collaboration/>;
 default:return <Generic route={route}/>;
 }
}

function useCtx(){const ws=useWorkspace();const params=useSearchParams();const requestedProjectId=params.get("projectId");const requestedReportId=params.get("reportId");const projects=useQuery({queryKey:["projects",ws.workspaceId],queryFn:()=>api.projects(ws.workspaceId!),enabled:Boolean(ws.workspaceId)});const projectId=useMemo(()=>requestedProjectId&&projects.data?.items.some(p=>p.id===requestedProjectId)?requestedProjectId:projects.data?.items?.[0]?.id,[projects.data,requestedProjectId]);const reports=useQuery({queryKey:["reports",projectId],queryFn:()=>api.projectReports(projectId!,ws.workspaceId!),enabled:Boolean(projectId&&ws.workspaceId)});const reportId=useMemo(()=>requestedReportId&&reports.data?.items.some(r=>r.id===requestedReportId)?requestedReportId:reports.data?.items?.[0]?.id,[reports.data,requestedReportId]);const activeProject=useMemo(()=>projects.data?.items.find(p=>p.id===projectId),[projects.data,projectId]);const activeReport=useMemo(()=>reports.data?.items.find(r=>r.id===reportId),[reports.data,reportId]);return {ws,projects,projectId,reports,reportId,activeProject,activeReport};}

function WorkflowContext({route,projectId,reportId,projects,reports}:{route:string;projectId:string|undefined;reportId:string|undefined;projects:ReturnType<typeof useCtx>["projects"];reports:ReturnType<typeof useCtx>["reports"]}){
  const router=useRouter();
  const params=useSearchParams();
  const projectItems=projects.data?.items??[];
  const reportItems=reports.data?.items??[];
  function navigate(nextProjectId:string,nextReportId?:string){
    const next=new URLSearchParams(params.toString());
    next.set("projectId",nextProjectId);
    if(nextReportId)next.set("reportId",nextReportId);
    else next.delete("reportId");
    router.push("/"+route+"?"+next.toString());
  }
  return <Card style={{marginTop:16}}>
    <div className="row" style={{alignItems:"flex-start"}}>
      <div style={{minWidth:0}}>
        <div className="kicker">Active research context</div>
        <div className="strong" style={{marginTop:3}}>Project → Report</div>
        <div className="muted tiny" style={{marginTop:3}}>Every discovery and source action below is scoped to the selected report.</div>
      </div>
      <Link className="btn" href={projectId?"/projects/"+projectId:"/projects"}>Project setup</Link>
    </div>
    <div className="grid grid-2" style={{marginTop:12}}>
      <div className="field">
        <label>Project</label>
        <select className="input" value={projectId??""} onChange={e=>navigate(e.target.value)} disabled={!projectItems.length}>
          {!projectItems.length&&<option value="">No projects</option>}
          {projectItems.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
      </div>
      <div className="field">
        <label>Report</label>
        <select className="input" value={reportId??""} onChange={e=>navigate(projectId!,e.target.value)} disabled={!projectId||reports.isPending||!reportItems.length}>
          {!reportItems.length&&<option value="">No report</option>}
          {reportItems.map(r=><option key={r.id} value={r.id}>{r.topic}</option>)}
        </select>
      </div>
    </div>
    {!projectId&&<div className="notice" style={{marginTop:12}}>Create a project first, then create its first report to start the Research → Sources workflow.</div>}
    {projectId&&!reportId&&!reports.isPending&&<div className="notice" style={{marginTop:12}}>This project has no report yet. Open Project setup and create the first report.</div>}
  </Card>;
}

function Dashboard(){const {ws,projects}=useCtx();const s=useQuery({queryKey:["dashboard",ws.workspaceId],queryFn:()=>api.dashboard(ws.workspaceId!),enabled:Boolean(ws.workspaceId)});const items=projects.data?.items??[];return <><Head route="dashboard" actions={<><Link className="btn primary" href="/projects">Create project</Link><Link className="btn" href="/team">Invite teammate</Link><Link className="btn" href="/workspace">Workspace overview</Link></>}/><div className="grid grid-4"><Metric label="Active projects" value={s.data?.active_projects}/><Metric label="Saved sources" value={s.data?.saved_sources}/><Metric label="Evidence items" value={s.data?.evidence_items}/><Metric label="AI generation units" value={s.data?.ai_generation_units}/></div><Card style={{marginTop:16}}><div className="row"><div><h3>Projects</h3><div className="muted tiny">Projects are the starting point for research work in this workspace.</div></div>{items.length>0&&<Link className="btn" href="/projects">View all projects</Link>}</div>{projects.isPending?<State title="Loading projects" description="Reading projects from the selected workspace."/>:items.length===0?<State title="Start your first research project" description="Create a project to define the research context, then create a report and continue into Research discovery."><Link className="btn primary" href="/projects">Create project →</Link></State>:<Table data={items as unknown as Obj[]}/>}</Card></>}
function Metric({label,value:v}:{label:string;value:unknown}){return <div className="card metric"><div className="label">{label}</div><div className="value">{value(v)}</div><div className="delta">Backend source of truth</div></div>}

function Research(){
  const {ws,reportId,projectId,projects,reports}=useCtx();
  const p=useSearchParams();
  const qc=useQueryClient();
  const [q,setQ]=useState(p.get("q")??"");
  const [submittedQuery,setSubmittedQuery]=useState("");
  const [year,setYear]=useState("");
  const [count,setCount]=useState(25);
  const [openAccess,setOpenAccess]=useState(false);
  const [savingIds,setSavingIds]=useState<string[]>([]);
  const [savedIds,setSavedIds]=useState<string[]>([]);
  const sources=useQuery({queryKey:["sources",reportId],queryFn:()=>api.sources(reportId!),enabled:Boolean(reportId)});
  const search=useQuery({
    queryKey:["source-discovery",reportId,submittedQuery,count,year,openAccess],
    queryFn:()=>api.searchSources(reportId!,submittedQuery,count,year?Number(year):undefined,openAccess),
    enabled:Boolean(reportId&&submittedQuery),
  });
  const save=useMutation({
    mutationFn:(item:SourceCandidate)=>api.createSource(reportId!,item),
    onMutate:item=>setSavingIds(ids=>ids.includes(item.external_source_id)?ids:[...ids,item.external_source_id]),
    onSuccess:(data,item)=>{setSavedIds(ids=>ids.includes(item.external_source_id)?ids:[...ids,item.external_source_id]);},
    onError:e=>setError(e instanceof Error?e.message:"Save source failed."),
    onSettled:(_,__,item)=>setSavingIds(ids=>ids.filter(id=>id!==item.external_source_id)),
  });
  const [error,setError]=useState("");
  const bulkSave=useMutation({
    mutationFn:async(items:SourceCandidate[])=>{
      const pending=items.filter(item=>!savedIds.includes(item.external_source_id));
      return Promise.all(pending.map(item=>api.createSource(reportId!,item)));
    },
    onSuccess:async results=>{
      setSavedIds(ids=>Array.from(new Set([...ids,...results.map(item=>item.external_source_id)])));
      await qc.invalidateQueries({queryKey:["sources",reportId]});
    },
    onError:e=>setError(e instanceof Error?e.message:"Bulk source save failed. Retry the operation."),
  });
  useEffect(()=>{
    const ids=(sources.data?.items??[]).map(item=>item.external_source_id).filter((id):id is string=>Boolean(id));
    if(ids.length)setSavedIds(ids);
  },[sources.data]);
  const global=useQuery({
    queryKey:["global-search",ws.workspaceId,q],
    queryFn:()=>api.globalSearch(q,ws.workspaceId!),
    enabled:Boolean(ws.workspaceId&&q.trim()&&!reportId),
  });
  const canSearch=Boolean(reportId&&q.trim()&&count>=1&&count<=1000);
  function runSearch(){
    if(canSearch)setSubmittedQuery(q.trim());
  }
  function doiHref(doi:string){
    return doi.startsWith("http://")||doi.startsWith("https://")?doi:"https://doi.org/"+doi.replace(/^doi:\s*/i,"");
  }
  return <><Head route="research"/>
    <WorkflowContext route="research" projectId={projectId} reportId={reportId} projects={projects} reports={reports}/>
    <div className="grid grid-3">
      <Card>
        <div className="field"><label>Research query</label><input className="input" value={q} onChange={e=>setQ(e.target.value)} onKeyDown={e=>{if(e.key==="Enter")runSearch()}} placeholder="topic, DOI, title, author…"/></div>
        <div className="field" style={{marginTop:12}}><label>Number of papers</label><input className="input" type="number" min={1} max={1000} step={1} value={count} onChange={e=>setCount(Math.max(1,Math.min(1000,Number(e.target.value)||1)))}/></div>
        <button className="btn primary" style={{marginTop:12}} disabled={!canSearch||search.isFetching} onClick={runSearch}>{search.isFetching?"Searching…":"Search papers"}</button>
      </Card>
      <Card><div className="field"><label>Year</label><input className="input" inputMode="numeric" value={year} onChange={e=>setYear(e.target.value.replace(/\D/g,"").slice(0,4))} placeholder="2024"/></div></Card>
      <Card><label className="checkbox"><input type="checkbox" checked={openAccess} onChange={e=>setOpenAccess(e.target.checked)}/><span><b>Open access only</b><br/><span className="muted tiny">Additional provider pages are fetched when needed to fill the requested count.</span></span></label></Card>
    </div>
    <Card style={{marginTop:16}}>
      <div className="row"><div><h3>Discovery results</h3><div className="muted small">{reportId?"Semantic Scholar-backed source discovery for the active report.":"Create a project and report first to search papers."}</div></div><div className="actions"><span className="tag">{search.data?.candidates?.length??global.data?.total??0} results</span>{reportId&&submittedQuery&&(search.data?.candidates?.some(item=>!savedIds.includes(item.external_source_id))??false)&&<button className="btn" disabled={bulkSave.isPending} onClick={()=>bulkSave.mutate(search.data?.candidates??[])}>{bulkSave.isPending?"Saving…":"Save all results"}</button>}</div></div>
      {!reportId&&<div className="notice" style={{marginTop:12}}>No active report. <Link href="/projects" style={{color:"var(--primary)",fontWeight:700}}>Create a project</Link>, then create a report inside it.</div>}
      {reportId&&!submittedQuery&&<State title="Ready to search" description="Enter a title, topic, DOI or author and press Search papers."/>}
      {reportId&&submittedQuery&&search.isFetching&&<State title="Searching papers" description={"Searching for “"+submittedQuery+"” and collecting up to "+count+" results."}/>}
      {reportId&&submittedQuery&&!search.isFetching&&search.isError&&<State title="Search failed" description={search.error instanceof Error?search.error.message:"The research provider returned an error."} error/>}
      {reportId&&submittedQuery&&!search.isFetching&&!search.isError&&<div className="list" style={{marginTop:10}}>
        {search.data?.candidates?.map((item,index)=>{
          const key=item.external_source_id??String(index);
          const saved=savedIds.includes(item.external_source_id);
          const saving=savingIds.includes(item.external_source_id);
          return <div className="list-item" key={key}>
            <div className="row" style={{alignItems:"flex-start"}}>
              <div style={{minWidth:0,flex:1}}>
                <div className="title" style={{overflowWrap:"anywhere"}}>{item.title}</div>
                <div className="meta" style={{overflowWrap:"anywhere"}}>{item.year??"Year unknown"} · {(item.authors??[]).slice(0,3).join(", ")||"Authors unavailable"} · {item.citation_count??0} citations</div>
                {item.abstract&&<div className="muted small" style={{marginTop:6,lineHeight:1.55}}>{item.abstract}</div>}
                <div className="actions" style={{marginTop:8}}>
                  {item.url&&<a className="btn" href={item.url} target="_blank" rel="noreferrer">Open article ↗</a>}
                  {item.doi&&<a className="btn" href={doiHref(item.doi)} target="_blank" rel="noreferrer">DOI ↗</a>}
                </div>
              </div>
              <button className={"btn"+(saved?" primary":"")} disabled={saved||saving||save.isPending} onClick={()=>save.mutate(item)}>{saving?"Saving…":saved?"Saved ✓":"Save source"}</button>
            </div>
          </div>;
        })}
        {(search.data?.candidates?.length??0)===0&&<State title="No papers found" description={"No provider result was returned for “"+submittedQuery+"” with the selected filters."}/>}
      </div>}
      {!reportId&&q&&<Table data={rows(global.data?.items)}/>}
      {error&&<div className="notice error" style={{marginTop:12}}>{error}</div>}
    </Card>
  </>;
}

function Notifications(){
  const {ws}=useCtx();
  const qc=useQueryClient();
  const q=useQuery({queryKey:["notifications-page",ws.workspaceId],queryFn:()=>api.notifications(ws.workspaceId!),enabled:Boolean(ws.workspaceId)});
  const read=useMutation({mutationFn:(id:string)=>api.markNotificationRead(id),onSuccess:()=>qc.invalidateQueries({queryKey:["notifications-page",ws.workspaceId]})});
  const all=useMutation({mutationFn:()=>api.readAllNotifications(ws.workspaceId!),onSuccess:()=>qc.invalidateQueries({queryKey:["notifications-page",ws.workspaceId]})});
  return <><Head route="notifications" actions={<button className="btn" disabled={!ws.workspaceId||all.isPending} onClick={()=>all.mutate()}>{all.isPending?"Marking…":"Mark all read"}</button>}/><Card><div className="row"><h3>Activity</h3><span className="tag primary">{q.data?.unread??0} unread</span></div><div className="list" style={{marginTop:10}}>{q.data?.items.map(n=><div className="list-item" key={n.id}><div className="row"><div><div className="title">{n.title}</div><div className="meta">{n.body??"No message"} · {new Date(n.created_at).toLocaleString()}</div></div>{n.read_at?<span className="tag">Read</span>:<button className="btn" onClick={()=>read.mutate(n.id)}>Mark read</button>}</div></div>)}{!q.isPending&&!q.data?.items.length&&<State title="No notifications" description="Review, workspace, job and security activity will appear here."/>}</div></Card></>;
}

function Jobs(){
  const {ws}=useCtx();
  const qc=useQueryClient();
  const q=useQuery({queryKey:["jobs",ws.workspaceId],queryFn:()=>api.jobs(ws.workspaceId??undefined),enabled:Boolean(ws.workspaceId),refetchInterval:5000});
  const retry=useMutation({mutationFn:(id:string)=>api.retryJob(id),onSuccess:()=>qc.invalidateQueries({queryKey:["jobs",ws.workspaceId]})});
  const cancel=useMutation({mutationFn:(id:string)=>api.cancelJob(id),onSuccess:()=>qc.invalidateQueries({queryKey:["jobs",ws.workspaceId]})});
  const operationError=retry.error??cancel.error;
  return <><Head route="jobs"/>
    <Card>
      {q.isError&&<State title="Jobs unavailable" description={q.error instanceof Error?q.error.message:"The job service could not be reached."} error/>}
      {q.isPending&&<State title="Loading jobs" description="Reading durable operations for the selected workspace."/>}
      {q.data?.length===0&&!q.isPending&&!q.isError&&<State title="No active jobs" description="Long-running research, analysis and generation jobs will appear here."/>}
      {q.data&&q.data.length>0&&<div className="table-wrap"><table className="table"><thead><tr><th>Operation</th><th>Status</th><th>Attempts</th><th>Timing</th><th>Error</th><th>Action</th></tr></thead><tbody>{q.data.map(job=>{
        const retrying=retry.isPending&&retry.variables===job.id;const cancelling=cancel.isPending&&cancel.variables===job.id;
        return <tr key={job.id}><td><div className="strong">{job.job_type}</div><div className="meta">{job.report_id?"Report "+job.report_id:"Project/workspace job"}</div></td><td>{job.status}</td><td>{job.attempt_count}/{job.max_attempts}</td><td><div>{job.created_at?new Date(job.created_at).toLocaleString():"—"}</div><div className="meta">{job.completed_at?new Date(job.completed_at).toLocaleString():job.started_at?"Started "+new Date(job.started_at).toLocaleString():"Queued"}</div></td><td style={{overflowWrap:"anywhere"}}>{job.last_error_message??job.last_error_code??"—"}</td><td>{job.status==="failed"?<button className="btn" disabled={retry.isPending} onClick={()=>retry.mutate(job.id)}>{retrying?"Retrying…":"Retry"}</button>:["queued","processing","retrying"].includes(job.status)?<button className="btn" disabled={cancel.isPending} onClick={()=>cancel.mutate(job.id)}>{cancelling?"Cancelling…":"Cancel"}</button>:<span className="tag">Done</span>}</td></tr>;
      })}</tbody></table></div>}
      {operationError&&<div className="notice error" style={{marginTop:12}}>{operationError instanceof Error?operationError.message:"Job operation failed. Retry the action."}</div>}
    </Card>
  </>;
}
function Team(){
  const {ws}=useCtx();
  const qc=useQueryClient();
  const members=useQuery({queryKey:["members",ws.workspaceId],queryFn:()=>api.members(ws.workspaceId!),enabled:Boolean(ws.workspaceId)});
  const invitations=useQuery({queryKey:["invitations",ws.workspaceId],queryFn:()=>api.invitations(ws.workspaceId!),enabled:Boolean(ws.workspaceId)});
  const me=useQuery({queryKey:["me"],queryFn:api.me});
  const [email,setEmail]=useState("");
  const [role,setRole]=useState("member");
  const [transferTarget,setTransferTarget]=useState("");
  const [inviteToken,setInviteToken]=useState("");
  const [error,setError]=useState("");

  const invite=useMutation({
    mutationFn:()=>api.invite(ws.workspaceId!,{email,role}),
    onSuccess:async result=>{
      setEmail("");
      setInviteToken(result.token);
      setError("");
      await qc.invalidateQueries({queryKey:["members",ws.workspaceId]});
      await qc.invalidateQueries({queryKey:["invitations",ws.workspaceId]});
    },
    onError:e=>setError(e instanceof Error?e.message:"Invitation failed."),
  });
  const revokeInvitation=useMutation({
    mutationFn:(id:string)=>api.revokeInvitation(ws.workspaceId!,id),
    onSuccess:()=>{setError("");void qc.invalidateQueries({queryKey:["invitations",ws.workspaceId]});},
    onError:e=>setError(e instanceof Error?e.message:"Invitation could not be revoked."),
  });
  const changeRole=useMutation({
    mutationFn:(x:{userId:string;role:string})=>api.changeMemberRole(ws.workspaceId!,x.userId,x.role),
    onSuccess:()=>{setError("");void qc.invalidateQueries({queryKey:["members",ws.workspaceId]});},
    onError:e=>setError(e instanceof Error?e.message:"Member role could not be changed."),
  });
  const remove=useMutation({
    mutationFn:(id:string)=>api.removeMember(ws.workspaceId!,id),
    onSuccess:()=>{setError("");void qc.invalidateQueries({queryKey:["members",ws.workspaceId]});},
    onError:e=>setError(e instanceof Error?e.message:"Member could not be removed."),
  });
  const transfer=useMutation({
    mutationFn:()=>api.transferOwnership(ws.workspaceId!,transferTarget),
    onSuccess:async()=>{
      setTransferTarget("");
      setError("");
      await qc.invalidateQueries({queryKey:["members",ws.workspaceId]});
      await qc.invalidateQueries({queryKey:["workspaces"]});
    },
    onError:e=>setError(e instanceof Error?e.message:"Ownership transfer failed."),
  });

  const activeMembers=members.data?.items??[];
  const transferable=activeMembers.filter(member=>member.role!=="owner"&&member.user_id!==me.data?.id);
  const pendingInvites=(invitations.data?.items??[]).filter(inv=>inv.state==="pending");

  async function copyInviteToken(){
    if(!inviteToken)return;
    try{
      await navigator.clipboard.writeText(inviteToken);
      setError("");
    }catch{
      setError("The browser did not allow clipboard access. Copy the token manually.");
    }
  }

  return <><Head route="team"/>
    {error&&<div className="notice error" style={{marginBottom:14}}>{error}</div>}
    <div className="grid grid-2">
      <Card><h3>Invite collaborator</h3><p className="muted small">Invitation state is durable. The raw token is displayed only once after creation.</p>
        <div className="field" style={{marginTop:14}}><label>Email</label><input className="input" type="email" autoComplete="email" value={email} onChange={e=>setEmail(e.target.value)} placeholder="researcher@lab.edu"/></div>
        <div className="field" style={{marginTop:12}}><label>Role</label><select className="input" value={role} onChange={e=>setRole(e.target.value)}><option value="member">Member</option><option value="viewer">Viewer</option><option value="admin">Admin</option></select></div>
        <button className="btn primary" style={{marginTop:12}} disabled={!ws.workspaceId||!email||invite.isPending} onClick={()=>invite.mutate()}>{invite.isPending?"Creating…":"Create invitation"}</button>
        {inviteToken&&<div className="notice success" style={{marginTop:12}}><div><b>Invitation token</b> — copy it now; it will not be returned again.</div><div className="mono" style={{overflowWrap:"anywhere",marginTop:8}}>{inviteToken}</div><button className="btn" style={{marginTop:8}} onClick={()=>void copyInviteToken()}>Copy token</button></div>}
      </Card>
      <Card><h3>Ownership transfer</h3><p className="muted small">Transfer makes the selected active member the workspace owner. The current owner becomes an admin.</p>
        <select className="input" value={transferTarget} onChange={e=>setTransferTarget(e.target.value)} disabled={transfer.isPending||transferable.length===0}>
          <option value="">{transferable.length?"Select active member":"No eligible member"}</option>
          {transferable.map(member=><option key={member.user_id} value={member.user_id}>{member.email} · {member.role}</option>)}
        </select>
        <button className="btn" style={{marginTop:10}} disabled={!transferTarget||transfer.isPending} onClick={()=>{if(confirm("Transfer workspace ownership to the selected member?"))transfer.mutate();}}>{transfer.isPending?"Transferring…":"Transfer ownership"}</button>
      </Card>
    </div>

    <Card style={{marginTop:16}}><div className="row"><div><h3>Pending invitations</h3><div className="muted tiny">Revoke invitations that should no longer be accepted.</div></div><span className="tag">{pendingInvites.length}</span></div>
      {invitations.isError?<State title="Invitations unavailable" description={invitations.error instanceof Error?invitations.error.message:"Invitation state could not be loaded."} error/>:pendingInvites.length===0&&!invitations.isPending?<State title="No pending invitations" description="New invitation tokens will appear here after creation."/>:<div className="list" style={{marginTop:10}}>{pendingInvites.map(inv=><div className="list-item" key={inv.id}><div className="row"><div><div className="title">{inv.email}</div><div className="meta">{inv.role} · expires {new Date(inv.expires_at).toLocaleString()}</div></div><button className="btn" disabled={revokeInvitation.isPending} onClick={()=>{if(confirm("Revoke this invitation?"))revokeInvitation.mutate(inv.id);}}>Revoke</button></div></div>)}</div>}
    </Card>

    <Card style={{marginTop:16}}><h3>Members</h3>{members.isError?<State title="Members unavailable" description={members.error instanceof Error?members.error.message:"Workspace membership could not be loaded."} error/>:members.isPending?<State title="Loading members" description="Reading active workspace membership."/>:<div className="table-wrap"><table className="table"><thead><tr><th>Member</th><th>Role</th><th>Status</th><th>Actions</th></tr></thead><tbody>{activeMembers.map(member=><tr key={member.user_id}><td>{member.email}</td><td><select className="input" aria-label={"Role for "+member.email} value={member.role} onChange={e=>changeRole.mutate({userId:member.user_id,role:e.target.value})} disabled={changeRole.isPending||member.role==="owner"}><option value="owner" disabled>Owner</option><option value="admin">Admin</option><option value="member">Member</option><option value="viewer">Viewer</option></select></td><td>{member.status}</td><td><button className="btn" disabled={remove.isPending||member.role==="owner"} onClick={()=>{if(confirm("Remove this member from the workspace?"))remove.mutate(member.user_id);}}>Remove</button></td></tr>)}</tbody></table></div>}</Card>

    <Card style={{marginTop:16}}><h3>Role matrix</h3><div className="list" style={{marginTop:10}}>{[["Owner","workspace ownership"],["Admin","members, billing and settings"],["Member","research and content"],["Viewer","read-only access"]].map(([a,b])=><div className="list-item" key={a}><div className="row"><b>{a}</b><span className="muted small">{b}</span></div></div>)}</div></Card>
  </>;
}
function Billing(){
  const {ws}=useCtx();
  const qc=useQueryClient();
  const u=useQuery({queryKey:["usage",ws.workspaceId],queryFn:()=>api.usage(ws.workspaceId!),enabled:Boolean(ws.workspaceId)});
  const p=useQuery({queryKey:["plan",ws.workspaceId],queryFn:()=>api.planSubscription(ws.workspaceId!),enabled:Boolean(ws.workspaceId)});
  const s=useQuery({queryKey:["subscription",ws.workspaceId],queryFn:()=>api.subscription(ws.workspaceId!),enabled:Boolean(ws.workspaceId)});
  const i=useQuery({queryKey:["invoices",ws.workspaceId],queryFn:()=>api.billingInvoices(ws.workspaceId!),enabled:Boolean(ws.workspaceId)});
  const [code,setCode]=useState("pro");
  useEffect(()=>{if(s.data?.plan_code)setCode(s.data.plan_code);},[s.data?.plan_code]);
  const checkout=useMutation({mutationFn:()=>api.billingCheckout(ws.workspaceId!,code),onError:()=>undefined});
  const changePlan=useMutation({mutationFn:()=>api.billingChangePlan(ws.workspaceId!,code),onSuccess:async()=>{await qc.invalidateQueries({queryKey:["plan",ws.workspaceId]});await qc.invalidateQueries({queryKey:["subscription",ws.workspaceId]});await qc.invalidateQueries({queryKey:["usage",ws.workspaceId]});}});
  const cancel=useMutation({mutationFn:()=>api.billingCancel(ws.workspaceId!),onSuccess:()=>void qc.invalidateQueries({queryKey:["subscription",ws.workspaceId]}),});
  const resume=useMutation({mutationFn:()=>api.billingResume(ws.workspaceId!),onSuccess:()=>void qc.invalidateQueries({queryKey:["subscription",ws.workspaceId]}),});
  const usageItems=u.data?.items??[];
  const subscriptionError=changePlan.error??cancel.error??resume.error;
  return <><Head route="usage-billing"/>
    {(p.isError||s.isError||u.isError||i.isError)&&<div className="notice error" style={{marginBottom:14}}>{p.isError?(p.error instanceof Error?p.error.message:"Plan data could not be loaded."):s.isError?(s.error instanceof Error?s.error.message:"Subscription data could not be loaded."):u.isError?(u.error instanceof Error?u.error.message:"Usage data could not be loaded."):i.error instanceof Error?i.error.message:"Invoice data could not be loaded."}</div>}
    <div className="grid grid-4">
      <Metric label="Plan" value={p.data?.name??p.data?.code??"Unavailable"}/>
      <Metric label="Subscription" value={s.data?.status??"Unavailable"}/>
      <Metric label="Billing provider" value={s.data?.provider??"Unavailable"}/>
      <Metric label="Renewal" value={s.data?.current_period_end?new Date(s.data.current_period_end).toLocaleDateString():"Not scheduled"}/>
    </div>
    <Card style={{marginTop:16}}><div className="row"><div><h3>Usage</h3><div className="muted small">Current consumption and plan limits from the workspace entitlement API.</div></div><span className="tag">{usageItems.length} metrics</span></div>
      {usageItems.length===0&&!u.isPending&&!u.isError&&<State title="No usage metrics" description="This workspace does not currently expose usage metrics."/>}
      {usageItems.length>0&&<div className="table-wrap" style={{marginTop:10}}><table className="table"><thead><tr><th>Metric</th><th>Current</th><th>Limit</th><th>Unit</th></tr></thead><tbody>{usageItems.map(item=><tr key={item.metric}><td>{item.metric}</td><td>{item.current}</td><td>{item.limit===null?"Unlimited":item.limit}</td><td>{item.unit}</td></tr>)}</tbody></table></div>}
    </Card>
    <div className="grid grid-2" style={{marginTop:16}}>
      <Card><h3>Subscription actions</h3><div className="field"><label>Plan</label><select className="input" value={code} onChange={e=>setCode(e.target.value)} disabled={changePlan.isPending||checkout.isPending}><option value="pro">Pro</option><option value="team">Team</option></select></div>
        <div className="actions" style={{marginTop:12}}>
          <button className="btn primary" onClick={()=>checkout.mutate()} disabled={!ws.workspaceId||checkout.isPending}>{checkout.isPending?"Opening…":"Open checkout"}</button>
          <button className="btn" onClick={()=>changePlan.mutate()} disabled={!ws.workspaceId||changePlan.isPending||code===s.data?.plan_code}>{changePlan.isPending?"Changing…":"Switch plan"}</button>
          {s.data?.cancel_at_period_end?<button className="btn" onClick={()=>resume.mutate()} disabled={resume.isPending}>{resume.isPending?"Resuming…":"Resume subscription"}</button>:<button className="btn" onClick={()=>cancel.mutate()} disabled={cancel.isPending}>{cancel.isPending?"Cancelling…":"Cancel at period end"}</button>}
        </div>
        {checkout.isError&&<div className="notice error" style={{marginTop:10}}>{checkout.error instanceof Error?checkout.error.message:"Checkout failed."}</div>}
        {subscriptionError&&<div className="notice error" style={{marginTop:10}}>{subscriptionError instanceof Error?subscriptionError.message:"Subscription update failed. Retry the action."}</div>}
        {checkout.data&&<div className="notice success" style={{marginTop:10}}>Checkout session created. <a href={checkout.data.checkout_url} target="_blank" rel="noreferrer">Continue to payment ↗</a></div>}
      </Card>
      <Card><h3>Invoices</h3>{i.data?.items.length===0&&!i.isPending?<State title="No invoices" description="Invoices will appear after billing activity is recorded."/>:<div className="table-wrap" style={{marginTop:10}}><table className="table"><thead><tr><th>Status</th><th>Amount</th><th>Created</th><th>Open</th></tr></thead><tbody>{i.data?.items.map(inv=><tr key={inv.id??inv.provider_invoice_id}><td>{inv.status}</td><td>{inv.amount_due===null?"—":String(inv.amount_due)+" "+(inv.currency??"")}</td><td>{inv.provider_created_at?new Date(inv.provider_created_at).toLocaleDateString():"—"}</td><td>{inv.hosted_invoice_url?<a href={inv.hosted_invoice_url} target="_blank" rel="noreferrer">Invoice ↗</a>:inv.invoice_pdf_url?<a href={inv.invoice_pdf_url} target="_blank" rel="noreferrer">PDF ↗</a>:"—"}</td></tr>)}</tbody></table></div>}</Card>
    </div>
  </>;
}
function Settings(){
  const {ws}=useCtx();
  const workspaceId=ws.workspaceId??undefined;
  const qc=useQueryClient();
  const sessions=useQuery({queryKey:["sessions"],queryFn:api.sessions});
  const tokens=useQuery({queryKey:["tokens"],queryFn:api.apiTokens});
  const tf=useQuery({queryKey:["2fa"],queryFn:api.twoFactor});
  const preferences=useQuery({queryKey:["notification-preferences",ws.workspaceId],queryFn:()=>api.notificationPreferences(workspaceId),enabled:Boolean(workspaceId)});
  const [tokenName,setTokenName]=useState("");
  const [tokenScopes,setTokenScopes]=useState("read");
  const [createdToken,setCreatedToken]=useState("");
  const [twoFaSetup,setTwoFaSetup]=useState<TwoFactorEnrollment|null>(null);
  const [twoFaCode,setTwoFaCode]=useState("");
  const [prefValues,setPrefValues]=useState<Record<string,boolean>>({});
  const [prefError,setPrefError]=useState("");

  useEffect(()=>{
    if(preferences.data) setPrefValues(preferences.data.preferences);
  },[preferences.data]);

  const revokeSession=useMutation({mutationFn:(id:string)=>api.revokeSession(id),onSuccess:()=>void qc.invalidateQueries({queryKey:["sessions"]})});
  const revokeOthers=useMutation({mutationFn:()=>api.revokeOtherSessions(),onSuccess:()=>void qc.invalidateQueries({queryKey:["sessions"]})});
  const createToken=useMutation({mutationFn:()=>api.createApiToken({name:tokenName,scopes:tokenScopes.split(",").map(x=>x.trim()).filter(Boolean)}),onSuccess:r=>{setCreatedToken(r.token);setTokenName("");void qc.invalidateQueries({queryKey:["tokens"]});}});
  const revokeToken=useMutation({mutationFn:(id:string)=>api.revokeApiToken(id),onSuccess:()=>void qc.invalidateQueries({queryKey:["tokens"]})});
  const begin2fa=useMutation({mutationFn:()=>api.beginTwoFactor(),onSuccess:setTwoFaSetup});
  const confirm2fa=useMutation({mutationFn:()=>api.confirmTwoFactor(twoFaCode),onSuccess:()=>{setTwoFaSetup(null);setTwoFaCode("");void qc.invalidateQueries({queryKey:["2fa"]});}});
  const disable2fa=useMutation({mutationFn:()=>api.disableTwoFactor(twoFaCode),onSuccess:()=>{setTwoFaCode("");void qc.invalidateQueries({queryKey:["2fa"]});}});
  const twoFaError=begin2fa.error??confirm2fa.error??disable2fa.error;
  const savePreferences=useMutation({
    mutationFn:()=>api.updateNotificationPreferences({channel:preferences.data?.channel??"in_app",preferences:prefValues},workspaceId),
    onSuccess:r=>{setPrefValues(r.preferences);setPrefError("");void qc.invalidateQueries({queryKey:["notification-preferences",ws.workspaceId]});},
    onError:e=>setPrefError(e instanceof Error?e.message:"Notification preferences could not be saved."),
  });

  const preferenceEntries=Object.entries(prefValues);
  return <><Head route="settings"/>
    <div className="grid grid-2">
      <Card id="security"><div className="row"><div><h3>Two-factor authentication</h3><div className="muted small">Protect account login with TOTP or a recovery code.</div></div><span className="tag">{tf.data?.enabled?"Enabled":"Not enabled"}</span></div>
        {!tf.data?.enabled&&!twoFaSetup&&<button className="btn primary" style={{marginTop:12}} disabled={begin2fa.isPending} onClick={()=>begin2fa.mutate()}>{begin2fa.isPending?"Preparing…":"Set up 2FA"}</button>}
        {twoFaSetup&&<div className="notice" style={{marginTop:12}}><div><b>Authenticator setup</b></div><div className="tiny" style={{marginTop:6}}>Secret: <span className="mono" style={{overflowWrap:"anywhere"}}>{twoFaSetup.secret}</span></div><div className="tiny" style={{marginTop:4}}>Provisioning URI: <span className="mono" style={{overflowWrap:"anywhere"}}>{twoFaSetup.provisioning_uri}</span></div><div className="tiny" style={{marginTop:4}}>Recovery codes: {twoFaSetup.recovery_codes.join(", ")}</div><div className="row" style={{marginTop:10}}><input className="input" aria-label="2FA confirmation code" inputMode="numeric" maxLength={6} value={twoFaCode} onChange={e=>setTwoFaCode(e.target.value.replace(/\D/g,"").slice(0,6))} placeholder="6-digit code"/><button className="btn" disabled={twoFaCode.length!==6||confirm2fa.isPending} onClick={()=>confirm2fa.mutate()}>{confirm2fa.isPending?"Confirming…":"Confirm"}</button></div></div>}
        {tf.data?.enabled&&<div className="row" style={{marginTop:12}}><input className="input" aria-label="2FA disable code" inputMode="numeric" maxLength={6} value={twoFaCode} onChange={e=>setTwoFaCode(e.target.value.replace(/\D/g,"").slice(0,6))} placeholder="6-digit code"/><button className="btn" disabled={twoFaCode.length!==6||disable2fa.isPending} onClick={()=>disable2fa.mutate()}>{disable2fa.isPending?"Disabling…":"Disable 2FA"}</button></div>}
        {twoFaError&&<div className="notice error" style={{marginTop:10}}>{twoFaError instanceof Error?twoFaError.message:"2FA operation failed."}</div>}
      </Card>
      <Card><div className="row"><div><h3>Sessions</h3><div className="muted small">Revoke access from individual sessions or all other sessions.</div></div><button className="btn" disabled={revokeOthers.isPending} onClick={()=>revokeOthers.mutate()}>{revokeOthers.isPending?"Revoking…":"Revoke others"}</button></div>
        <div className="list" style={{marginTop:10}}>{sessions.isError?<State title="Sessions unavailable" description={sessions.error instanceof Error?sessions.error.message:"Session list could not be loaded."} error/>:sessions.data?.items.map(s=><div className="list-item" key={s.id}><div className="row"><div><div className="title">{s.user_agent||"Unknown client"}</div><div className="meta">Created {new Date(s.created_at).toLocaleString()} · Expires {new Date(s.expires_at).toLocaleString()}</div></div><button className="btn" disabled={revokeSession.isPending} onClick={()=>revokeSession.mutate(s.id)}>Revoke</button></div></div>)}</div>
      </Card>
      <Card><div className="row"><div><h3>API tokens</h3><div className="muted small">The full token is revealed once at creation. Store it securely.</div></div></div>
        <div className="row" style={{marginTop:10}}><input className="input" value={tokenName} onChange={e=>setTokenName(e.target.value)} placeholder="Token name"/><input className="input" value={tokenScopes} onChange={e=>setTokenScopes(e.target.value)} placeholder="Scopes, comma separated"/><button className="btn primary" disabled={!tokenName.trim()||createToken.isPending} onClick={()=>createToken.mutate()}>{createToken.isPending?"Creating…":"Create token"}</button></div>
        {createdToken&&<div className="notice success" style={{marginTop:10}}>Copy this token now; it will not be shown again: <span className="mono" style={{overflowWrap:"anywhere"}}>{createdToken}</span></div>}
        {createToken.isError&&<div className="notice error" style={{marginTop:10}}>{createToken.error instanceof Error?createToken.error.message:"Token creation failed."}</div>}
        <div className="list" style={{marginTop:10}}>{tokens.data?.length===0&&!tokens.isPending?<State title="No API tokens" description="Create a scoped token for programmatic access."/>:tokens.data?.map(t=><div className="list-item" key={t.id}><div className="row"><div><div className="title">{t.name}</div><div className="meta">{t.token_prefix} · {t.scopes.join(", ")||"No scopes"} · {t.expires_at?new Date(t.expires_at).toLocaleDateString():"No expiry"}</div></div>{t.revoked_at?<span className="tag">Revoked</span>:<button className="btn" disabled={revokeToken.isPending} onClick={()=>revokeToken.mutate(t.id)}>Revoke</button>}</div></div>)}</div>
      </Card>
      <Card id="notifications"><div className="row"><div><h3>Notification settings</h3><div className="muted small">Workspace-scoped in-app notification preferences.</div></div><span className="tag">{preferences.data?.channel??"in_app"}</span></div>
        {preferences.isError?<State title="Notification settings unavailable" description={preferences.error instanceof Error?preferences.error.message:"Notification preferences could not be loaded."} error/>:preferences.isPending?<State title="Loading notification settings" description="Reading current notification preferences."/>:preferenceEntries.length===0?<State title="No configurable preferences" description="The workspace has no notification toggles configured."/>:<>
          <div className="list" style={{marginTop:10}}>{preferenceEntries.map(([key,enabled])=><label className="list-item row" key={key}><span><b>{key}</b><span className="muted tiny" style={{display:"block"}}>In-app notifications</span></span><input type="checkbox" checked={enabled} onChange={e=>setPrefValues(prev=>({...prev,[key]:e.target.checked}))}/></label>)}</div>
          {prefError&&<div className="notice error" style={{marginTop:10}}>{prefError}</div>}
          <button className="btn primary" style={{marginTop:10}} disabled={savePreferences.isPending} onClick={()=>savePreferences.mutate()}>{savePreferences.isPending?"Saving…":"Save notification settings"}</button>
        </>}
      </Card>
    </div>
  </>;
}
function Workspace(){
  const {ws,projects}=useCtx();
  const [name,setName]=useState("");
  const qc=useQueryClient();
  const create=useMutation({
    mutationFn:()=>api.createWorkspace(name.trim()),
    onSuccess:async workspace=>{
      setName("");
      ws.setSelected(workspace.id);
      await qc.invalidateQueries({queryKey:["workspaces"]});
    },
  });
  const current=ws.workspaces.find(w=>w.id===ws.workspaceId);
  return <><Head route="workspace" actions={<Link className="btn primary" href="/projects">Create project →</Link>}/>
    <div className="grid grid-2">
      <Card>
        <h3>Current workspace</h3>
        {current ? (
          <>
            <div className="title" style={{marginTop:10,fontSize:15}}>{current.name}</div>
            <div className="meta">{current.slug} · {current.status} · Role: {current.role}</div>
            <div className="notice" style={{marginTop:14}}>
              <b>Workspace is the tenant boundary.</b>
              <div className="muted tiny" style={{marginTop:4}}>Membership, access, usage and billing belong here. Research work belongs in projects.</div>
            </div>
          </>
        ) : <State title="No workspace selected" description="Select a workspace from the sidebar to continue."/>}
      </Card>
      <Card>
        <h3>Create workspace</h3>
        <p className="muted small">Create a separate tenant boundary for another team or research environment. Your existing projects stay in their current workspace.</p>
        <div className="row" style={{marginTop:14}}>
          <input className="input" aria-label="Workspace name" value={name} onChange={e=>setName(e.target.value)} placeholder="Workspace name"/>
          <button className="btn primary" disabled={!name.trim()||create.isPending} onClick={()=>create.mutate()}>{create.isPending?"Creating…":"Create workspace"}</button>
        </div>
        {create.isError&&<div className="notice error" style={{marginTop:10}}>{create.error instanceof Error?create.error.message:"Workspace creation failed."}</div>}
      </Card>
    </div>

    <Card style={{marginTop:16}}>
      <div className="row">
        <div><h3>Workspaces</h3><div className="muted tiny">Use the sidebar selector to switch the active workspace.</div></div>
        <span className="tag">{ws.workspaces.length} total</span>
      </div>
      <div className="list" style={{marginTop:8}}>
        {ws.workspaces.map(w=><div className="list-item" key={w.id}>
          <div className="row">
            <div style={{minWidth:0}}><div className="title" style={{overflowWrap:"anywhere"}}>{w.name}</div><div className="meta">{w.slug} · {w.status} · {w.role}</div></div>
            {w.id===ws.workspaceId?<span className="tag primary">Selected</span>:<button className="btn" onClick={()=>ws.setSelected(w.id)}>Use workspace</button>}
          </div>
        </div>)}
      </div>
    </Card>

    <Card style={{marginTop:16}}>
      <div className="row">
        <div><h3>Projects in this workspace</h3><div className="muted tiny">Projects hold the research effort; reports and sources are scoped underneath a project.</div></div>
        <Link className="btn" href="/projects">Open projects</Link>
      </div>
      <div style={{marginTop:10}}><Table data={rows(projects.data?.items)}/></div>
      {!projects.isPending&&!(projects.data?.items?.length)&&<div className="notice" style={{marginTop:12}}>No projects yet. <Link href="/projects" style={{color:"var(--primary)",fontWeight:700}}>Create the first project.</Link></div>}
    </Card>
  </>;
}

function Sources(){
  const {reportId,projectId,projects,reports}=useCtx();
  const q=useQuery({queryKey:["sources",reportId],queryFn:()=>api.sources(reportId!),enabled:Boolean(reportId)});
  const qc=useQueryClient();
  const [processingId,setProcessingId]=useState("");
  const [embeddingId,setEmbeddingId]=useState("");
  const [error,setError]=useState("");
  const [embeddingNotice,setEmbeddingNotice]=useState("");
  const process=useMutation({mutationFn:(id:string)=>api.extractSource(reportId!,id),onMutate:id=>{setProcessingId(id);setError("");},onSuccess:async()=>{await qc.invalidateQueries({queryKey:["sources",reportId]});},onError:e=>setError(e instanceof Error?e.message:"Source processing failed."),onSettled:()=>setProcessingId("")});
  const embed=useMutation({mutationFn:(id:string)=>api.embedSource(reportId!,id),onMutate:id=>{setEmbeddingId(id);setEmbeddingNotice("");setError("");},onSuccess:result=>{setEmbeddingNotice("Embedding complete: "+result.embedded+" new chunks, "+result.already_current+" already current, "+result.failed+" failed, "+result.pending+" pending.");},onError:e=>setError(e instanceof Error?e.message:"Embedding failed. Check provider configuration and retry."),onSettled:()=>setEmbeddingId("")});
  return <><Head route="sources" actions={<Link className="btn primary" href={reportId?"/research?projectId="+encodeURIComponent(projectId??"")+"&reportId="+encodeURIComponent(reportId):"/research"}>Discover sources</Link>}/>
    <WorkflowContext route="sources" projectId={projectId} reportId={reportId} projects={projects} reports={reports}/>
    {!reportId&&<Card><State title="No active report" description="Create a project report before managing the source library."/></Card>}
    {reportId&&<Card><div className="row"><div><h3>Source library</h3><div className="muted small">Saved sources are metadata-only until processing creates chunks; semantic retrieval also requires current-profile embeddings.</div></div><span className="tag">{q.data?.items.length??0} sources</span></div>
      {error&&<div className="notice error" style={{marginTop:12}}>{error}</div>}
      {embeddingNotice&&<div className="notice success" style={{marginTop:12}}>{embeddingNotice}</div>}
      {(q.data?.items??[]).length===0&&!q.isPending&&<State title="Source library is empty" description="Use Research discovery to find and save provider-backed candidates."/>}
      {(q.data?.items??[]).length>0&&<div className="table-wrap" style={{marginTop:12}}><table className="table"><thead><tr><th>Source</th><th>Year</th><th>Processing</th><th>Links</th><th>Actions</th></tr></thead><tbody>{q.data?.items.map(source=>{
        const processing=processingId===source.id;const embedding=embeddingId===source.id;const doi=source.doi?("https://doi.org/"+source.doi.replace(/^doi:\s*/i,"")):null;
        return <tr key={source.id}><td><div className="strong" style={{whiteSpace:"normal",overflowWrap:"anywhere",maxWidth:430}}>{source.title}</div><div className="meta">{(source.authors??[]).slice(0,3).join(", ")||"Authors unavailable"}</div></td>
          <td>{source.year??"—"}</td><td>{source.status}</td><td><div className="actions">{source.url&&<a className="btn" href={source.url} target="_blank" rel="noreferrer">Article ↗</a>}{doi&&<a className="btn" href={doi} target="_blank" rel="noreferrer">DOI ↗</a>}</div></td>
          <td><div className="actions"><button className="btn" disabled={processing||embedding} onClick={()=>process.mutate(source.id)}>{processing?"Processing…":source.status==="full_text"||source.status==="structured_full_text"?"Re-process":"Process source"}</button><button className="btn" disabled={embedding||processing||source.status==="metadata_only"} onClick={()=>embed.mutate(source.id)}>{embedding?"Embedding…":"Embed source"}</button></div></td>
        </tr>;})}</tbody></table></div>}
    </Card>}
  </>;
}
function Literature(){
  const {projectId}=useCtx();
  const q=useQuery({queryKey:["literature",projectId],queryFn:()=>api.literature(projectId!),enabled:Boolean(projectId)});
  const clusters=useQuery({queryKey:["literature-clusters",projectId],queryFn:()=>api.literatureClusters(projectId!),enabled:Boolean(projectId)});
  const gaps=useQuery({queryKey:["literature-gaps",projectId],queryFn:()=>api.literatureGaps(projectId!),enabled:Boolean(projectId)});
  const runs=useQuery({queryKey:["literature-runs",projectId],queryFn:()=>api.literatureRuns(projectId!),enabled:Boolean(projectId)});
  const qc=useQueryClient();
  const [analysisNotice,setAnalysisNotice]=useState("");
  const analyze=useMutation({mutationFn:()=>api.literatureAnalyze(projectId!,true),onSuccess:async result=>{setAnalysisNotice(result.status==="queued"?"Analysis queued.":"Analysis completed.");await Promise.all([qc.invalidateQueries({queryKey:["literature",projectId]}),qc.invalidateQueries({queryKey:["literature-clusters",projectId]}),qc.invalidateQueries({queryKey:["literature-gaps",projectId]}),qc.invalidateQueries({queryKey:["literature-runs",projectId]})])}});
  const screening=useMutation({mutationFn:(x:{id:string;status:"discovered"|"candidate"|"included"|"excluded"|"uncertain"})=>api.updateLiteratureItem(projectId!,x.id,{screening_status:x.status}),onSuccess:()=>qc.invalidateQueries({queryKey:["literature",projectId]})});
  const items=q.data?.items??[];const clusterItems=clusters.data?.items??[];const gapItems=gaps.data?.items??[];
  const themes=clusterItems.reduce((count,item)=>count+(item.themes?.length??0),0);
  return <><Head route="literature" actions={<button className="btn primary" disabled={!projectId||analyze.isPending} onClick={()=>analyze.mutate()}>{analyze.isPending?"Analyzing…":"Analyze literature"}</button>}/>
    {!projectId&&<Card><State title="No active project" description="Create a project before running literature intelligence."/></Card>}
    {projectId&&<div className="grid grid-4"><Metric label="Literature items" value={q.isPending?"…":items.length}/><Metric label="Clusters" value={clusters.isPending?"…":clusterItems.length}/><Metric label="Themes" value={themes}/><Metric label="Gaps" value={gaps.isPending?"…":gapItems.length}/></div>}
    {analysisNotice&&<div className="notice" style={{marginTop:16}}>{analysisNotice}</div>}
    {analyze.isError&&<div className="notice error" style={{marginTop:16}}>{analyze.error instanceof Error?analyze.error.message:"Literature analysis failed. Retry the analysis run."}</div>}
    <div className="grid grid-2" style={{marginTop:16}}>
      <Card><div className="row"><div><h3>Literature corpus</h3><div className="muted small">Screen papers and inspect structured analysis state.</div></div><span className="tag">{items.length}</span></div>
        {q.isError?<State title="Literature unavailable" description={q.error instanceof Error?q.error.message:"The literature corpus could not be loaded."} error/>:q.isPending?<State title="Loading literature" description="Reading the project literature corpus."/>:items.length===0?<State title="No literature items yet" description="Save sources first, then run Analyze literature."/>:<div className="table-wrap" style={{marginTop:10}}><table className="table"><thead><tr><th>Source</th><th>Relevance</th><th>Screening</th><th>Analysis</th></tr></thead><tbody>{items.map(item=><tr key={item.id}><td style={{overflowWrap:"anywhere"}}>{item.source_id}</td><td>{item.relevance_score===null?"Unavailable":Math.round(item.relevance_score*100)+"%"}</td><td><select className="input" value={item.screening_status} disabled={screening.isPending} onChange={e=>{const status=e.target.value;if(status==="discovered"||status==="candidate"||status==="included"||status==="excluded"||status==="uncertain")screening.mutate({id:item.id,status});}}><option value="discovered">Discovered</option><option value="candidate">Candidate</option><option value="included">Included</option><option value="excluded">Excluded</option><option value="uncertain">Uncertain</option></select></td><td>{item.analysis_status}</td></tr>)}</tbody></table></div>}
      </Card>
      <Card><div className="row"><div><h3>Analysis runs</h3><div className="muted small">Persistent runs provide history and failure state.</div></div><span className="tag">{runs.data?.total??0}</span></div>
        {runs.isError?<State title="Run history unavailable" description={runs.error instanceof Error?runs.error.message:"Analysis run history could not be loaded."} error/>:runs.data?.items.length===0&&!runs.isPending?<State title="No analysis runs" description="Run Analyze literature to build clusters, themes and gaps."/>:runs.data?.items.map(run=><div className="list-item" key={run.id}><div className="row"><div><div className="title">{run.status}</div><div className="meta">{run.source_count} sources · {run.cluster_count} clusters · {run.gap_count} gaps · {new Date(run.created_at).toLocaleString()}</div></div>{run.error_message&&<span className="tag">{run.error_message}</span>}</div></div>)}
      </Card>
    </div>
    <div className="grid grid-2" style={{marginTop:16}}>
      <Card><h3>Clusters & themes</h3>{clusterItems.length===0&&!clusters.isPending?<State title="No clusters yet" description="Run literature analysis after adding sources."/>:<div className="list">{clusterItems.map(c=><div className="list-item" key={c.id}><div className="title">{c.name}</div><div className="meta">{c.source_count} sources · {(c.themes??[]).join(", ")||"No themes extracted"}</div><div className="muted tiny" style={{marginTop:4}}>{c.summary??"No cluster summary."}</div></div>)}</div>}</Card>
      <Card><h3>Research gaps</h3>{gapItems.length===0&&!gaps.isPending?<State title="No gaps yet" description="Run literature analysis to detect gaps from the current corpus."/>:<div className="list">{gapItems.map(g=><div className="list-item" key={g.id}><div className="row"><div className="title" style={{overflowWrap:"anywhere"}}>{g.title}</div><span className="tag">{Math.round(g.confidence*100)}%</span></div><div className="muted small" style={{marginTop:4}}>{g.description}</div></div>)}</div>}</Card>
    </div>
  </>;
}
function Evidence(){
  const {reportId}=useCtx();
  const matrix=useQuery({queryKey:["evidence",reportId],queryFn:()=>api.evidenceMatrix(reportId!),enabled:Boolean(reportId)});
  const manuscript=useQuery({queryKey:["evidence-manuscript",reportId],queryFn:()=>api.manuscript(reportId!),enabled:Boolean(reportId)});
  const citations=useQuery({queryKey:["evidence-citations",reportId],queryFn:()=>api.citations(reportId!),enabled:Boolean(reportId)});
  const sources=useQuery({queryKey:["evidence-sources",reportId],queryFn:()=>api.sources(reportId!),enabled:Boolean(reportId)});
  const qc=useQueryClient();
  const [claimText,setClaimText]=useState("");
  const [claimType,setClaimType]=useState("background");
  const [sectionId,setSectionId]=useState("");
  const [evidenceType,setEvidenceType]=useState("m28_evidence");
  const [evidenceId,setEvidenceId]=useState("");
  const [sourceId,setSourceId]=useState("");
  const [supportLevel,setSupportLevel]=useState("supports");
  const [relevance,setRelevance]=useState("0.8");
  const [error,setError]=useState("");

  const claims=matrix.data??[];
  const createClaim=useMutation({
    mutationFn:()=>api.createEvidenceClaim(reportId!,{
      citation_run_id:citations.data!.run.id,
      manuscript_version_id:manuscript.data!.version.id,
      manuscript_section_id:sectionId||null,
      claim_text:claimText.trim(),
      claim_type:claimType,
      location:null,
    }),
    onSuccess:async()=>{setClaimText("");setError("");await qc.invalidateQueries({queryKey:["evidence",reportId]});},
    onError:e=>setError(e instanceof Error?e.message:"Claim creation failed."),
  });
  const link=useMutation({
    mutationFn:(claimId:string)=>api.linkEvidence(reportId!,claimId,{
      evidence_type:evidenceType,
      evidence_id:evidenceId.trim(),
      source_id:sourceId||null,
      support_level:supportLevel,
      relevance_score:Math.max(0,Math.min(1,Number(relevance)||0)),
      provenance:{ui:"evidence-matrix"},
    }),
    onSuccess:async()=>{setEvidenceId("");setSourceId("");setError("");await qc.invalidateQueries({queryKey:["evidence",reportId]});},
    onError:e=>setError(e instanceof Error?e.message:"Evidence link failed."),
  });
  const unlink=useMutation({
    mutationFn:(x:{claimId:string;linkId:string})=>api.unlinkEvidence(reportId!,x.claimId,x.linkId),
    onSuccess:async()=>{setError("");await qc.invalidateQueries({queryKey:["evidence",reportId]});},
    onError:e=>setError(e instanceof Error?e.message:"Evidence unlink failed."),
  });

  const canCreate=Boolean(reportId&&claimText.trim()&&manuscript.data?.version.id&&citations.data?.run.id&&!createClaim.isPending);
  const canLink=Boolean(reportId&&evidenceId.trim()&&claims.length&&!link.isPending);
  return <><Head route="evidence" actions={<Link className="btn" href={reportId?"/generate?reportId="+reportId:"/generate"}>Use in generation</Link>}/>
    {error&&<div className="notice error" style={{marginTop:12}}>{error}</div>}
    {!reportId&&<Card><State title="No active report" description="Evidence is scoped to a report."/></Card>}
    {reportId&&matrix.isError&&<Card><State title="Evidence unavailable" description={matrix.error instanceof Error?matrix.error.message:"The evidence service returned an error."} error/></Card>}
    {reportId&&<div className="grid grid-2" style={{marginTop:16}}>
      <Card>
        <h3>Create claim</h3>
        <p className="muted small">Claims are attached to the current manuscript version and active citation run.</p>
        {!manuscript.data||!citations.data?<State title="Preparing claim context" description="Loading the current manuscript version and citation run."/>:<>
          <div className="field" style={{marginTop:10}}><label>Claim text</label><textarea className="input textarea" value={claimText} onChange={e=>setClaimText(e.target.value)} placeholder="State the evidence-bearing claim precisely."/></div>
          <div className="grid grid-2" style={{marginTop:10}}>
            <div className="field"><label>Claim type</label><select className="input" value={claimType} onChange={e=>setClaimType(e.target.value)}>
              {["background","definition","method","result","comparison","causal","limitation","synthesis","conclusion","technical"].map(t=><option key={t} value={t}>{t}</option>)}
            </select></div>
            <div className="field"><label>Manuscript section</label><select className="input" value={sectionId} onChange={e=>setSectionId(e.target.value)}><option value="">Not specified</option>{manuscript.data.sections.map(s=><option key={s.id} value={s.id}>{s.title}</option>)}</select></div>
          </div>
          <button className="btn primary" style={{marginTop:12}} disabled={!canCreate} onClick={()=>createClaim.mutate()}>{createClaim.isPending?"Creating…":"Create claim"}</button>
        </>}
      </Card>

      <Card>
        <h3>Link evidence</h3>
        <p className="muted small">Use a durable evidence record ID; optionally bind the record to a source in this report.</p>
        {claims.length===0?<State title="Create a claim first" description="The claim list must contain a target before evidence can be linked."/>:<>
          <div className="notice" style={{marginTop:10}}>Use “Link evidence to this claim” under the target claim below.</div>
          <div className="grid grid-2" style={{marginTop:10}}>
            <div className="field"><label>Evidence type</label><select className="input" value={evidenceType} onChange={e=>setEvidenceType(e.target.value)}>{["m28_evidence","m29_technical_fact","m29_experiment_result","m29_metric"].map(t=><option key={t} value={t}>{t}</option>)}</select></div>
            <div className="field"><label>Evidence record UUID</label><input className="input" value={evidenceId} onChange={e=>setEvidenceId(e.target.value)} placeholder="UUID"/></div>
          </div>
          <div className="grid grid-2" style={{marginTop:10}}>
            <div className="field"><label>Source (optional)</label><select className="input" value={sourceId} onChange={e=>setSourceId(e.target.value)}><option value="">No source</option>{sources.data?.items.map(s=><option key={s.id} value={s.id}>{s.title}</option>)}</select></div>
            <div className="field"><label>Support</label><select className="input" value={supportLevel} onChange={e=>setSupportLevel(e.target.value)}>{["supports","partially_supports","contradicts","context_only"].map(t=><option key={t} value={t}>{t}</option>)}</select></div>
          </div>
          <div className="field" style={{marginTop:10}}><label>Relevance (0–1)</label><input className="input" type="number" min={0} max={1} step={0.05} value={relevance} onChange={e=>setRelevance(e.target.value)}/></div>
          <div className="muted tiny" style={{marginTop:8}}>Click “Link” on the claim you want to update; the same evidence tuple is idempotent.</div>
          <div className="list" style={{marginTop:10}}>{claims.map(item=><div className="list-item" key={item.claim.id}>
            <div className="row"><div className="title" style={{overflowWrap:"anywhere"}}>{item.claim.claim_text}</div><span className="tag">{item.evidence.length} linked</span></div>
            <div className="meta">{item.claim.claim_type} · {item.claim.status}</div>
            <button className="btn" style={{marginTop:8}} disabled={!canLink||link.isPending} onClick={()=>link.mutate(item.claim.id)}>{link.isPending?"Linking…":"Link evidence to this claim"}</button>
            {item.evidence.length>0&&<div className="list" style={{marginTop:8}}>{item.evidence.map(ev=><div className="notice" key={ev.id}><div className="row"><span><b>{ev.support_level}</b> · {Math.round(ev.relevance_score*100)}% relevance</span><button className="btn" disabled={unlink.isPending} onClick={()=>unlink.mutate({claimId:item.claim.id,linkId:ev.id})}>Remove</button></div><div className="muted tiny" style={{marginTop:4}}>{ev.evidence_type} · {ev.evidence_id}{ev.source_id?" · Source "+ev.source_id:""}</div></div>)}</div>}
          </div>)}</div>
        </>}
      </Card>
    </div>}
    {reportId&&<Card style={{marginTop:16}}>
      <div className="row"><div><h3>Evidence matrix</h3><div className="muted small">Persistent claim-to-evidence relationships, including support level and provenance.</div></div><span className="tag">{claims.length} claims</span></div>
      {matrix.isPending?<State title="Loading evidence" description="Reading claim-to-source support from the selected report."/>:claims.length===0?<State title="No evidence claims yet" description="Create the first claim above, then link supporting or conflicting evidence."/>:<div className="table-wrap" style={{marginTop:10}}><table className="table"><thead><tr><th>Claim</th><th>Links</th><th>Status</th><th>Created</th></tr></thead><tbody>{claims.map(item=><tr key={item.claim.id}><td style={{maxWidth:560,whiteSpace:"normal",overflowWrap:"anywhere"}}>{item.claim.claim_text}</td><td>{item.evidence.length}</td><td>{item.claim.status}</td><td>{new Date(item.claim.created_at).toLocaleString()}</td></tr>)}</tbody></table></div>}
    </Card>}
  </>;
}
function RAG(){
  const {projectId,reportId,projects,reports}=useCtx();
  const readiness=useQuery({queryKey:["rag-readiness",projectId],queryFn:()=>api.ragReadiness(projectId!),enabled:Boolean(projectId),refetchInterval:5000});
  const runs=useQuery({queryKey:["rag-runs",projectId],queryFn:()=>api.ragRuns(projectId!,25,0),enabled:Boolean(projectId),refetchInterval:5000});
  const [query,setQuery]=useState("");
  const [mode,setMode]=useState<"lexical"|"semantic"|"hybrid">("hybrid");
  const [maxResults,setMaxResults]=useState(10);
  const [result,setResult]=useState<RAGResponse|null>(null);
  const [selectedRunId,setSelectedRunId]=useState("");
  const qc=useQueryClient();
  const selectedRun=useQuery({queryKey:["rag-run",projectId,selectedRunId],queryFn:()=>api.ragRun(projectId!,selectedRunId),enabled:Boolean(projectId&&selectedRunId)});
  const retrieve=useMutation({
    mutationFn:()=>api.ragRetrieve(projectId!,{query:query.trim(),mode,max_results:maxResults,report_id:reportId??undefined,async:false}),
    onSuccess:async response=>{
      setResult(response);
      setSelectedRunId(response.run?.id??"");
      await qc.invalidateQueries({queryKey:["rag-runs",projectId]});
    }
  });
  useEffect(()=>{if(selectedRun.data)setResult(selectedRun.data);},[selectedRun.data]);
  function setSelectedMode(next:string){if(next==="lexical"||next==="semantic"||next==="hybrid")setMode(next);}
  return <><Head route="rag"/>
    <WorkflowContext route="rag" projectId={projectId} reportId={reportId} projects={projects} reports={reports}/>
    {!projectId&&<Card><State title="No active project" description="Create a project before running retrieval."/></Card>}
    {projectId&&readiness.isError&&<Card><State title="Retrieval readiness unavailable" description={readiness.error instanceof Error?readiness.error.message:"The retrieval readiness service could not be reached."} error/></Card>}
    {projectId&&readiness.data&&<Card><div className="row"><div><h3>Retrieval readiness</h3><div className="muted small">Processed sources support lexical retrieval. Semantic and hybrid retrieval require current-profile embeddings.</div></div><span className="tag">{readiness.data.status}</span></div>
      <div className="grid grid-4" style={{marginTop:12}}><Metric label="Saved" value={readiness.data.saved_sources}/><Metric label="Processed" value={readiness.data.processed_sources}/><Metric label="Embedded" value={readiness.data.embedded_sources}/><Metric label="Semantic-ready" value={readiness.data.semantic_ready_sources}/></div>
      {readiness.data.reason&&<div className="notice" style={{marginTop:12}}>{readiness.data.reason}</div>}
    </Card>}
    {projectId&&<Card style={{marginTop:16}}><div className="grid grid-3">
      <div className="field"><label>Retrieval query</label><input className="input" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Ask about the research corpus…"/></div>
      <div className="field"><label>Mode</label><select className="input" value={mode} onChange={e=>setSelectedMode(e.target.value)}><option value="lexical">Lexical</option><option value="semantic">Semantic</option><option value="hybrid">Hybrid</option></select></div>
      <div className="field"><label>Maximum results</label><input className="input" type="number" min={1} max={200} value={maxResults} onChange={e=>setMaxResults(Math.max(1,Math.min(200,Number(e.target.value)||1)))}/></div>
    </div>
    <button className="btn primary" style={{marginTop:12}} disabled={!query.trim()||retrieve.isPending} onClick={()=>retrieve.mutate()}>{retrieve.isPending?"Retrieving…":"Run retrieval"}</button>
    {retrieve.isError&&<div className="notice error" style={{marginTop:12}}>{retrieve.error instanceof Error?retrieve.error.message:"Retrieval failed. Check the readiness state and retry."}</div>}
    {result?.status==="queued"&&<div className="notice" style={{marginTop:12}}>Retrieval queued. Job <span className="mono">{result.job_id}</span> is processing.</div>}
    {selectedRun.isError&&<div className="notice error" style={{marginTop:12}}>{selectedRun.error instanceof Error?selectedRun.error.message:"Saved retrieval run could not be loaded."}</div>}
    {result&&result.status!=="queued"&&result.results.length===0&&<State title="No retrieval results" description="No source-backed chunks matched this query and mode. Process more sources or switch retrieval mode."/>}
    {result&&result.results.length>0&&<div className="table-wrap" style={{marginTop:12}}><table className="table"><thead><tr><th>Rank</th><th>Source</th><th>Score</th><th>Stage</th><th>Reason</th></tr></thead><tbody>{result.results.map(item=><tr key={item.rank}><td>{item.rank}</td><td className="mono">{item.source_id??"Unavailable"}</td><td>{item.final_score.toFixed(3)}</td><td>{item.retrieval_stage}</td><td style={{overflowWrap:"anywhere"}}>{item.retrieval_reason.join(", ")||"Ranked by retrieval score."}</td></tr>)}</tbody></table></div>}
    </Card>}
    {projectId&&<Card style={{marginTop:16}}><div className="row"><div><h3>Retrieval history</h3><div className="muted small">Persisted retrieval runs for this project. Selecting one reloads its stored results.</div></div><span className="tag">{runs.data?.total??0} runs</span></div>
      {runs.isError?<State title="Run history unavailable" description={runs.error instanceof Error?runs.error.message:"Retrieval history could not be loaded."} error/>:runs.isPending?<State title="Loading retrieval history" description="Reading persisted retrieval runs."/>:runs.data?.items.length===0?<State title="No retrieval runs" description="Completed retrieval requests will appear here."/>:<div className="list" style={{marginTop:10}}>{runs.data.items.map(run=><button className="list-item" style={{textAlign:"left",width:"100%",cursor:"pointer",background:run.id===selectedRunId?"var(--surface)":"transparent"}} key={run.id} onClick={()=>setSelectedRunId(run.id)}><div className="row"><div><div className="title">{run.query}</div><div className="meta">{run.status} · {run.final_result_count} results · {new Date(run.started_at).toLocaleString()}</div></div><span className="tag">{run.duration_ms===null?"Duration —":run.duration_ms+" ms"}</span></div></button>)}</div>}
    </Card>}
  </>;
}
function Knowledge(){
  const {projectId}=useCtx();
  const summary=useQuery({queryKey:["kg-summary",projectId],queryFn:()=>api.knowledgeGraphSummary(projectId!),enabled:Boolean(projectId)});
  const [search,setSearch]=useState("");
  const [nodeType,setNodeType]=useState("");
  const nodes=useQuery({queryKey:["kg-nodes",projectId,search,nodeType],queryFn:()=>api.knowledgeGraphNodes(projectId!,search,nodeType,100,0),enabled:Boolean(projectId)});
  const [selectedId,setSelectedId]=useState("");
  const neighbors=useQuery({queryKey:["kg-neighbors",projectId,selectedId],queryFn:()=>api.knowledgeGraphNeighbors(projectId!,selectedId),enabled:Boolean(projectId&&selectedId)});
  const query=useMutation({mutationFn:(payload:{start_node_id:string;max_depth:number;max_nodes:number})=>api.knowledgeGraphQuery(projectId!,payload)});
  const [depth,setDepth]=useState(2);
  const [nodeCap,setNodeCap]=useState(100);
  const [exportError,setExportError]=useState("");
  const ex=useMutation({mutationFn:(f:"json"|"csv")=>api.knowledgeGraphExport(projectId!,f),onError:e=>setExportError(e instanceof Error?e.message:"Knowledge graph export failed. Retry.")});
  async function exportGraph(format:"json"|"csv"){try{const blob=await ex.mutateAsync(format);const url=URL.createObjectURL(blob);const link=document.createElement("a");link.href=url;link.download="knowledge-graph-"+projectId+"."+format;document.body.appendChild(link);link.click();link.remove();window.setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(e){setExportError(e instanceof Error?e.message:"Knowledge graph export failed. Retry.");}}
  const nodeTypes=Object.keys(summary.data?.node_type_counts??{});
  return <><Head route="knowledge" actions={<><button className="btn" disabled={!projectId||ex.isPending} onClick={()=>void exportGraph("json")}>{ex.isPending?"Exporting…":"Export JSON"}</button><button className="btn" disabled={!projectId||ex.isPending} onClick={()=>void exportGraph("csv")}>Export CSV</button></>}/>
    {!projectId&&<Card><State title="No active project" description="Create a project before inspecting the knowledge graph."/></Card>}
    {exportError&&<div className="notice error" style={{marginTop:12}}>{exportError}</div>}
    {projectId&&summary.isError&&<Card><State title="Knowledge graph unavailable" description={summary.error instanceof Error?summary.error.message:"No ready knowledge graph is available. Generate the graph after literature and planning inputs are ready."} error/></Card>}
    {projectId&&summary.data&&<><div className="grid grid-4"><Metric label="Nodes" value={summary.data.node_count}/><Metric label="Edges" value={summary.data.edge_count}/><Metric label="Node types" value={nodeTypes.length}/><Metric label="Version" value={summary.data.version}/></div>
      <Card style={{marginTop:16}}><div className="grid grid-2"><div className="field"><label>Search nodes</label><input className="input" value={search} onChange={e=>setSearch(e.target.value)} placeholder="label or node key"/></div><div className="field"><label>Node type</label><select className="input" value={nodeType} onChange={e=>setNodeType(e.target.value)}><option value="">All types</option>{nodeTypes.map(t=><option key={t} value={t}>{t} ({summary.data.node_type_counts[t]})</option>)}</select></div></div>
        {nodes.isPending?<State title="Loading nodes" description="Reading the active graph version."/>:nodes.isError?<State title="Nodes unavailable" description={nodes.error instanceof Error?nodes.error.message:"The node list could not be loaded."} error/>:nodes.data?.items.length===0?<State title="No nodes match" description="Try a broader search or another node type."/>:<div className="table-wrap" style={{marginTop:12}}><table className="table"><thead><tr><th>Type</th><th>Label</th><th>Entity</th></tr></thead><tbody>{nodes.data?.items.map(node=><tr key={node.id} onClick={()=>setSelectedId(node.id)} style={{cursor:"pointer"}}><td>{node.node_type}</td><td style={{overflowWrap:"anywhere"}}>{node.label||node.node_key}</td><td className="mono">{node.entity_id}</td></tr>)}</tbody></table></div>}
      </Card>
      <Card style={{marginTop:16}}>{!selectedId?<State title="Select a node" description="Choose a row above to inspect connected relationships and bounded traversal."/>:neighbors.isPending?<State title="Loading neighbors" description="Reading graph relationships."/>:neighbors.isError?<State title="Neighbor lookup failed" description={neighbors.error instanceof Error?neighbors.error.message:"The selected node relationships could not be loaded."} error/>:neighbors.data?.length===0?<State title="No neighbors" description="This node has no connected relationships."/>:<div><h3>Neighbors</h3><div className="list" style={{marginTop:10}}>{neighbors.data.map(n=><div className="list-item" key={n.edge_id}><div className="row"><div><div className="title">{n.neighbor.label||n.neighbor.node_key}</div><div className="meta">{n.direction} · {n.relation_type} · {n.provenance_type}</div></div><span className="tag">{n.confidence===null?"Confidence unavailable":Math.round(n.confidence*100)+"%"}</span></div></div>)}</div></div>}</Card>
      {selectedId&&neighbors.data&&neighbors.data.length>0&&<><Card style={{marginTop:16}}><div className="row"><div><h3>Graph view</h3><div className="muted small">Interactive local neighborhood for the selected node. Click a node to inspect its neighbors.</div></div><span className="tag">{Math.min(neighbors.data.length,12)} neighbors</span></div>
        <div style={{overflowX:"auto",marginTop:12}}>
          <svg role="img" aria-label="Knowledge graph local neighborhood" viewBox="0 0 720 360" width="100%" height="360" style={{minWidth:560,border:"1px solid var(--border)",borderRadius:12,background:"var(--surface)"}}>
            {neighbors.data.slice(0,12).map((edge,index)=>{
              const angle=(Math.PI*2*index)/Math.max(1,Math.min(12,neighbors.data.length));
              const cx=360+Math.cos(angle)*230;
              const cy=180+Math.sin(angle)*120;
              return <line key={"edge-"+edge.edge_id} x1="360" y1="180" x2={cx} y2={cy} stroke="currentColor" strokeOpacity="0.25"/>;
            })}
            <g>
              <circle cx="360" cy="180" r="42" fill="var(--primary)" opacity="0.14" stroke="var(--primary)"/>
              <text x="360" y="176" textAnchor="middle" fontSize="11" fontWeight="700">Selected</text>
              <text x="360" y="193" textAnchor="middle" fontSize="8">{selectedId.slice(0,8)}…</text>
            </g>
            {neighbors.data.slice(0,12).map((edge,index)=>{
              const angle=(Math.PI*2*index)/Math.max(1,Math.min(12,neighbors.data.length));
              const cx=360+Math.cos(angle)*230;
              const cy=180+Math.sin(angle)*120;
              const label=(edge.neighbor.label||edge.neighbor.node_key||"Node").slice(0,28);
              return <g key={edge.edge_id} role="button" tabIndex={0} onClick={()=>setSelectedId(edge.neighbor.id)} onKeyDown={event=>{if(event.key==="Enter"||event.key===" ")setSelectedId(edge.neighbor.id);}} style={{cursor:"pointer"}}>
                <circle cx={cx} cy={cy} r="30" fill="var(--surface)" stroke="var(--border)"/>
                <text x={cx} y={cy-2} textAnchor="middle" fontSize="8" fontWeight="600">{label}</text>
                <text x={cx} y={cy+11} textAnchor="middle" fontSize="7" opacity="0.65">{edge.relation_type.slice(0,20)}</text>
              </g>;
            })}
          </svg>
        </div>
      </Card> 
      <Card style={{marginTop:16}}><div className="row"><div><h3>Bounded query</h3><div className="muted small">Traverse from the selected node without exceeding the configured depth/node limits.</div></div>{query.data&&<span className="tag">{query.data.nodes.length} nodes · {query.data.edges.length} edges</span>}</div>
        {!selectedId?<State title="Select a start node" description="Select a node above, then run a bounded graph query."/>:<div className="row" style={{marginTop:12}}><div className="field"><label>Max depth</label><input className="input" type="number" min={1} max={10} value={depth} onChange={e=>setDepth(Math.max(1,Math.min(10,Number(e.target.value)||1)))}/></div><div className="field"><label>Max nodes</label><input className="input" type="number" min={1} max={10000} value={nodeCap} onChange={e=>setNodeCap(Math.max(1,Math.min(10000,Number(e.target.value)||1)))}/></div><button className="btn primary" style={{marginTop:24}} disabled={query.isPending} onClick={()=>query.mutate({start_node_id:selectedId,max_depth:depth,max_nodes:nodeCap})}>{query.isPending?"Querying…":"Run query"}</button></div>}
        {query.isError&&<div className="notice error" style={{marginTop:12}}>{query.error instanceof Error?query.error.message:"Graph query failed. Retry the traversal."}</div>}
        {query.data&&<div className="table-wrap" style={{marginTop:12}}><table className="table"><thead><tr><th>Node</th><th>Type</th><th>Depth</th></tr></thead><tbody>{query.data.nodes.slice(0,100).map((node,index)=><tr key={String(node.id??index)}><td style={{overflowWrap:"anywhere"}}>{value(node.label??node.node_key??node.id,"Node")}</td><td>{value(node.node_type)}</td><td>{value(node.depth)}</td></tr>)}</tbody></table></div>}
      </Card>
    </>}
  </>}
  </>;
}

// File/folder controls are kept in a separate component to isolate mutations.
function FolderTools({projectId,folders,onChanged}:{projectId:string|undefined;folders:FileFolder[];onChanged:()=>void}){
  const [name,setName]=useState("");const [error,setError]=useState("");const [busyId,setBusyId]=useState("");
  const create=useMutation({mutationFn:()=>api.createFolder(projectId!,{name}),onSuccess:()=>{setName("");setError("");onChanged();},onError:e=>setError(e instanceof Error?e.message:"Folder creation failed.")});
  async function rename(id:string,current:string){const next=window.prompt("Folder name",current)?.trim();if(!next||next===current)return;setBusyId(id);setError("");try{await api.updateFolder(projectId!,id,{name:next});onChanged();}catch(e){setError(e instanceof Error?e.message:"Folder rename failed.");}finally{setBusyId("");}}
  async function remove(id:string,current:string){if(!window.confirm(`Delete empty folder "${current}"?`))return;setBusyId(id);setError("");try{await api.deleteFolder(projectId!,id);onChanged();}catch(e){setError(e instanceof Error?e.message:"Folder deletion failed.");}finally{setBusyId("");}}
  return <div><div className="row" style={{marginTop:10}}><input className="input" value={name} onChange={e=>setName(e.target.value)} placeholder="New folder name"/><button className="btn" disabled={!projectId||!name.trim()||create.isPending} onClick={()=>create.mutate()}>{create.isPending?"Creating…":"Create"}</button></div>{error&&<div className="notice error" style={{marginTop:8}}>{error}</div>}<div className="list" style={{marginTop:10}}>{folders.map(folder=><div className="list-item" key={folder.id}><div className="row"><span style={{overflowWrap:"anywhere"}}>{folder.name}</span><span className="actions"><button className="btn" disabled={busyId===folder.id} onClick={()=>void rename(folder.id,folder.name)}>Rename</button><button className="btn" disabled={busyId===folder.id} onClick={()=>void remove(folder.id,folder.name)}>Delete</button></span></div></div>)}</div></div>;
}

function Files(){
  const {projectId}=useCtx();
  const q=useQuery({queryKey:["files",projectId],queryFn:()=>api.files(projectId!),enabled:Boolean(projectId),refetchInterval:5000});
  const folders=useQuery({queryKey:["folders",projectId],queryFn:()=>api.folders(projectId!),enabled:Boolean(projectId)});
  const qc=useQueryClient();
  const inputRef=useRef<HTMLInputElement>(null);
  const [folderId,setFolderId]=useState("");
  const [uploading,setUploading]=useState(false);
  const [uploadProgress,setUploadProgress]=useState(0);
  const [uploadName,setUploadName]=useState("");
  const [busyId,setBusyId]=useState("");
  const [error,setError]=useState("");
  const [uploadNotice,setUploadNotice]=useState("");
  const [retryFile,setRetryFile]=useState<File|null>(null);
  const [retryFolderId,setRetryFolderId]=useState<string|undefined>(undefined);
  const uploadAbortRef=useRef<AbortController|null>(null);

  async function upload(file:File,selectedFolderId=folderId){
    if(!projectId)return;
    if(file.size===0){
      setError("The selected file is empty. Choose a non-empty research file.");
      setRetryFile(null);
      return;
    }

    setError("");
    setUploadNotice("");
    setRetryFile(null);
    setRetryFolderId(undefined);
    setUploadName(file.name);
    setUploadProgress(0);
    setUploading(true);

    const controller=new AbortController();
    uploadAbortRef.current=controller;

    try{
      await api.uploadFile(projectId,file,{
        folderId:selectedFolderId||undefined,
        signal:controller.signal,
        onProgress:progress=>setUploadProgress(progress.percent),
      });
      setUploadProgress(100);
      setUploadNotice(`Uploaded "${file.name}". Processing continues in the background.`);
      await qc.invalidateQueries({queryKey:["files",projectId]});
    }catch(e){
      if(e instanceof Error&&e.name==="UploadCancelledError"){
        setUploadNotice(`Upload of "${file.name}" was cancelled.`);
      }else{
        setError(e instanceof Error?e.message:"Upload failed. Retry the file.");
        setRetryFile(file);
        setRetryFolderId(selectedFolderId||undefined);
      }
    }finally{
      setUploading(false);
      uploadAbortRef.current=null;
      if(inputRef.current)inputRef.current.value="";
    }
  }

  function cancelUpload(){
    uploadAbortRef.current?.abort();
  }

  async function fetchFileBlob(id:string){
    const response=await api.downloadFile(id);
    if(!response.ok){
      const body=await response.text().catch(()=> "");
      throw new Error(body||"File request failed.");
    }
    return response.blob();
  }

  async function download(id:string,name:string){
    setBusyId(id);
    setError("");
    try{
      const blob=await fetchFileBlob(id);
      const url=URL.createObjectURL(blob);
      const link=document.createElement("a");
      link.href=url;
      link.download=name||"download";
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(()=>URL.revokeObjectURL(url),1000);
    }catch(e){
      setError(e instanceof Error?e.message:"Download failed.");
    }finally{
      setBusyId("");
    }
  }

  async function openFile(id:string){
    setBusyId(id);
    setError("");
    const popup=window.open("about:blank","_blank");
    try{
      const blob=await fetchFileBlob(id);
      const url=URL.createObjectURL(blob);
      if(popup){
        popup.location.href=url;
        window.setTimeout(()=>URL.revokeObjectURL(url),60_000);
      }else{
        window.location.href=url;
      }
    }catch(e){
      popup?.close();
      setError(e instanceof Error?e.message:"Open failed.");
    }finally{
      setBusyId("");
    }
  }

  async function remove(id:string){
    if(!confirm("Delete this file?"))return;
    setBusyId(id);
    setError("");
    try{
      await api.deleteFile(id);
      await qc.invalidateQueries({queryKey:["files",projectId]});
    }catch(e){
      setError(e instanceof Error?e.message:"Delete failed.");
    }finally{
      setBusyId("");
    }
  }

  const bytes=(n:number)=>n<1024?String(n)+" B":n<1024*1024?(n/1024).toFixed(1)+" KB":(n/1024/1024).toFixed(1)+" MB";
  const files=q.data?.items??[];

  return <><Head route="files"/>
    <div className="grid grid-3">
      <Card><div className="row"><h3>Folders</h3><span className="tag">{folders.data?.length??0}</span></div><FolderTools projectId={projectId} folders={folders.data??[]} onChanged={()=>void qc.invalidateQueries({queryKey:["folders",projectId]})}/></Card>
      <Card><h3>Upload</h3>
        <select className="input" value={folderId} onChange={e=>setFolderId(e.target.value)}>
          <option value="">Project root</option>
          {rows(folders.data).map(f=><option key={value(f.id)} value={value(f.id)}>{value(f.name)}</option>)}
        </select>
        <div className="dropzone" style={{display:"grid",placeItems:"center",minHeight:140,marginTop:12}}>
          <input
            ref={inputRef}
            hidden
            type="file"
            disabled={!projectId||uploading}
            onChange={e=>{const f=e.currentTarget.files?.[0];if(f)void upload(f);}}
          />
          {projectId ? (
            uploading ? (
              <button type="button" className="btn" onClick={cancelUpload}>Cancel upload</button>
            ) : (
              <button
                type="button"
                className="btn primary"
                onClick={()=>inputRef.current?.click()}
              >
                Choose a file
              </button>
            )
          ) : (
            <Link className="btn primary" href="/projects">Create a project first</Link>
          )}
          {uploading&&<div style={{width:"100%",maxWidth:360,marginTop:12}}>
            <div className="row tiny"><span style={{overflowWrap:"anywhere"}}>{uploadName}</span><span>{Math.round(uploadProgress)}%</span></div>
            <progress max={100} value={uploadProgress} style={{width:"100%",marginTop:6}}/>
          </div>}
          {uploadNotice&&<div className="notice success" style={{marginTop:10}}>{uploadNotice}</div>}
          {error&&<div className="notice error" style={{marginTop:10}}>
            <span>{error}</span>
            {retryFile&&<button className="btn" style={{marginLeft:8}} onClick={()=>void upload(retryFile,retryFolderId)}>Retry</button>}
          </div>}
          <div className="muted tiny" style={{marginTop:8}}>{projectId?"PDF, DOCX, TXT, CSV, XLSX and other provider-supported research files are accepted; server validation is authoritative.":"File upload is scoped to a project."}</div>
        </div>
      </Card>
      <Card><h3>Intelligence</h3><p className="muted small">Extraction, indexing, classification, code analysis and data profiling run as durable jobs.</p></Card>
    </div>
    <Card style={{marginTop:16}}>
      <div className="row"><h3>Project files</h3><span className="tag">{files.length} files</span></div>
      <div className="table-wrap" style={{marginTop:10}}>
        <table className="table"><thead><tr><th>File</th><th>Status</th><th>Size</th><th>Actions</th></tr></thead>
          <tbody>
            {files.map(f=>{
              const id=value(f.id);
              const name=value(f.original_filename,"Unnamed file");
              const busy=busyId===id;
              return <tr key={id}>
                <td><div className="strong">{name}</div><div className="meta">{value(f.file_kind)}</div></td>
                <td><div>{value(f.status)}</div><div className="meta">{value(f.extraction_status)}</div></td>
                <td>{typeof f.size_bytes==="number"?bytes(f.size_bytes):"—"}</td>
                <td><div className="actions">
                  <select className="input" aria-label={"Move "+name} value={f.folder_id??""} disabled={busy} onChange={async e=>{try{setBusyId(id);await api.updateFile(id,{folder_id:e.target.value||null});await qc.invalidateQueries({queryKey:["files",projectId]});}catch(err){setError(err instanceof Error?err.message:"File move failed.");}finally{setBusyId("");}}}><option value="">Root</option>{(folders.data??[]).map(folder=><option key={folder.id} value={folder.id}>{folder.name}</option>)}</select>
                  <button className="btn" disabled={busy} onClick={()=>void openFile(id)}>{busy?"Working…":"Open"}</button>
                  <button className="btn" disabled={busy} onClick={()=>void download(id,name)}>Download</button>
                  <button className="btn" disabled={busy} onClick={()=>void remove(id)}>Delete</button>
                </div></td>
              </tr>;
            })}
            {!q.isPending&&files.length===0&&<tr><td colSpan={4}><State title="No files" description="Upload a research file to start extraction and intelligence jobs."/></td></tr>}
          </tbody>
        </table>
      </div>
    </Card>
  </>;
}

function Plan(){
  const {projectId}=useCtx();
  const q=useQuery({queryKey:["plan",projectId],queryFn:()=>api.plan(projectId!),enabled:Boolean(projectId)});
  const v=useQuery({queryKey:["plan-v",projectId],queryFn:()=>api.planVersions(projectId!),enabled:Boolean(projectId)});
  const coverage=useQuery({queryKey:["plan-coverage",projectId],queryFn:()=>api.planCoverage(projectId!),enabled:Boolean(projectId)});
  const qc=useQueryClient();
  const [objective,setObjective]=useState("");
  const [questions,setQuestions]=useState("");
  const [hypotheses,setHypotheses]=useState("");
  const [error,setError]=useState("");
  const save=useMutation({mutationFn:()=>api.savePlan(projectId!,{research_objective_snapshot:objective.trim()||null,research_questions_snapshot:questions.split("\n").map(x=>x.trim()).filter(Boolean),hypotheses_snapshot:hypotheses.split("\n").map(x=>x.trim()).filter(Boolean),expected_version:q.data?.version}),onSuccess:async()=>{setError("");await qc.invalidateQueries({queryKey:["plan",projectId]});await qc.invalidateQueries({queryKey:["plan-v",projectId]});await qc.invalidateQueries({queryKey:["plan-coverage",projectId]});},onError:e=>setError(e instanceof Error?e.message:"Plan save failed. Reload the current plan and retry.")});
  const validate=useMutation({mutationFn:()=>api.validatePlan(projectId!),onError:e=>setError(e instanceof Error?e.message:"Plan validation failed.")});
  useEffect(()=>{if(q.data){setObjective(q.data.research_objective_snapshot??"");setQuestions((q.data.research_questions_snapshot??[]).map(String).join("\n"));setHypotheses((q.data.hypotheses_snapshot??[]).map(String).join("\n"));}},[q.data]);
  const plan=q.data;
  return <><Head route="plan" actions={<button className="btn primary" disabled={!projectId||validate.isPending||!plan} onClick={()=>validate.mutate()}>{validate.isPending?"Validating…":"Validate plan"}</button>}/>
    {!projectId&&<Card><State title="No active project" description="Create a project before building a research plan."/></Card>}
    {projectId&&q.isError&&<Card><State title="Research plan unavailable" description={q.error instanceof Error?q.error.message:"Generate a plan first, then edit and validate it."} error/></Card>}
    {projectId&&q.isPending&&<Card><State title="Loading research plan" description="Reading the current version and its research dependencies."/></Card>}
    {plan&&<><div className="grid grid-4"><Metric label="Version" value={plan.version}/><Metric label="Sections" value={plan.sections.length}/><Metric label="Evidence requirements" value={plan.evidence_requirements.length}/><Metric label="Coverage" value={plan.coverage_score===null?"Not calculated":Math.round(plan.coverage_score*100)+"%"}/></div>
      <div className="grid grid-2" style={{marginTop:16}}><Card><h3>Research objective</h3><textarea className="input textarea" value={objective} onChange={e=>setObjective(e.target.value)} placeholder="What does this research need to establish?"/><div className="field" style={{marginTop:12}}><label>Research questions</label><textarea className="input textarea" value={questions} onChange={e=>setQuestions(e.target.value)} placeholder="One question per line"/></div><div className="field" style={{marginTop:12}}><label>Hypotheses</label><textarea className="input textarea" value={hypotheses} onChange={e=>setHypotheses(e.target.value)} placeholder="One hypothesis per line"/></div><button className="btn" style={{marginTop:12}} disabled={save.isPending||!objective.trim()} onClick={()=>save.mutate()}>{save.isPending?"Saving…":"Save plan inputs"}</button>{error&&<div className="notice error" style={{marginTop:10}}>{error}</div>}{validate.data&&<div className="notice" style={{marginTop:10}}>Validation: {validate.data.validation_status}. Completeness {validate.data.completeness_score===null?"unavailable":Math.round(validate.data.completeness_score*100)+"%"}.{validate.data.validation_errors.length>0?" "+validate.data.validation_errors.join(" "):""}</div>}</Card>
        <Card><div className="row"><div><h3>Plan coverage</h3><div className="muted small">Coverage is evaluated against evidence requirements.</div></div><span className="tag">{coverage.data?Math.round(coverage.data.coverage_score*100)+"%":"—"}</span></div>{coverage.isError?<State title="Coverage unavailable" description={coverage.error instanceof Error?coverage.error.message:"Coverage could not be loaded."} error/>:<div className="list" style={{marginTop:10}}>{(coverage.data?.per_requirement??[]).slice(0,20).map((item,index)=>{const x=row(item);return <div className="list-item" key={index}>{value(x.requirement_key??x.requirement_id??"Requirement")} · {value(x.state??x.status??"pending")}</div>;})}</div>}</Card></div>
      <Card style={{marginTop:16}}><h3>Plan sections</h3>{plan.sections.length===0?<State title="No plan sections" description="Generate a plan with at least one section before saving inputs."/>:<div className="list" style={{marginTop:10}}>{plan.sections.map(section=><div className="list-item" key={section.id}><div className="row"><div><div className="title">{section.display_order+1}. {section.title}</div><div className="meta">{section.section_type} · {section.word_budget} words · Evidence target {Math.round(section.evidence_coverage_target*100)}%</div><div className="muted tiny" style={{marginTop:4}}>{section.purpose??"No purpose specified."}</div></div><span className="tag">{section.required?"Required":"Optional"}</span></div></div>)}</div>}</Card>
      <Card style={{marginTop:16}}><h3>Evidence requirements</h3>{plan.evidence_requirements.length===0?<State title="No evidence requirements" description="The plan does not currently define evidence requirements."/>:<div className="table-wrap" style={{marginTop:10}}><table className="table"><thead><tr><th>Requirement</th><th>Section</th><th>Sources</th><th>Full text</th></tr></thead><tbody>{plan.evidence_requirements.map(req=>{const section=plan.sections.find(s=>s.id===req.section_id);return <tr key={req.id}><td style={{overflowWrap:"anywhere"}}>{req.description}</td><td>{section?.title??req.section_id}</td><td>{req.min_sources??"—"}–{req.max_sources??"unlimited"}</td><td>{req.full_text_required?"Required":"Optional"}</td></tr>})}</tbody></table></div>}</Card>
      <Card style={{marginTop:16}}><div className="row"><h3>Version history</h3><span className="tag">{v.data?.total??0}</span></div>{v.isError?<State title="Version history unavailable" description={v.error instanceof Error?v.error.message:"Plan versions could not be loaded."} error/>:v.data?.items.map(version=><div className="list-item" key={version.id}><div className="row"><div><div className="title">Version {version.version}</div><div className="meta">{version.status} · {new Date(version.created_at).toLocaleString()}</div></div><span className="tag">{version.validation_status}</span></div></div>)}</Card>
    </>}</>;
}
function Manuscript(){
  const {reportId}=useCtx();
  const current=useQuery({queryKey:["manuscript",reportId],queryFn:()=>api.manuscript(reportId!),enabled:Boolean(reportId)});
  const versions=useQuery({queryKey:["manuscript-versions",reportId],queryFn:()=>api.manuscriptVersions(reportId!),enabled:Boolean(reportId)});
  const prose=useQuery({queryKey:["manuscript-prose",reportId],queryFn:()=>api.manuscriptProseCurrent(reportId!),enabled:Boolean(reportId)});
  const draft=useQuery({queryKey:["draft",reportId],queryFn:()=>api.manuscriptDraft(reportId!),enabled:Boolean(reportId)});
  const qc=useQueryClient();
  const [sectionDrafts,setSectionDrafts]=useState<Record<string,string>>({});
  const [revision,setRevision]=useState(0);
  const [baseVersionId,setBaseVersionId]=useState<string|undefined>();
  const [dirty,setDirty]=useState(false);
  const [savingError,setSavingError]=useState("");
  const [conflictDraft,setConflictDraft]=useState<{revision:number;base_version_id:string|null;content:unknown}|null>(null);
  const initialized=useRef(false);

  function contentSections(content:unknown):Record<string,string>{
    const obj=row(content);
    const sections=row(obj.sections);
    const result:Record<string,string>={};
    if(!Array.isArray(sections)){
      for(const [key,val] of Object.entries(sections))if(typeof val==="string")result[key]=val;
    }
    return result;
  }
  function applyDraft(remote:{revision:number;base_version_id:string|null;content:unknown}){
    const map=contentSections(remote.content);
    setRevision(remote.revision);
    setBaseVersionId(remote.base_version_id??undefined);
    setSectionDrafts(map);
    setDirty(false);
    setConflictDraft(null);
    setSavingError("");
  }

  useEffect(()=>{
    if(!draft.data||initialized.current)return;
    initialized.current=true;
    setRevision(draft.data.revision);
    setBaseVersionId(draft.data.base_version_id??undefined);
    const map=contentSections(draft.data.content);
    if(Object.keys(map).length===0&&prose.data?.sections.length){
      for(const section of prose.data.sections)map[section.section_key]=section.text;
    }
    setSectionDrafts(map);
  },[draft.data,prose.data]);

  const saveDraft=useMutation({
    mutationFn:()=>api.autosaveManuscript(reportId!,{revision,content:{sections:sectionDrafts},base_version_id:baseVersionId}),
    onSuccess:res=>{
      if(res.conflict){
        setConflictDraft(res.draft);
        setSavingError("Draft changed elsewhere. Your local edits were not accepted.");
        return;
      }
      setRevision(res.draft.revision);
      setBaseVersionId(res.draft.base_version_id??undefined);
      setDirty(false);
      setSavingError("");
      setConflictDraft(null);
      void qc.invalidateQueries({queryKey:["draft",reportId]});
    },
    onError:e=>setSavingError(e instanceof Error?e.message:"Autosave failed. Reload the current draft and retry."),
  });

  useEffect(()=>{
    if(!dirty||!reportId)return;
    const timer=window.setTimeout(()=>{void saveDraft.mutateAsync();},700);
    return()=>window.clearTimeout(timer);
  },[dirty,reportId,sectionDrafts]);

  const saveVersion=useMutation({
    mutationFn:()=>api.saveManuscriptVersion(reportId!,{expected_revision:revision}),
    onSuccess:async()=>{
      setSavingError("");
      await Promise.all([
        qc.invalidateQueries({queryKey:["manuscript",reportId]}),
        qc.invalidateQueries({queryKey:["manuscript-versions",reportId]}),
        qc.invalidateQueries({queryKey:["draft",reportId]}),
      ]);
    },
    onError:e=>setSavingError(e instanceof Error?e.message:"Version save failed."),
  });

  const restoreVersion=useMutation({
    mutationFn:(versionId:string)=>api.restoreManuscriptVersion(reportId!,versionId,{expected_revision:revision}),
    onSuccess:res=>{
      if(res.conflict){
        setConflictDraft(res.draft);
        setSavingError("Restore was not applied because the draft changed elsewhere.");
        return;
      }
      applyDraft(res.draft);
      void qc.invalidateQueries({queryKey:["draft",reportId]});
      setSavingError("Historical version restored into the draft. Review it before saving a new version.");
    },
    onError:e=>setSavingError(e instanceof Error?e.message:"Version restore failed."),
  });

  const validate=useMutation({mutationFn:()=>api.manuscriptProseValidate(reportId!),onError:e=>setSavingError(e instanceof Error?e.message:"Manuscript validation failed.")});
  const regenerate=useMutation({
    mutationFn:()=>api.manuscriptProseGenerate(reportId!,{base_manuscript_version_id:current.data?.version.id??"",async:false,force:true}),
    onSuccess:async()=>{setSavingError("");await qc.invalidateQueries({queryKey:["manuscript-prose",reportId]});},
    onError:e=>setSavingError(e instanceof Error?e.message:"Prose generation failed. Retry the generation run."),
  });
  const version=current.data?.version;

  return <><Head route="manuscript" actions={<><span className="tag">{savingError?"Attention required":dirty?"Saving…":"Autosaved"}</span><button className="btn" disabled={!reportId||validate.isPending} onClick={()=>validate.mutate()}>{validate.isPending?"Validating…":"Validate"}</button><button className="btn" disabled={!reportId||regenerate.isPending||!version} onClick={()=>regenerate.mutate()}>{regenerate.isPending?"Generating…":"Regenerate prose"}</button><button className="btn primary" disabled={!reportId||saveVersion.isPending||dirty||Boolean(conflictDraft)} onClick={()=>saveVersion.mutate()}>{saveVersion.isPending?"Saving…":"Save version"}</button></>}/>
    {savingError&&<div className="notice error" style={{marginBottom:14}}>{savingError}{conflictDraft&&<button className="btn" style={{marginLeft:10}} onClick={()=>applyDraft(conflictDraft)}>Reload authoritative draft</button>}</div>}
    {!reportId&&<Card><State title="No active report" description="Manuscript editing is scoped to a report."/></Card>}
    {reportId&&current.isError&&<Card><State title="Manuscript unavailable" description={current.error instanceof Error?current.error.message:"Generate a manuscript architecture before editing prose."} error/></Card>}
    {reportId&&current.data&&<><Card><div className="row"><div><div className="title">{version?.title??"Untitled manuscript"}</div><div className="meta">Architecture {value(version?.architecture_version)} · Current version {value(version?.version?.toString())}</div></div><Link className="btn" href={"/evidence?reportId="+reportId}>Evidence</Link></div>{validate.data&&<div className="notice" style={{marginTop:12}}>Validation: {validate.data.validation_status}{validate.data.validation_errors.length?" · "+validate.data.validation_errors.join(" "):""}{validate.data.warnings.length?" · Warnings: "+validate.data.warnings.join(" "):""}</div>}</Card>
      <Card style={{marginTop:16}}><div className="row"><div><h3>Manuscript prose</h3><div className="muted small">Each section is edited independently and autosaved against the current draft revision.</div></div><span className="tag">{prose.data?.run.status??"Not generated"}</span></div>
        {prose.isError?<State title="Prose unavailable" description={prose.error instanceof Error?prose.error.message:"Generate manuscript prose before editing sections."} error/>:prose.isPending?<State title="Loading prose" description="Reading the latest persisted prose run."/>:prose.data?.sections.length===0?<State title="No prose sections yet" description="Use Regenerate prose to run the persisted manuscript prose pipeline."/>:<div className="list" style={{marginTop:12}}>{prose.data.sections.map(section=>{const architectureSection=current.data.sections.find(s=>s.section_key===section.section_key);return <div className="list-item" key={section.id}><div className="row"><div><div className="title">{section.display_order+1}. {section.title}</div><div className="meta">{section.word_count} words · {section.status}</div></div><span className="tag">{architectureSection?.citation_required?"Citations required":"Citations optional"}</span></div><textarea className="input textarea" style={{marginTop:10,minHeight:180}} aria-label={"Edit "+section.title} value={sectionDrafts[section.section_key]??section.text} onChange={event=>{setSectionDrafts(prev=>({...prev,[section.section_key]:event.target.value}));setDirty(true);setSavingError("");}}/>{section.error_message&&<div className="notice error" style={{marginTop:8}}>{section.error_message}</div>}</div>;})}</div>}
      </Card>
      <Card style={{marginTop:16}}><div className="row"><div><h3>Version history</h3><div className="muted small">Restore copies a historical snapshot into the current draft; it does not silently overwrite the saved current version.</div></div><span className="tag">{versions.data?.total??0} versions</span></div>
        {versions.isError?<State title="Version history unavailable" description={versions.error instanceof Error?versions.error.message:"Manuscript versions could not be loaded."} error/>:versions.isPending?<State title="Loading versions" description="Reading saved manuscript versions."/>:versions.data?.items.length===0?<State title="No saved versions" description="Save the current draft as a version to build history."/>:<div className="list" style={{marginTop:10}}>{versions.data.items.map(item=><div className="list-item" key={item.id}><div className="row"><div><div className="title">Version {item.version}{item.id===version?.id?" · Current":""}</div><div className="meta">{item.status} · {item.word_target} word target · {new Date(item.created_at).toLocaleString()}</div></div><button className="btn" disabled={dirty||restoreVersion.isPending||item.id===version?.id} onClick={()=>restoreVersion.mutate(item.id)}>{restoreVersion.isPending?"Restoring…":"Restore to draft"}</button></div></div>)}</div>}
      </Card>
    </>}
  </>;
}
function Generate(){
  const {reportId}=useCtx();const [brief,setBrief]=useState("");const m=useMutation({mutationFn:()=>api.enqueueJob("generate_report",{report_id:reportId,brief},reportId)});
  return <><Head route="generate"/><div className="grid grid-2"><Card><div className="field"><label>Generation brief</label><textarea className="input textarea" value={brief} onChange={e=>setBrief(e.target.value)} placeholder="Draft Methods, Discussion, Abstract or Reviewer Response…"/></div><div className="pillbar" style={{marginTop:12}}><span className="tag primary">Evidence grounded</span><span className="tag">Verified evidence</span><span className="tag">Unsupported claim flag</span></div><button className="btn primary" style={{marginTop:14}} disabled={!reportId||m.isPending} onClick={()=>m.mutate()}>{m.isPending?"Queueing…":"Generate"}</button>{m.isError&&<div className="notice error" style={{marginTop:12}}>Generation request failed.</div>}{Boolean(m.data)&&<div className="notice success" style={{marginTop:12}}>Job queued: {value((m.data as Obj).id??(m.data as Obj).job_id)}</div>}</Card><Card><h3>Context</h3><div className="list"><div className="list-item">Evidence matrix</div><div className="list-item">Research plan</div><div className="list-item">Current report</div><div className="list-item">Durable job state</div></div></Card></div></>;
}

function Humanize(){
  const {reportId}=useCtx();const [versionId,setVersionId]=useState("");const [detectionRunId,setDetectionRunId]=useState("");const [policyVersion,setPolicyVersion]=useState("");
  const m=useMutation({mutationFn:()=>api.humanize(reportId!,{version_id:versionId,detection_run_id:detectionRunId,...(policyVersion.trim()?{policy_version:policyVersion.trim()}: {})})});
  return <><Head route="humanize"/><div className="grid grid-2"><Card><div className="field"><label>Report version UUID</label><input className="input" value={versionId} onChange={e=>setVersionId(e.target.value)} placeholder="Approved version"/></div><div className="field" style={{marginTop:12}}><label>Detection run UUID</label><input className="input" value={detectionRunId} onChange={e=>setDetectionRunId(e.target.value)} placeholder="Completed detection run"/></div><div className="field" style={{marginTop:12}}><label>Policy version</label><input className="input" value={policyVersion} onChange={e=>setPolicyVersion(e.target.value)}/></div><button className="btn primary" style={{marginTop:14}} disabled={!reportId||!versionId||!detectionRunId||m.isPending} onClick={()=>m.mutate()}>{m.isPending?"Queueing…":"Rewrite"}</button></Card><Card><h3>Preservation controls</h3>{["Claim integrity","Evidence markers","Citations","URLs / DOIs","Numbers"].map(x=><div className="row list-item" key={x}><span>{x}</span><span className="tag success">Protected</span></div>)}</Card></div></>;
}

function Translate(){
  const {reportId}=useCtx();const [version,setVersion]=useState("");const [lang,setLang]=useState("fa");const m=useMutation({mutationFn:()=>api.translate(reportId!,{source_version_id:version,target_language:lang})});
  return <><Head route="translate"/><Card><div className="grid grid-3"><div className="field"><label>Approved source version</label><input className="input" value={version} onChange={e=>setVersion(e.target.value)} placeholder="Version UUID"/></div><div className="field"><label>Target language</label><select className="input" value={lang} onChange={e=>setLang(e.target.value)}><option value="fa">Persian</option><option value="en">English</option><option value="de">German</option><option value="fr">French</option></select></div><div className="actions" style={{alignItems:"end"}}><button className="btn primary" disabled={!reportId||!version||m.isPending} onClick={()=>m.mutate()}>{m.isPending?"Queueing…":"Translate"}</button></div></div>{m.isError&&<div className="notice error" style={{marginTop:12}}>Translation request failed; verify the source version is the approved version.</div>}</Card></>;
}

function Collaboration(){
  const {ws,reportId}=useCtx();
  const manuscript=useQuery({queryKey:["collab-manuscript",reportId],queryFn:()=>api.manuscript(reportId!),enabled:Boolean(reportId)});
  const versionId=value(row(row(manuscript.data).version).id,"");
  const comments=useQuery({queryKey:["comments",reportId,versionId],queryFn:()=>api.manuscriptComments(reportId!,versionId),enabled:Boolean(reportId&&versionId)});
  const reviews=useQuery({queryKey:["reviews",reportId,versionId],queryFn:()=>api.reviewTasks(reportId!,versionId),enabled:Boolean(reportId&&versionId)});
  const members=useQuery({queryKey:["collab-members",ws.workspaceId],queryFn:()=>api.members(ws.workspaceId!),enabled:Boolean(ws.workspaceId)});
  const qc=useQueryClient();
  const [comment,setComment]=useState("");
  const [reviewTitle,setReviewTitle]=useState("");
  const [assignee,setAssignee]=useState("");
  const [severity,setSeverity]=useState("info");
  const [error,setError]=useState("");
  const addComment=useMutation({mutationFn:()=>api.addManuscriptComment(reportId!,versionId,{body:comment}),onSuccess:()=>{setComment("");setError("");void qc.invalidateQueries({queryKey:["comments",reportId,versionId]});},onError:e=>setError(e instanceof Error?e.message:"Comment could not be added.")});
  const addReview=useMutation({
    mutationFn:()=>api.createReviewTask(reportId!,versionId,{manuscript_version_id:versionId,title:reviewTitle,severity,assignee_user_id:assignee||null}),
    onSuccess:()=>{setReviewTitle("");setAssignee("");setSeverity("info");setError("");void qc.invalidateQueries({queryKey:["reviews",reportId,versionId]});},
    onError:e=>setError(e instanceof Error?e.message:"Review task could not be created."),
  });
  const resolve=useMutation({mutationFn:(id:string)=>api.resolveComment(reportId!,id),onSuccess:()=>void qc.invalidateQueries({queryKey:["comments",reportId,versionId]}),onError:e=>setError(e instanceof Error?e.message:"Comment update failed.")});
  const reopen=useMutation({mutationFn:(id:string)=>api.reopenComment(reportId!,id),onSuccess:()=>void qc.invalidateQueries({queryKey:["comments",reportId,versionId]}),onError:e=>setError(e instanceof Error?e.message:"Comment update failed.")});
  const updateReview=useMutation({mutationFn:(x:{id:string;status:string})=>api.updateReviewTask(reportId!,x.id,{status:x.status}),onSuccess:()=>void qc.invalidateQueries({queryKey:["reviews",reportId,versionId]}),onError:e=>setError(e instanceof Error?e.message:"Review task update failed.")});
  const memberItems=members.data?.items??[];
  return <><Head route="collaboration"/>
    {error&&<div className="notice error" style={{marginBottom:14}}>{error}</div>}
    {!reportId&&<Card><State title="No active report" description="Collaboration is attached to a report version."/></Card>}
    {reportId&&<div className="grid grid-2">
      <Card><h3>Comments</h3><textarea className="input textarea" aria-label="Review comment" style={{minHeight:130,marginTop:12}} value={comment} onChange={e=>setComment(e.target.value)} placeholder="Add a review comment…"/><button className="btn primary" style={{marginTop:10}} disabled={!versionId||!comment.trim()||addComment.isPending} onClick={()=>addComment.mutate()}>{addComment.isPending?"Posting…":"Add comment"}</button><div className="list" style={{marginTop:14}}>{comments.isError?<State title="Comments unavailable" description={comments.error instanceof Error?comments.error.message:"Comments could not be loaded."} error/>:comments.data?.items.length===0?<State title="No comments" description="Add a comment anchored to the current manuscript version."/>:comments.data?.items.map(item=><div className="list-item" key={item.id}><div className="title" style={{overflowWrap:"anywhere"}}>{item.body}</div><div className="meta">{item.status} · {item.author_user_id} · {new Date(item.created_at).toLocaleString()}</div><div className="actions" style={{marginTop:8}}>{item.status==="resolved"?<button className="btn" disabled={reopen.isPending} onClick={()=>reopen.mutate(item.id)}>Reopen</button>:<button className="btn" disabled={resolve.isPending} onClick={()=>resolve.mutate(item.id)}>Resolve</button>}</div></div>)}</div></Card>
      <Card><h3>Review tasks</h3><div className="grid grid-3" style={{marginTop:12}}><div className="field"><label>Task</label><input className="input" value={reviewTitle} onChange={e=>setReviewTitle(e.target.value)} placeholder="Review task title"/></div><div className="field"><label>Assignee</label><select className="input" value={assignee} onChange={e=>setAssignee(e.target.value)}><option value="">Unassigned</option>{memberItems.map(m=><option key={m.user_id} value={m.user_id}>{m.email}</option>)}</select></div><div className="field"><label>Severity</label><select className="input" value={severity} onChange={e=>setSeverity(e.target.value)}><option value="info">Info</option><option value="warning">Warning</option><option value="error">Error</option><option value="blocking">Blocking</option></select></div></div><button className="btn primary" style={{marginTop:10}} disabled={!versionId||!reviewTitle.trim()||addReview.isPending} onClick={()=>addReview.mutate()}>{addReview.isPending?"Creating…":"Create review task"}</button><div className="list" style={{marginTop:14}}>{reviews.isError?<State title="Review queue unavailable" description={reviews.error instanceof Error?reviews.error.message:"Review tasks could not be loaded."} error/>:reviews.data?.items.length===0?<State title="No review tasks" description="Create a review task for this manuscript version."/>:reviews.data?.items.map(item=><div className="list-item" key={item.id}><div className="row"><div><div className="title">{item.title}</div><div className="meta">{item.status} · {item.severity} · {item.assignee_user_id?"Assigned":"Unassigned"}</div><div className="muted tiny" style={{marginTop:4}}>Created {new Date(item.created_at).toLocaleString()}{item.resolved_at?" · Resolved "+new Date(item.resolved_at).toLocaleString():""}</div></div><span className="tag">{item.assignee_user_id??"Unassigned"}</span></div><div className="actions" style={{marginTop:8}}>{item.status!=="resolved"&&item.status!=="rejected"&&<button className="btn" disabled={updateReview.isPending} onClick={()=>updateReview.mutate({id:item.id,status:"resolved"})}>Resolve</button>}{item.status==="resolved"&&<button className="btn" disabled={updateReview.isPending} onClick={()=>updateReview.mutate({id:item.id,status:"open"})}>Reopen</button>}</div></div>)}</div></Card>
    </div>}
    {reportId&&<Card style={{marginTop:16}}><h3>Version context</h3><div className="muted small">Review actions are attached to the current manuscript version. Version: <span className="mono">{versionId||"Unavailable"}</span> · Workspace: <span className="mono">{ws.workspaceId||"Unavailable"}</span></div></Card>}
  </>;
}
function Generic({route}:{route:string}){
  const {projectId,reportId,ws}=useCtx();
  const q=useQuery({queryKey:["generic",route,projectId,reportId,ws.workspaceId],queryFn:async()=>{
    switch(route){
      case "sources":return reportId?api.sources(reportId):[];
      case "literature":return projectId?api.literature(projectId):{};
      case "evidence":return reportId?api.evidenceMatrix(reportId):[];
      case "knowledge":return projectId?api.knowledgeGraph(projectId):{};
      case "files":return projectId?api.files(projectId):{};
      case "plan":return projectId?api.plan(projectId):{};
      case "manuscript":return reportId?api.manuscript(reportId):{};
      case "collaboration":case "team":return ws.workspaceId?api.members(ws.workspaceId):{};
      default:return {route};
    }
  },enabled:Boolean(projectId||reportId||ws.workspaceId)});
  return <><Head route={route}/><Card>{q.isError?<State title="API request failed" description="The backend returned an error for this capability." error/>:<pre className="code" style={{whiteSpace:"pre-wrap",fontSize:11}}>{JSON.stringify(q.data??{status:"waiting"},null,2)}</pre>}</Card></>;
}

