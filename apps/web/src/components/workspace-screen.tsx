"use client";
import Link from "next/link";
import {useEffect,useMemo,useState} from "react";
import {useMutation,useQuery,useQueryClient} from "@tanstack/react-query";
import {useSearchParams} from "next/navigation";
import {AppShell,useWorkspace} from "./app-shell";
import {api} from "@/lib/api/client";
import type {SourceCandidate} from "@/lib/api/generated";

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
function value(v:unknown,fallback="—"):string{ if(typeof v==="string"&&v.trim())return v; if(typeof v==="number"||typeof v==="boolean")return String(v); return fallback; }
function Head({route,actions}:{route:string;actions?:React.ReactNode}){const m=META[route]??{eyebrow:"Research AI",title:"Page",description:""};return <div className="page-head"><div><div className="eyebrow">{m.eyebrow}</div><h1>{m.title}</h1><p>{m.description}</p></div>{actions&&<div className="actions">{actions}</div>}</div>}
function Card({children,style,id}:{children:React.ReactNode;style?:React.CSSProperties;id?:string}){return <section className="card pad" style={style} id={id}>{children}</section>}
function State({title,description,error=false}:{title:string;description:string;error?:boolean}){return <div className={"state"+(error?" error":"")}><h3>{title}</h3><p>{description}</p></div>}
function Table({data}:{data:Obj[]}){return <div className="table-wrap"><table className="table"><thead><tr><th>Record</th><th>Status</th><th>Identifier</th></tr></thead><tbody>{data.slice(0,30).map((x,i)=><tr key={i}><td>{value(x.title??x.name??x.claim??x.type,"Record")}</td><td>{value(x.status??x.state)}</td><td className="mono">{value(x.id)}</td></tr>)}</tbody></table></div>}

export function WorkspaceScreen({route}:{route:string}){return <Screen route={route}/>;}

function Screen({route}:{route:string}){
 switch(route){
 case "dashboard":return <Dashboard/>;case "research":return <Research/>;case "notifications":return <Notifications/>;case "jobs":return <Jobs/>;case "team":return <Team/>;case "settings":return <Settings/>;case "usage-billing":return <Billing/>;case "knowledge":return <Knowledge/>;case "files":return <Files/>;case "plan":return <Plan/>;case "manuscript":return <Manuscript/>;case "generate":return <Generate/>;case "humanize":return <Humanize/>;case "translate":return <Translate/>;case "collaboration":return <Collaboration/>;
 default:return <Generic route={route}/>;
 }
}

function useCtx(){const ws=useWorkspace();const projects=useQuery({queryKey:["projects",ws.workspaceId],queryFn:()=>api.projects(ws.workspaceId!),enabled:Boolean(ws.workspaceId)});const projectId=projects.data?.items?.[0]?.id;const reports=useQuery({queryKey:["reports",projectId],queryFn:()=>api.projectReports(projectId!,ws.workspaceId!),enabled:Boolean(projectId&&ws.workspaceId)});const reportId=reports.data?.items?.[0]?.id;return {ws,projects,projectId,reports,reportId};}

function Dashboard(){const {ws,projects}=useCtx();const s=useQuery({queryKey:["dashboard",ws.workspaceId],queryFn:()=>api.dashboard(ws.workspaceId!),enabled:Boolean(ws.workspaceId)});return <><Head route="dashboard" actions={<><Link className="btn" href="/team">Invite teammate</Link><Link className="btn primary" href="/workspace">Open workspace</Link></>}/><div className="grid grid-4"><Metric label="Active projects" value={s.data?.active_projects}/><Metric label="Saved sources" value={s.data?.saved_sources}/><Metric label="Evidence items" value={s.data?.evidence_items}/><Metric label="AI generation units" value={s.data?.ai_generation_units}/></div><Card style={{marginTop:16}}><h3>Projects</h3><Table data={(projects.data?.items??[]) as unknown as Obj[]}/></Card></>}
function Metric({label,value:v}:{label:string;value:unknown}){return <div className="card metric"><div className="label">{label}</div><div className="value">{value(v)}</div><div className="delta">Backend source of truth</div></div>}

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

function Jobs(){const {ws}=useCtx();const qc=useQueryClient();const q=useQuery({queryKey:["jobs",ws.workspaceId],queryFn:()=>api.jobs(ws.workspaceId??undefined),enabled:Boolean(ws.workspaceId),refetchInterval:5000});const retry=useMutation({mutationFn:(id:string)=>api.retryJob(id),onSuccess:()=>qc.invalidateQueries({queryKey:["jobs",ws.workspaceId]})});const cancel=useMutation({mutationFn:(id:string)=>api.cancelJob(id),onSuccess:()=>qc.invalidateQueries({queryKey:["jobs",ws.workspaceId]})});return <><Head route="jobs"/><Card>{rows(q.data).map(x=>{const id=value(x.id);const st=value(x.status);return <div className="list-item" key={id}><div className="row"><div><div className="title">{value(x.job_type,"Job")}</div><div className="meta">{st} · {value(x.error_code)}</div></div><div className="actions">{st==="failed"&&<button className="btn" onClick={()=>retry.mutate(id)}>Retry</button>}{["queued","processing","retrying"].includes(st)&&<button className="btn" onClick={()=>cancel.mutate(id)}>Cancel</button>}</div></div></div>})}</Card></>}
function Team(){
  const {ws}=useCtx();
  const q=useQuery({queryKey:["members",ws.workspaceId],queryFn:()=>api.members(ws.workspaceId!),enabled:Boolean(ws.workspaceId)});
  const qc=useQueryClient();
  const [email,setEmail]=useState("");const [role,setRole]=useState("member");const [error,setError]=useState("");
  const invite=useMutation({
    mutationFn:()=>api.invite(ws.workspaceId!,{email,role}),
    onSuccess:()=>{setEmail("");setError("");void qc.invalidateQueries({queryKey:["members",ws.workspaceId]});},
    onError:e=>setError(e instanceof Error?e.message:"Invitation failed."),
  });
  const changeRole=useMutation({
    mutationFn:(x:{userId:string;role:string})=>api.changeMemberRole(ws.workspaceId!,x.userId,x.role),
    onSuccess:()=>void qc.invalidateQueries({queryKey:["members",ws.workspaceId]}),
  });
  const remove=useMutation({
    mutationFn:(id:string)=>api.removeMember(ws.workspaceId!,id),
    onSuccess:()=>void qc.invalidateQueries({queryKey:["members",ws.workspaceId]}),
  });
  return <><Head route="team"/><div className="grid grid-2">
    <Card><h3>Invite collaborator</h3><p className="muted small">Invitation state is persisted by the workspace membership service and delivered asynchronously when email is configured.</p><div className="field" style={{marginTop:14}}><label>Email</label><input className="input" type="email" value={email} onChange={e=>setEmail(e.target.value)} placeholder="researcher@lab.edu"/></div><div className="field" style={{marginTop:12}}><label>Role</label><select className="input" value={role} onChange={e=>setRole(e.target.value)}><option value="member">Member</option><option value="viewer">Viewer</option><option value="admin">Admin</option></select></div><button className="btn primary" style={{marginTop:12}} disabled={!ws.workspaceId||!email||invite.isPending} onClick={()=>invite.mutate()}>{invite.isPending?"Sending…":"Send invitation"}</button>{error&&<div className="notice error" style={{marginTop:12}}>{error}</div>}</Card>
    <Card><h3>Role matrix</h3><div className="list" style={{marginTop:10}}>{[["Owner","workspace ownership"],["Admin","members, billing and settings"],["Member","research and content"],["Viewer","read-only access"]].map(([a,b])=><div className="list-item" key={a}><div className="row"><b>{a}</b><span className="muted small">{b}</span></div></div>)}</div></Card>
  </div>
  <Card style={{marginTop:16}}><h3>Members</h3><div className="table-wrap"><table className="table"><thead><tr><th>Member</th><th>Role</th><th>Status</th><th>Actions</th></tr></thead><tbody>{q.data?.items?.map(m=>{const x=m as unknown as Obj;const id=value(x.user_id);const rle=value(x.role);return <tr key={id}><td>{value(x.email??x.user_id)}</td><td><select className="input" value={rle} onChange={e=>changeRole.mutate({userId:id,role:e.target.value})} disabled={changeRole.isPending||rle==="owner"}><option value="owner">Owner</option><option value="admin">Admin</option><option value="member">Member</option><option value="viewer">Viewer</option></select></td><td>{value(x.status,"active")}</td><td><button className="btn" disabled={remove.isPending||rle==="owner"} onClick={()=>remove.mutate(id)}>Remove</button></td></tr>})}</tbody></table></div></Card>
  </>;
}

function Billing(){const {ws}=useCtx();const u=useQuery({queryKey:["usage",ws.workspaceId],queryFn:()=>api.usage(ws.workspaceId!),enabled:Boolean(ws.workspaceId)});const p=useQuery({queryKey:["plan",ws.workspaceId],queryFn:()=>api.planSubscription(ws.workspaceId!),enabled:Boolean(ws.workspaceId)});const i=useQuery({queryKey:["invoices",ws.workspaceId],queryFn:()=>api.billingInvoices(ws.workspaceId!),enabled:Boolean(ws.workspaceId)});const [code,setCode]=useState("pro");const checkout=useMutation({mutationFn:()=>api.billingCheckout(ws.workspaceId!,code)});return <><Head route="usage-billing"/><div className="grid grid-4"><Metric label="Plan" value={row(p.data).code??row(p.data).name}/><Metric label="AI units" value={row(u.data).ai_generation_units}/><Metric label="Storage bytes" value={row(u.data).storage_bytes}/><Metric label="Invoices" value={rows(i.data).length}/></div><div className="grid grid-2" style={{marginTop:16}}><Card><h3>Checkout</h3><select className="input" value={code} onChange={e=>setCode(e.target.value)}><option value="pro">Pro</option><option value="team">Team</option></select><button className="btn primary" style={{marginTop:12}} onClick={()=>checkout.mutate()} disabled={!ws.workspaceId||checkout.isPending}>Open checkout</button></Card><Card><h3>Invoices</h3><pre className="code" style={{whiteSpace:"pre-wrap",fontSize:11}}>{JSON.stringify(i.data??[],null,2)}</pre></Card></div></>}
function Settings(){const sessions=useQuery({queryKey:["sessions"],queryFn:api.sessions});const tokens=useQuery({queryKey:["tokens"],queryFn:api.apiTokens});const tf=useQuery({queryKey:["2fa"],queryFn:api.twoFactor});return <><Head route="settings"/><div className="grid grid-2"><Card id="security"><h3>Two-factor</h3><div className="tag">{Boolean(row(tf.data).enabled)?"Enabled":"Not enabled"}</div></Card><Card><h3>Sessions</h3><Table data={rows(sessions.data)}/></Card><Card><h3>API tokens</h3><Table data={rows(tokens.data)}/></Card><Card id="notifications"><h3>Notification settings</h3><p className="muted small">Notification preferences and unread state are served by the backend notification API.</p></Card></div></>}


function Workspace(){
  const {ws,projects}=useCtx();
  const [name,setName]=useState("");
  const qc=useQueryClient();
  const create=useMutation({mutationFn:()=>api.createWorkspace(name),onSuccess:()=>{setName("");void qc.invalidateQueries({queryKey:["workspaces"]})}});
  return <><Head route="workspace"/><div className="grid grid-2">
    <Card><h3>Workspace context</h3><div className="list" style={{marginTop:10}}>{ws.workspaces.map(w=><div className="list-item" key={w.id}><div className="row"><div><div className="title">{w.name}</div><div className="meta">{w.slug} · {w.status}</div></div><span className="tag">{w.role}</span></div></div>)}</div></Card>
    <Card><h3>Create workspace</h3><p className="muted small">Owner membership and subscription setup are handled transactionally by the backend.</p><div className="row" style={{marginTop:14}}><input className="input" value={name} onChange={e=>setName(e.target.value)} placeholder="Workspace name"/><button className="btn primary" disabled={!name.trim()||create.isPending} onClick={()=>create.mutate()}>{create.isPending?"Creating…":"Create"}</button></div>{create.isError&&<div className="notice error" style={{marginTop:10}}>Workspace creation failed.</div>}</Card>
  </div><Card style={{marginTop:16}}><h3>Projects</h3><Table data={rows(projects.data?.items)}/></Card></>;
}

function Sources(){
  const {reportId}=useCtx();
  const q=useQuery({queryKey:["sources",reportId],queryFn:()=>api.sources(reportId!),enabled:Boolean(reportId)});
  return <><Head route="sources" actions={<Link className="btn primary" href="/research">Discover sources</Link>}/><Card><Table data={rows(q.data?.items)}/>{!reportId&&<State title="No active report" description="Create a project report before managing the source library."/>}{reportId&&!q.isPending&&rows(q.data?.items).length===0&&<State title="Source library is empty" description="Use Research discovery to find and save provider-backed candidates."/>}</Card></>;
}

function Literature(){
  const {projectId}=useCtx();
  const q=useQuery({queryKey:["literature",projectId],queryFn:()=>api.literature(projectId!),enabled:Boolean(projectId)});
  return <><Head route="literature"/><div className="grid grid-2"><Card><h3>Literature payload</h3><pre className="code" style={{whiteSpace:"pre-wrap",fontSize:11}}>{JSON.stringify(q.data??{},null,2)}</pre></Card><Card><h3>Pipeline</h3><div className="timeline"><div className="step"><div className="dot"/><b>Discovery</b><div className="meta">Provider search, pagination and deduplication.</div></div><div className="step"><div className="dot"/><b>Analysis</b><div className="meta">Clusters, themes and gaps.</div></div><div className="step"><div className="dot"/><b>Screening</b><div className="meta">Human screening overrides are persisted.</div></div></div></Card></div></>;
}

function Evidence(){
  const {reportId}=useCtx();
  const q=useQuery({queryKey:["evidence",reportId],queryFn:()=>api.evidenceMatrix(reportId!),enabled:Boolean(reportId)});
  return <><Head route="evidence" actions={<Link className="btn" href="/generate">Use in generation</Link>}/><Card><div className="table-wrap"><table className="table"><thead><tr><th>Claim</th><th>Relation</th><th>Confidence</th><th>Source</th></tr></thead><tbody>{rows(q.data).map((x,i)=><tr key={i}><td>{value(x.claim??x.text)}</td><td>{value(x.support??x.relation)}</td><td>{value(x.confidence?.toString())}</td><td className="mono">{value(x.source_id)}</td></tr>)}</tbody></table></div>{!reportId&&<State title="No active report" description="Evidence is scoped to a report."/>}{reportId&&!q.isPending&&rows(q.data).length===0&&<State title="No claims yet" description="Claims and evidence will appear after retrieval/evidence processing."/>}</Card></>;
}

function Knowledge(){
  const {projectId}=useCtx();
  const q=useQuery({queryKey:["kg",projectId],queryFn:()=>api.knowledgeGraph(projectId!),enabled:Boolean(projectId)});
  const ex=useMutation({mutationFn:(f:"json"|"csv")=>api.knowledgeGraphExport(projectId!,f)});
  return <><Head route="knowledge" actions={<><button className="btn" disabled={!projectId||ex.isPending} onClick={()=>ex.mutate("json")}>Export JSON</button><button className="btn" disabled={!projectId||ex.isPending} onClick={()=>ex.mutate("csv")}>Export CSV</button></>}/><div className="grid grid-2"><Card><div className="graph">{rows((q.data as Obj|null)?.nodes).slice(0,18).map((n,i)=><div key={i} className={"node"+(i===0?" main":"")} style={{left:(8+(i*17)%82)+"%",top:(12+(i*23)%76)+"%"}}>{value(n.label??n.name)}</div>)}</div></Card><Card><pre className="code" style={{whiteSpace:"pre-wrap",fontSize:11}}>{JSON.stringify(q.data??{},null,2)}</pre></Card></div></>;
}

function Files(){
  const {projectId}=useCtx();
  const q=useQuery({queryKey:["files",projectId],queryFn:()=>api.files(projectId!),enabled:Boolean(projectId),refetchInterval:5000});
  const folders=useQuery({queryKey:["folders",projectId],queryFn:()=>api.folders(projectId!),enabled:Boolean(projectId)});
  const qc=useQueryClient();
  const [folderId,setFolderId]=useState("");
  const [uploading,setUploading]=useState(false);
  const [busyId,setBusyId]=useState("");
  const [error,setError]=useState("");

  async function upload(file:File){
    if(!projectId)return;
    setError("");
    setUploading(true);
    try{
      await api.uploadFile(projectId,file,folderId||undefined);
      await qc.invalidateQueries({queryKey:["files",projectId]});
    }catch(e){
      setError(e instanceof Error?e.message:"Upload failed.");
    }finally{
      setUploading(false);
    }
  }

  async function download(id:string,name:string){
    setBusyId(id);
    setError("");
    try{
      const response=await api.downloadFile(id);
      if(!response.ok){
        const body=await response.text().catch(()=> "");
        throw new Error(body||"Download failed.");
      }
      const blob=await response.blob();
      const url=URL.createObjectURL(blob);
      const link=document.createElement("a");
      link.href=url;
      link.download=name||"download";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    }catch(e){
      setError(e instanceof Error?e.message:"Download failed.");
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
  const files=rows(q.data?.items);

  return <><Head route="files"/>
    <div className="grid grid-3">
      <Card><h3>Folders</h3><div className="list">{rows(folders.data).map(f=><div className="list-item" key={value(f.id)}>{value(f.name)}</div>)}</div></Card>
      <Card><h3>Upload</h3>
        <select className="input" value={folderId} onChange={e=>setFolderId(e.target.value)}>
          <option value="">Project root</option>
          {rows(folders.data).map(f=><option key={value(f.id)} value={value(f.id)}>{value(f.name)}</option>)}
        </select>
        <label className="dropzone" style={{display:"grid",placeItems:"center",minHeight:140,marginTop:12}}>
          <input hidden type="file" disabled={!projectId||uploading} onChange={e=>{const f=e.target.files?.[0];if(f)void upload(f)}}/>
          <div><div className="strong">{uploading?"Uploading…":"Choose a file"}</div><div className="muted tiny">Backend validates size, MIME and authorization.</div></div>
        </label>
        {error&&<div className="notice error" style={{marginTop:10}}>{error}</div>}
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
              const name=value(f.original_filename,f.normalized_filename as string);
              const busy=busyId===id;
              return <tr key={id}>
                <td><div className="strong">{name}</div><div className="meta">{value(f.file_kind)}</div></td>
                <td>{value(f.status)}</td>
                <td>{typeof f.size_bytes==="number"?bytes(f.size_bytes):"—"}</td>
                <td><div className="actions">
                  <button className="btn" disabled={busy} onClick={()=>void download(id,name)}>{busy?"Working…":"Download"}</button>
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
  const qc=useQueryClient();const [objective,setObjective]=useState("");
  const save=useMutation({mutationFn:()=>api.savePlan(projectId!,{research_objective_snapshot:objective}),onSuccess:()=>{void qc.invalidateQueries({queryKey:["plan",projectId]})}});
  const validate=useMutation({mutationFn:()=>api.validatePlan(projectId!)});
  const current=row(q.data);
  return <><Head route="plan" actions={<button className="btn primary" disabled={!projectId||validate.isPending} onClick={()=>validate.mutate()}>{validate.isPending?"Validating…":"Validate plan"}</button>}/><div className="grid grid-2"><Card><h3>Objective</h3><textarea className="input textarea" value={objective||value(current.research_objective_snapshot,"")} onChange={e=>setObjective(e.target.value)} placeholder="Research objective…"/><button className="btn" style={{marginTop:12}} disabled={!projectId||save.isPending||!objective.trim()} onClick={()=>save.mutate()}>{save.isPending?"Saving…":"Save objective"}</button></Card><Card><h3>Current plan</h3><pre className="code" style={{whiteSpace:"pre-wrap",fontSize:11}}>{JSON.stringify(q.data??{},null,2)}</pre></Card></div><Card style={{marginTop:16}}><h3>Versions</h3><Table data={rows(row(v.data).items)}/>{validate.data?<div className="notice" style={{marginTop:12}}>{JSON.stringify(validate.data)}</div>:null}</Card></>;
}

function Manuscript(){
  const {reportId}=useCtx();
  const current=useQuery({queryKey:["manuscript",reportId],queryFn:()=>api.manuscript(reportId!),enabled:Boolean(reportId)});
  const draft=useQuery({queryKey:["draft",reportId],queryFn:()=>api.manuscriptDraft(reportId!),enabled:Boolean(reportId)});
  const qc=useQueryClient();const [content,setContent]=useState("");const [revision,setRevision]=useState(0);const [baseVersionId,setBaseVersionId]=useState<string|undefined>();const [dirty,setDirty]=useState(false);const [conflict,setConflict]=useState("");
  useEffect(()=>{if(draft.data){setRevision(draft.data.revision);setBaseVersionId(draft.data.base_version_id??undefined);setContent(JSON.stringify(draft.data.content??{},null,2));}},[draft.data]);
  useEffect(()=>{if(!dirty||!reportId)return;const t=window.setTimeout(async()=>{try{const parsed=JSON.parse(content);const res=await api.autosaveManuscript(reportId,{revision,content:parsed,base_version_id:baseVersionId});if(res.conflict){setConflict("A newer draft exists. Reload the authoritative draft before continuing.");setDirty(false);return;}setRevision(res.draft.revision);setBaseVersionId(res.draft.base_version_id??undefined);setDirty(false);setConflict("");await qc.invalidateQueries({queryKey:["draft",reportId]});}catch(e){setConflict(e instanceof Error?e.message:"Autosave failed.");}},700);return()=>window.clearTimeout(t);},[content,dirty,revision,baseVersionId,reportId,qc]);
  const saveVersion=useMutation({mutationFn:()=>api.saveManuscriptVersion(reportId!,{expected_revision:revision})});
  const ms=row(current.data);const ver=row(ms.version);
  return <><Head route="manuscript" actions={<><span className="tag">{dirty?"Saving…":"Autosaved"}</span><button className="btn" disabled={!reportId||saveVersion.isPending} onClick={()=>saveVersion.mutate()}>{saveVersion.isPending?"Saving…":"Save version"}</button></>}/>{conflict&&<div className="notice error" style={{marginBottom:14}}>{conflict}</div>}<div className="editor"><div className="row"><div><div className="title">{value(ver.title,"Untitled manuscript")}</div><div className="meta">Version {value(ver.version?.toString())}</div></div><Link className="btn" href="/evidence">Evidence</Link></div><div className="field" style={{marginTop:18}}><label>Draft document</label><textarea className="input textarea" style={{minHeight:520,fontFamily:"var(--mono)",fontSize:12}} value={content} onChange={e=>{setContent(e.target.value);setDirty(true)}} disabled={!reportId}/></div></div></>;
}

function Generate(){
  const {reportId}=useCtx();const [brief,setBrief]=useState("");const m=useMutation({mutationFn:()=>api.enqueueJob("generate_report",{report_id:reportId,brief},reportId)});
  return <><Head route="generate"/><div className="grid grid-2"><Card><div className="field"><label>Generation brief</label><textarea className="input textarea" value={brief} onChange={e=>setBrief(e.target.value)} placeholder="Draft Methods, Discussion, Abstract or Reviewer Response…"/></div><div className="pillbar" style={{marginTop:12}}><span className="tag primary">Evidence grounded</span><span className="tag">Verified evidence</span><span className="tag">Unsupported claim flag</span></div><button className="btn primary" style={{marginTop:14}} disabled={!reportId||m.isPending} onClick={()=>m.mutate()}>{m.isPending?"Queueing…":"Generate"}</button>{m.isError&&<div className="notice error" style={{marginTop:12}}>Generation request failed.</div>}{m.data&&<div className="notice success" style={{marginTop:12}}>Job queued: {value((m.data as Obj).id??(m.data as Obj).job_id)}</div>}</Card><Card><h3>Context</h3><div className="list"><div className="list-item">Evidence matrix</div><div className="list-item">Research plan</div><div className="list-item">Current report</div><div className="list-item">Durable job state</div></div></Card></div></>;
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
  const qc=useQueryClient();
  const [comment,setComment]=useState("");
  const [reviewTitle,setReviewTitle]=useState("");
  const addComment=useMutation({mutationFn:()=>api.addManuscriptComment(reportId!,versionId,{body:comment}),onSuccess:()=>{setComment("");void qc.invalidateQueries({queryKey:["comments",reportId,versionId]})}});
  const addReview=useMutation({mutationFn:()=>api.createReviewTask(reportId!,versionId,{manuscript_version_id:versionId,title:reviewTitle,severity:"info"}),onSuccess:()=>{setReviewTitle("");void qc.invalidateQueries({queryKey:["reviews",reportId,versionId]})}});
  return <><Head route="collaboration"/><div className="grid grid-2">
    <Card><h3>Comments</h3><textarea className="input textarea" style={{minHeight:130,marginTop:12}} value={comment} onChange={e=>setComment(e.target.value)} placeholder="Add a review comment…"/><button className="btn primary" style={{marginTop:10}} disabled={!versionId||!comment.trim()||addComment.isPending} onClick={()=>addComment.mutate()}>{addComment.isPending?"Posting…":"Add comment"}</button><div className="list" style={{marginTop:14}}>{rows(comments.data?.items).map(x=><div className="list-item" key={value(x.id)}><div className="title">{value(x.body)}</div><div className="meta">{value(x.status)} · {value(x.author_user_id)}</div></div>)}</div></Card>
    <Card><h3>Review tasks</h3><div className="row" style={{marginTop:12}}><input className="input" value={reviewTitle} onChange={e=>setReviewTitle(e.target.value)} placeholder="Review task title"/><button className="btn" disabled={!versionId||!reviewTitle.trim()||addReview.isPending} onClick={()=>addReview.mutate()}>{addReview.isPending?"Creating…":"Create"}</button></div><div className="list" style={{marginTop:14}}>{rows(reviews.data?.items).map(x=><div className="list-item" key={value(x.id)}><div className="row"><div><div className="title">{value(x.title)}</div><div className="meta">{value(x.status)} · {value(x.severity)}</div></div><span className="tag">{value(x.assignee_user_id,"Unassigned")}</span></div></div>)}</div></Card>
  </div><Card style={{marginTop:16}}><h3>Workspace</h3><div className="muted small">Review actions are tenant-scoped by the backend. Current manuscript version: <span className="mono">{versionId||"—"}</span> · Workspace: <span className="mono">{ws.workspaceId||"—"}</span></div></Card></>;
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

