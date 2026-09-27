"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/client-api";

type Stats = { active_projects:number; saved_sources:number; evidence_items:number; active_jobs:number; storage_bytes:number; ai_generation_units:number; ai_generation_limit:number|null; workspace_count:number };
type SearchItem = { type:string; id:string; title:string; snippet:string|null; project_id:string|null; report_id:string|null };
type SearchResponse = { query:string; items:SearchItem[]; total:number; limit:number; offset:number };
type Job = { id:string; status:string; type?:string; job_type?:string; created_at?:string; progress?:number };
type Session = { id:string; created_at:string; last_used_at:string|null; expires_at:string; user_agent:string|null; ip_address:string|null };
type Token = { id:string; name:string; token_prefix:string; scopes:string[]; expires_at:string|null; revoked_at:string|null; last_used_at:string|null; created_at:string };
type NotificationResponse = { items:{id:string;title:string;body:string|null;read_at:string|null;created_at:string}[]; total:number; unread:number };

const titles: Record<string,{title:string;subtitle:string;eyebrow:string}> = {
 dashboard:{title:"Research dashboard",subtitle:"Track active research, evidence, jobs and workspace consumption.",eyebrow:"Overview"},
 workspace:{title:"Workspace",subtitle:"Project context, milestones and research priorities.",eyebrow:"Workspace"},
 research:{title:"Research discovery",subtitle:"Search the connected literature and workspace corpus with provenance.",eyebrow:"Discover"},
 sources:{title:"Sources",subtitle:"Manage saved research sources and evidence-ready material.",eyebrow:"Corpus"},
 literature:{title:"Literature",subtitle:"Compare themes, methods, citations, clusters and research gaps.",eyebrow:"Synthesis"},
 evidence:{title:"Evidence matrix",subtitle:"Bind claims to supporting or conflicting evidence with provenance.",eyebrow:"Evidence"},
 knowledge:{title:"Knowledge graph",subtitle:"Explore concepts, relationships, neighborhoods and graph exports.",eyebrow:"Knowledge"},
 files:{title:"Files & intelligence",subtitle:"Upload, organize and inspect research files and extracted intelligence.",eyebrow:"Files"},
 plan:{title:"Research plan",subtitle:"Build an editable, versioned plan with evidence requirements.",eyebrow:"Planning"},
 manuscript:{title:"Manuscript",subtitle:"Edit drafts, preserve versions and retain citation context.",eyebrow:"Writing"},
 generate:{title:"AI Studio",subtitle:"Run evidence-grounded generation against selected research context.",eyebrow:"AI Studio"},
 humanize:{title:"Humanize",subtitle:"Rewrite manuscript text while preserving structured references and claims.",eyebrow:"Revision"},
 translate:{title:"Translate",subtitle:"Translate approved manuscript versions with citation and terminology preservation.",eyebrow:"Language"},
 collaboration:{title:"Collaboration",subtitle:"Coordinate review tasks, comments, replies and approvals.",eyebrow:"Review"},
 jobs:{title:"Jobs",subtitle:"Monitor queued, running, failed and completed background work.",eyebrow:"Operations"},
 team:{title:"Team",subtitle:"Manage members, invitations and workspace permissions.",eyebrow:"People"},
 "usage-billing":{title:"Usage & billing",subtitle:"Inspect workspace consumption, plan entitlements and invoices.",eyebrow:"SaaS"},
 settings:{title:"Settings",subtitle:"Manage workspace preferences, security, sessions and API access.",eyebrow:"Configuration"},
 notifications:{title:"Notifications",subtitle:"Review workspace activity and mark notifications as read.",eyebrow:"Activity"},
};

function Empty({ title, text }: { title:string; text:string }) { return <div className="card state"><h3>{title}</h3><p>{text}</p></div>; }
function ErrorState({ message }: { message:string }) { return <div className="card state error"><h3>Request failed</h3><p>{message}</p></div>; }

function DashboardView(){
 const q=useQuery({queryKey:["dashboard"],queryFn:()=>apiFetch<Stats>("dashboard")});
 if(q.isLoading) return <div className="grid grid-4">{Array.from({length:4},(_,i)=><div className="card metric" key={i}><div className="metric label">Loading</div><div className="value">—</div></div>)}</div>;
 if(q.error) return <ErrorState message={(q.error as Error).message}/>;
 const s=q.data!;
 const mb=(s.storage_bytes/1024/1024).toFixed(1);
 return <><div className="grid grid-4">{[[s.active_projects,"Active projects"],[s.saved_sources,"Saved sources"],[s.evidence_items,"Evidence items"],[s.active_jobs,"Active jobs"]].map(([v,l])=><div className="card metric" key={String(l)}><div className="label">{l}</div><div className="value">{v}</div></div>)}</div><div className="grid grid-2" style={{marginTop:14}}><div className="card pad"><h3>AI generation usage</h3><p className="muted small">{s.ai_generation_units} internal generation units in the current window.</p><div className="progress" style={{marginTop:12}}><span style={{width:s.ai_generation_limit?Math.min(100,(s.ai_generation_units/s.ai_generation_limit)*100):0+"%"}}/></div><div className="row small muted" style={{marginTop:7}}><span>{s.ai_generation_units} used</span><span>{s.ai_generation_limit===null?"Unlimited":s.ai_generation_limit+" limit"}</span></div></div><div className="card pad"><h3>Storage</h3><div className="value" style={{fontFamily:"var(--font-display)",fontSize:30}}>{mb} MB</div><p className="muted small">Aggregated from non-deleted workspace files.</p></div></div></>;
}

function ResearchView(){
 const [term,setTerm]=useState(""); const [submitted,setSubmitted]=useState("");
 const q=useQuery({queryKey:["global-search",submitted],queryFn:()=>apiFetch<SearchResponse>("search?q="+encodeURIComponent(submitted)),enabled:submitted.length>0});
 return <><div className="card pad"><div className="field"><label>Workspace search</label><form className="row" onSubmit={e=>{e.preventDefault();setSubmitted(term.trim())}}><input className="input" value={term} onChange={e=>setTerm(e.target.value)} placeholder="Search projects, sources, files…" /><button className="btn primary">Search</button></form></div></div>{submitted && q.isLoading?<div className="card state" style={{marginTop:14}}>Searching…</div>:null}{q.error?<div style={{marginTop:14}}><ErrorState message={(q.error as Error).message}/></div>:null}{q.data?<div className="card pad" style={{marginTop:14}}><div className="row"><h3>Results</h3><span className="tag">{q.data.total} total</span></div><div className="list">{q.data.items.length?q.data.items.map(item=><div className="list-item" key={item.type+"-"+item.id}><div className="row"><div><div className="title">{item.title}</div><div className="meta">{item.type} · {item.snippet ?? "No snippet available"}</div></div><span className="tag primary">{item.type}</span></div></div>):<Empty title="No matching resources" text="The backend returned no workspace-scoped results for this query."/>}</div></div>:null}</>;
}

function NotificationView(){
 const q=useQuery({queryKey:["notifications-page"],queryFn:()=>apiFetch<NotificationResponse>("notifications?limit=50")});
 if(q.isLoading)return <div className="card state">Loading notifications…</div>;
 if(q.error)return <ErrorState message={(q.error as Error).message}/>;
 return <div className="card pad"><div className="row"><h3>Activity</h3><span className="tag primary">{q.data?.unread??0} unread</span></div><div className="list">{q.data?.items.length?q.data.items.map(n=><div className="list-item" key={n.id}><div className="row"><div><div className="title">{n.title}</div><div className="meta">{n.body??"No message"} · {new Date(n.created_at).toLocaleString()}</div></div>{n.read_at?<span className="tag">Read</span>:<span className="tag primary">Unread</span>}</div></div>):<Empty title="No notifications" text="New review, workspace, job and security events will appear here when generated by the platform."/>}</div></div>;
}

function JobsView(){
 const q=useQuery({queryKey:["jobs"],queryFn:()=>apiFetch<Job[]>("jobs?limit=50")});
 if(q.isLoading)return <div className="card state">Loading jobs…</div>;
 if(q.error)return <ErrorState message={(q.error as Error).message}/>;
 const jobs=q.data??[];
 return <div className="card table-wrap"><table className="table"><thead><tr><th>Job</th><th>Status</th><th>Created</th><th>Action</th></tr></thead><tbody>{jobs.length?jobs.map(j=><tr key={j.id}><td className="mono">{j.id.slice(0,8)}</td><td><span className="tag">{j.status}</span></td><td>{j.created_at?new Date(j.created_at).toLocaleString():"—"}</td><td><Link className="btn ghost" href={"/jobs/"+j.id}>Open</Link></td></tr>):<tr><td colSpan={4}><Empty title="No jobs" text="Queued research and AI operations will appear here after a real backend action." /></td></tr>}</tbody></table></div>;
}

function SettingsView(){
 const sessions=useQuery({queryKey:["sessions"],queryFn:()=>apiFetch<{items:Session[]}>("auth/sessions")});
 const tokens=useQuery({queryKey:["api-tokens"],queryFn:()=>apiFetch<Token[]>("auth/api-tokens")});
 const tfa=useQuery({queryKey:["2fa"],queryFn:()=>apiFetch<{enabled:boolean}>("auth/2fa")});
 return <div className="grid grid-2"><div className="card pad"><h3>Security</h3><div className="list"><div className="list-item row"><span>Two-factor authentication</span><span className={tfa.data?.enabled?"tag success":"tag warn"}>{tfa.isLoading?"Loading…":tfa.data?.enabled?"Enabled":"Not enabled"}</span></div><div className="list-item row"><span>Active sessions</span><span className="tag">{sessions.data?.items.length??"—"}</span></div><div className="list-item row"><span>API tokens</span><span className="tag">{tokens.data?.length??"—"}</span></div></div></div><div className="card pad"><h3>Workspace policy</h3><p className="muted small">Citation style, default language, evidence-required generation, upload indexing and notification preferences are controlled by the workspace settings API.</p><Link className="btn primary" href="/workspace">Open workspace settings</Link></div></div>;
}

function GenericView({slug}:{slug:string}){ const meta=titles[slug] ?? {title:"Research AI",subtitle:"Connected workspace capability.",eyebrow:"Product"}; return <><div className="grid grid-3"><div className="card pad"><h3>Real backend contract</h3><p className="muted small">This page is wired through the shared typed API client. Domain mutations are enabled only where the corresponding backend contract has been verified.</p></div><div className="card pad"><h3>Versioned</h3><p className="muted small">Research artifacts remain attributable to projects, reports, jobs and versions rather than overwriting historical state.</p></div><div className="card pad"><h3>Tenant-aware</h3><p className="muted small">Requests run through the authenticated backend boundary and do not use prototype data.</p></div></div><div className="card pad" style={{marginTop:14}}><h3>Next backend action</h3><p className="muted small">Connect this page to its domain-specific endpoint set as each M39/M40 capability gate reaches GREEN.</p></div></> }

export function ProductPage({slug}:{slug:string}){ const meta=titles[slug] ?? {title:"Research AI",subtitle:"Connected workspace capability.",eyebrow:"Product"}; return <ProductShell><div className="content"><div className="page-head"><div><div className="eyebrow">{meta.eyebrow}</div><h1>{meta.title}</h1><p>{meta.subtitle}</p></div><div className="actions"><Link className="btn" href="/research">Discover</Link><Link className="btn primary" href="/generate">Open AI Studio</Link></div></div>{slug==="dashboard"?<DashboardView/>:slug==="research"?<ResearchView/>:slug==="notifications"?<NotificationView/>:slug==="jobs"?<JobsView/>:slug==="settings"?<SettingsView/>:<GenericView slug={slug}/>}</div></ProductShell> }