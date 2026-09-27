"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/client-api";

type Workspace = { id: string; name: string; slug: string };
type NotificationResponse = { unread: number };

const nav = [
  ["Core", [["/dashboard","⌂","Dashboard"],["/workspace","W","Workspace"]]],
  ["Research", [["/research","R","Research"],["/sources","S","Sources"],["/literature","L","Literature"],["/evidence","E","Evidence"],["/knowledge","K","Knowledge"],["/files","F","Files & intelligence"],["/plan","P","Research plan"]]],
  ["Create", [["/manuscript","M","Manuscript"],["/generate","G","AI Studio"],["/humanize","H","Humanize"],["/translate","T","Translate"]]],
  ["Operate", [["/collaboration","C","Collaboration"],["/jobs","J","Jobs"],["/team","T","Team"],["/usage-billing","$","Usage & billing"],["/settings","⚙","Settings"]]],
] as const;

export function ProductShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { data: workspaces } = useQuery({ queryKey: ["workspaces"], queryFn: () => apiFetch<Workspace[]>("workspaces") });
  const { data: notifications } = useQuery({ queryKey: ["notifications"], queryFn: () => apiFetch<NotificationResponse>("notifications?limit=1") });
  const activeWorkspace = workspaces?.[0];
  const workspaceCount = workspaces?.length ?? 0;
  return (
    <div className="app">
      <aside className="sidebar">
        <Link className="brand" href="/dashboard"><span className="brand-mark">R</span><span>Research AI</span></Link>
        <div className="workspace-switch"><div className="ws-row"><div className="avatar">{(activeWorkspace?.name?.[0] ?? "R").toUpperCase()}</div><div className="ws-info" style={{minWidth:0}}><div className="small strong" style={{overflow:"hidden",textOverflow:"ellipsis"}}>{activeWorkspace?.name ?? "Workspace"}</div><div className="tiny muted">{workspaceCount} workspace{workspaceCount === 1 ? "" : "s"}</div></div><span className="tiny muted">⌄</span></div></div>
        <nav className="nav">{nav.map(([section, links]) => <div key={section}><div className="nav-title">{section}</div>{links.map(([href, icon, label]) => { const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(href + "/")); return <Link href={href} className={active ? "active" : ""} key={href}><span className="icon">{icon}</span><span>{label}</span></Link>; })}</div>)}</nav>
        <div className="sidebar-foot"><div className="upgrade"><div className="small strong">Research workspace</div><div className="tiny muted" style={{marginTop:3}}>Quota and provider policy come from the active workspace.</div></div></div>
      </aside>
      <main className="main">
        <header className="topbar"><div className="topbar-left"><Link href="/research"><input className="search" aria-label="Search" placeholder="Search projects, sources, files…" readOnly /></Link></div><div className="topbar-right"><Link className="btn ghost" href="/notifications">Bell {notifications?.unread ? <span className="notification-badge">{notifications.unread}</span> : null}</Link><Link className="avatar" href="/settings">RA</Link></div></header>
        {children}
      </main>
    </div>
  );
}