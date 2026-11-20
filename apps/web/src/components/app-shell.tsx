"use client";

import Link from "next/link";
import {usePathname,useRouter} from "next/navigation";
import {useEffect,useMemo,useState} from "react";
import {useQuery} from "@tanstack/react-query";
import {api} from "@/lib/api/client";

const nav=[
  ["/dashboard","⌂","Dashboard"],
  ["/workspace","◈","Workspace"],
  ["/projects","▦","Projects"],
  ["/research","⌕","Research discovery"],
  ["/rag","⌁","RAG retrieval"],
  ["/sources","◎","Sources"],
  ["/literature","▤","Literature"],
  ["/evidence","◇","Evidence"],
  ["/citations","◌","Citations"],
  ["/academic-qa","✓","Academic QA"],
  ["/classification","⊙","Classification"],
  ["/knowledge","✦","Knowledge graph"],
  ["/files","□","Files & intelligence"],
  ["/technical-intelligence","⌬","Technical intelligence"],
  ["/section-research","◍","Section research"],
  ["/publication","▣","Publication"],
  ["/orchestration","⚙","Orchestration"],
  ["/plan","☷","Research plan"],
  ["/manuscript","▥","Manuscript"],
  ["/generate","✧","AI Studio"],
  ["/humanize","≈","Humanize"],
  ["/translate","⇄","Translate"],
  ["/collaboration","◌","Collaboration"],
  ["/jobs","◷","Jobs"],
  ["/team","♙","Team"],
  ["/usage-billing","◫","Usage & billing"],
  ["/settings","⚙","Settings"],
] as const;

export function useWorkspace(){
  const {data}=useQuery({queryKey:["workspaces"],queryFn:api.workspaces});
  const [selected,setSelected]=useState<string|null>(null);
  useEffect(()=>{setSelected(localStorage.getItem("research_ai_workspace"));},[]);
  const workspaceId=useMemo(
    ()=>selected&&data?.items.some(w=>w.id===selected)
      ? selected
      : data?.items[0]?.id??null,
    [data,selected],
  );
  useEffect(()=>{
    if(workspaceId)localStorage.setItem("research_ai_workspace",workspaceId);
  },[workspaceId]);
  return {workspaces:data?.items??[],workspaceId,setSelected};
}

function initials(email:string){
  return email.split("@")[0].slice(0,2).toUpperCase();
}

export function AppShell({userEmail,children}:{userEmail:string;children:React.ReactNode}){
  const pathname=usePathname();
  const router=useRouter();
  const ws=useWorkspace();
  const notifications=useQuery({
    queryKey:["notifications",ws.workspaceId],
    queryFn:()=>api.notifications(ws.workspaceId!),
    enabled:Boolean(ws.workspaceId),
    refetchInterval:30000,
  });

  async function logout(){
    await fetch("/api/auth/logout",{method:"POST"});
    router.replace("/login");
    router.refresh();
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <Link className="brand" href="/">
          <span className="brand-mark">R</span><span>Research AI</span>
        </Link>
        <div className="workspace-switch">
          <div className="ws-row">
            <div className="avatar">{initials(userEmail)}</div>
            <div className="ws-info">
              <div className="strong" style={{fontSize:12}}>
                {ws.workspaces.find(w=>w.id===ws.workspaceId)?.name??"Workspace"}
              </div>
              <div className="muted tiny">
                Role: {ws.workspaces.find(w=>w.id===ws.workspaceId)?.role??"—"}
              </div>
            </div>
            <select
              aria-label="Workspace"
              value={ws.workspaceId??""}
              onChange={e=>ws.setSelected(e.target.value)}
              className="workspace-select"

            >
              {ws.workspaces.map(w=><option key={w.id} value={w.id}>{w.name}</option>)}
            </select>
          </div>
        </div>
        <div className="nav-title">Workspace</div>
        <nav className="nav">
          {nav.map(([href,icon,label])=>(
            <Link key={href} href={href} className={pathname===href||pathname.startsWith(href+"/")?"active":""}>
              <span className="icon">{icon}</span><span>{label}</span>
            </Link>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div className="upgrade">
            <div className="strong" style={{fontSize:12}}>Production workspace</div>
            <div className="muted tiny" style={{margin:"5px 0 9px"}}>
              Usage and limits are read from the backend.
            </div>
          </div>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div className="topbar-left">
            <button className="btn ghost mobile-menu" type="button" onClick={()=>document.body.classList.toggle("nav-open")}>☰</button>
            <SearchBox/>
            <span className="tag">⌘ K</span>
          </div>
          <div className="topbar-right">
            <span className="tag success">API connected</span>
            <Link className="btn ghost" href="/settings#notifications" aria-label="Notifications">
              🔔{(notifications.data?.unread??0)>0 && <span className="notification-badge">{notifications.data?.unread}</span>}
            </Link>
            <div className="avatar">{initials(userEmail)}</div>
            <button className="btn ghost" onClick={logout}>Sign out</button>
          </div>
        </header>
        <div className="content">{children}</div>
      </main>
    </div>
  );
}

function SearchBox(){
  const router=useRouter();
  const [value,setValue]=useState("");
  function submit(e:React.FormEvent){
    e.preventDefault();
    const q=value.trim();
    if(q)router.push("/research?q="+encodeURIComponent(q));
  }
  return <form onSubmit={submit} className="topbar-left" style={{gap:8}}>
    <input className="search" value={value} onChange={e=>setValue(e.target.value)} placeholder="Search papers, projects, evidence…" aria-label="Global search"/>
  </form>;
}
