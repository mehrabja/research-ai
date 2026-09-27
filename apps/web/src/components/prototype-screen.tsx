"use client";
import Link from "next/link";
import {useMemo,useState} from "react";
import {useMutation,useQuery,useQueryClient} from "@tanstack/react-query";
import {useSearchParams} from "next/navigation";
import {AppShell,useWorkspace} from "./app-shell";
import {api} from "@/lib/api/client";

type Obj=Record<string,unknown>;
const META:Record<string,{eyebrow:string;title:string;description:string}>={
  dashboard:{eyebrow:"Workspace",title:"Research control plane",description:"Projects, evidence, jobs and usage from the selected workspace."},
  workspace:{eyebrow:"Workspace",title:"Research workspace",description:"Tenant context, project inventory and workspace lifecycle."},
  research:{eyebrow:"Discovery",title:"Research discovery",description:"Workspace-scoped research search with real API results."},
  sources:{eyebrow:"Corpus",title:"Source library",description:"Saved sources and discovery candidates for the active report."},
  literature:{eyebrow:"Synthesis",title:"Literature intelligence",description:"Analysis, clusters, themes, screening and gaps."},
  evidence:{eyebrow:"Evidence",title:"Evidence matrix",description:"Claims, support, conflict, confidence and provenance."},
  knowledge:{eyebrow:"Knowledge",title:"Knowledge graph",description:"Concepts and relationships with JSON/CSV export."},
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
function value(v:unknown,fallback="—"):string{ return typeof v==="string"&&v.trim()?v:fallback; }
function Head({route,actions}:{route:string;actions?:React.ReactNode}){const m=META[route]??{eyebrow:"Research AI",title:"Page",description:""};return <div className="page-head"><div><div className="eyebrow">{m.eyebrow}</div><h1>{m.title}</h1><p>{m.description}</p></div>{actions&&<div className="actions">{actions}</div>}</div>}
function Card({children}:{children:React.ReactNode}){return <section className="card pad">{children}</section>}
function State({title,description,error=false}:{title:string;description:string;error?:boolean}){return <div className={"state"+(error?" error":"")}><h3>{title}</h3><p>{description}</p></div>}
function Table({data}:{data:Obj[]}){return <div className="table-wrap"><table className="table"><thead><tr><th>Record</th><th>Status</th><th>Identifier</th></tr></thead><tbody>{data.slice(0,30).map((x,i)=><tr key={i}><td>{value(x.title??x.name??x.claim??x.type,"Record")}</td><td>{value(x.status??x.state)}</td><td className="mono">{value(x.id)}</td></tr>)}</tbody></table></div>}

export function PrototypeScreen({segments}:{segments:string[]}){
  const route=segments[0]??"dashboard";
  if(route==="landing")return <Landing/>;
  if(route==="loading")return <LoadingView/>;
  return <AuthenticatedScreen route={route}/>;
}
function AuthenticatedScreen({route}:{route:string}){
  const user=useQuery({queryKey:["me"],queryFn:api.me});
  if(user.isPending)return <State title="Loading session" description="Restoring the authenticated workspace…"/>;
  if(user.isError)return <State title="Session unavailable" description="The backend authentication session could not be restored." error/>;
  return <AppShell userEmail={user.data.email}><Screen route={route}/></AppShell>;
}
function LoadingView(){return <div className="auth-page"><section className="auth-side"><div className="brand"><span className="brand-mark">R</span><span>Research AI</span></div><div className="eyebrow" style={{marginTop:70}}>Research workspace</div><h1>Restoring your evidence context.</h1><p>The workspace is reconnecting to the authenticated API session.</p></section><section className="auth-main"><div className="auth-card"><div className="eyebrow">Loading</div><h2>Opening workspace…</h2><div className="notice" style={{marginTop:14}}>The interface is waiting for backend state; no demo data is inserted.</div></div></section></div>}

function Screen({route}:{route:string}){
 switch(route){
 case "dashboard":return <Dashboard/>;case "research":return <Research/>;case "notifications":return <Notifications/>;case "jobs":return <Jobs/>;case "team":return <Team/>;case "settings":return <Settings/>;case "usage-billing":return <Billing/>;case "knowledge":return <Knowledge/>;case "files":return <Files/>;case "plan":return <Plan/>;case "manuscript":return <Manuscript/>;case "generate":return <Generate/>;case "humanize":return <Humanize/>;case "translate":return <Translate/>;case "collaboration":return <Collaboration/>;
 default:return <Generic route={route}/>;
 }
}

function useCtx(){const ws=useWorkspace();const projects=useQuery({queryKey:["projects",ws.workspaceId],queryFn:()=>api.projects(ws.workspaceId!),enabled:Boolean(ws.workspaceId)});const projectId=projects.data?.items?.[0]?.id;const reports=useQuery({queryKey:["reports",projectId],queryFn:()=>api.projectReports(projectId!,ws.workspaceId!),enabled:Boolean(projectId&&ws.workspaceId)});const reportId=reports.data?.items?.[0]?.id;return {ws,projects,projectId,reports,reportId};}

function Dashboard(){const {ws,projects}=useCtx();const s=useQuery({queryKey:["dashboard",ws.workspaceId],queryFn:()=>api.dashboard(ws.workspaceId!),enabled:Boolean(ws.workspaceId)});return <><Head route="dashboard" actions={<><Link className="btn" href="/team">Invite teammate</Link><Link className="btn primary" href="/workspace">Open workspace</Link></>}/><div className="grid grid-4"><Metric label="Active projects" value={s.data?.active_projects}/><Metric label="Saved sources" value={s.data?.saved_sources}/><Metric label="Evidence items" value={s.data?.evidence_items}/><Metric label="AI generation units" value={s.data?.ai_generation_units}/></div><Card style={{marginTop:16}}><h3>Projects</h3><Table data={(projects.data?.items??[]) as unknown as Obj[]}/></Card></>}
function Metric({label,value:v}:{label:string;value:unknown}){return <div className="card metric"><div className="label">{label}</div><div className="value">{v??"—"}</div><div className="delta">Backend source of truth</div></div>}

function Research(){
  const {ws,reportId}=useCtx();
  const p=useSearchParams();
  const [q,setQ]=useState(p.get("q")??"");
  const [year,setYear]=useState("");
  const [openAccess,setOpenAccess]=useState(false);
  const search=useQuery({
    queryKey:["source-discovery",reportId,q,year,openAccess],
    queryFn:()=>api.searchSources(reportId!,q,year?Number(year):undefined,openAccess),
    enabled:Boolean(reportId&&q.trim()),
  });
  const save=useMutation({mutationFn:(item:unknown)=>api.createSource(reportId!,item as SourceCandidate)});
  const global=useQuery({
    queryKey:["global-search",ws.workspaceId,q],
    queryFn:()=>api.globalSearch(q,ws.workspaceId!),
    enabled:Boolean(ws.workspaceId&&q.trim()&&!reportId),
  });
  return <><Head route="research"/>
    <div className="grid grid-3">
      <Card><div className="field"><label>Research query</label><input className="input" value={q} onChange={e=>setQ(e.target.value)} placeholder="topic, DOI, title, author…"/></div></Card>
      <Card><div className="field"><label>Year</label><input className="input" inputMode="numeric" value={year} onChange={e=>setYear(e.target.value.replace(/\D/g,"").slice(0,4))} placeholder="2024"/></div></Card>
      <Card><label className="checkbox"><input type="checkbox" checked={openAccess} onChange={e=>setOpenAccess(e.target.checked)}/><span><b>Open access only</b><br/><span className="muted tiny">Applied only where the research provider supports it.</span></span></label></Card>
    </div>
    <Card style={{marginTop:16}}><div className="row"><div><h3>Discovery results</h3><div className="muted small">{reportId?"Semantic Scholar-backed source discovery for the active report.":"Workspace global search."}</div></div><span className="tag">{search.data?.candidates?.length??global.data?.total??0} results</span></div>
      {reportId&&<div className="list" style={{marginTop:10}}>{search.data?.candidates?.map((item,index)=><div className="list-item" key={item.external_source_id??index}><div className="row"><div><div className="title">{item.title}</div><div className="meta">{item.year??"Year unknown"} · {item.doi??item.url??"No DOI/URL"}</div></div><button className="btn" disabled={save.isPending} onClick={()=>save.mutate(item)}>Save source</button></div></div>)}{q&&!search.isPending&&(search.data?.candidates?.length??0)===0&&<State title="No provider results" description="The source provider returned no candidate for this query/filter set."/>}</div>}
      {!reportId&&q&&<Table data={rows(global.data?.items)}/>}
      {!q&&<State title="Start with a research query" description="Search the current report's literature or the workspace index."/>}
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

function Jobs(){const {ws}=useCtx();const qc=useQueryClient();const q=useQuery({queryKey:["jobs",ws.workspaceId],queryFn:()=>api.jobs(ws.workspaceId),enabled:Boolean(ws.workspaceId),refetchInterval:5000});const retry=useMutation({mutationFn:(id:string)=>api.retryJob(id),onSuccess:()=>qc.invalidateQueries({queryKey:["jobs",ws.workspaceId]})});const cancel=useMutation({mutationFn:(id:string)=>api.cancelJob(id),onSuccess:()=>qc.invalidateQueries({queryKey:["jobs",ws.workspaceId]})});return <><Head route="jobs"/><Card>{rows(q.data).map(x=>{const id=value(x.id);const st=value(x.status);return <div className="list-item" key={id}><div className="row"><div><div className="title">{value(x.job_type,"Job")}</div><div className="meta">{st} · {value(x.error_code)}</div></div><div className="actions">{st==="failed"&&<button className="btn" onClick={()=>retry.mutate(id)}>Retry</button>}{["queued","processing","retrying"].includes(st)&&<button className="btn" onClick={()=>cancel.mutate(id)}>Cancel</button>}</div></div></div>})}</Card></>}
function Team(){const {ws}=useCtx();const q=useQuery({queryKey:["members",ws.workspaceId],queryFn:()=>api.members(ws.workspaceId!),enabled:Boolean(ws.workspaceId)});return <><Head route="team"/><Card><Table data={rows(q.data?.items)}/></Card></>}
function Billing(){const {ws}=useCtx();const u=useQuery({queryKey:["usage",ws.workspaceId],queryFn:()=>api.usage(ws.workspaceId!),enabled:Boolean(ws.workspaceId)});const p=useQuery({queryKey:["plan",ws.workspaceId],queryFn:()=>api.planSubscription(ws.workspaceId!),enabled:Boolean(ws.workspaceId)});const i=useQuery({queryKey:["invoices",ws.workspaceId],queryFn:()=>api.billingInvoices(ws.workspaceId!),enabled:Boolean(ws.workspaceId)});const [code,setCode]=useState("pro");const checkout=useMutation({mutationFn:()=>api.billingCheckout(ws.workspaceId!,code)});return <><Head route="usage-billing"/><div className="grid grid-4"><Metric label="Plan" value={row(p.data).code??row(p.data).name}/><Metric label="AI units" value={row(u.data).ai_generation_units}/><Metric label="Storage bytes" value={row(u.data).storage_bytes}/><Metric label="Invoices" value={rows(i.data).length}/></div><div className="grid grid-2" style={{marginTop:16}}><Card><h3>Checkout</h3><select className="input" value={code} onChange={e=>setCode(e.target.value)}><option value="pro">Pro</option><option value="team">Team</option></select><button className="btn primary" style={{marginTop:12}} onClick={()=>checkout.mutate()} disabled={!ws.workspaceId||checkout.isPending}>Open checkout</button></Card><Card><h3>Invoices</h3><pre className="code" style={{whiteSpace:"pre-wrap",fontSize:11}}>{JSON.stringify(i.data??[],null,2)}</pre></Card></div></>}
function Settings(){const sessions=useQuery({queryKey:["sessions"],queryFn:api.sessions});const tokens=useQuery({queryKey:["tokens"],queryFn:api.apiTokens});const tf=useQuery({queryKey:["2fa"],queryFn:api.twoFactor});return <><Head route="settings"/><div className="grid grid-2"><Card id="security"><h3>Two-factor</h3><div className="tag">{Boolean(row(tf.data).enabled)?"Enabled":"Not enabled"}</div></Card><Card><h3>Sessions</h3><Table data={rows(sessions.data)}/></Card><Card><h3>API tokens</h3><Table data={rows(tokens.data)}/></Card><Card id="notifications"><h3>Notification settings</h3><p className="muted small">Notification preferences and unread state are served by the backend notification API.</p></Card></div></>}

function Landing(){return <><div className="hero"><div className="container"><div className="hero-grid"><div><div className="eyebrow">Research operating system</div><h1>From question to a defensible paper.</h1><p>Discovery, evidence, planning, writing, review and translation in one controlled workspace.</p><div className="actions" style={{marginTop:20}}><Link className="btn primary" href="/dashboard">Open workspace</Link><Link className="btn" href="/register">Create account</Link></div></div><div className="hero-card"><div className="hero-ui"><div className="mini-side"><div className="mini-line mid"/><div className="mini-line"/><div className="mini-line short"/></div><div className="mini-main"><span className="tag primary">Evidence grounded</span><div className="mini-line mid"/><div className="mini-line"/><div className="notice" style={{marginTop:16}}>Question → Discovery → Evidence → Plan → Write</div></div></div></div></div></div></div><div className="section container"><div className="grid grid-3"><div className="card feature"><div className="tag">01</div><h3>Discover</h3><p>Search literature with provenance and screening.</p></div><div className="card feature"><div className="tag">02</div><h3>Understand</h3><p>Connect sources to claims, evidence and plans.</p></div><div className="card feature"><div className="tag">03</div><h3>Create</h3><p>Write, review, humanize and translate with traceability.</p></div></div></div></>}