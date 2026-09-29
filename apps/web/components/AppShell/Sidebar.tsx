"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAV_ITEMS } from "./nav-items";
import { useResearchContext } from "@/lib/research-context";

function initials(email: string): string {
  const local = email.split("@")[0] ?? email;
  const clean = local.replace(/[^a-zA-Z0-9]/g, "");
  return clean.slice(0, 2).toUpperCase() || "R";
}

export function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const pathname = usePathname();
  const { user, workspace, project, contextHref } = useResearchContext();

  return <>
    {open && <div onClick={onClose} aria-hidden="true" className="mobile-menu-backdrop" style={{position:"fixed",inset:0,background:"rgba(16,24,40,.35)",zIndex:20}} />}
    <aside className="sidebar" data-open={open ? "true" : "false"}>
      <Link className="brand" href={contextHref("/dashboard")}>
        <span className="brand-mark">R</span><span>Research AI</span>
      </Link>
      <Link className="workspace-switch" href={contextHref("/workspace")} onClick={onClose} aria-label="Open selected research context">
        <div className="ws-row">
          <div className="avatar">{workspace ? initials(user.email) : "—"}</div>
          <div className="ws-info">
            <div className="strong" style={{fontSize:12}}>{workspace?.name ?? "No workspace"}</div>
            <div className="muted tiny">{workspace ? "Role: " + workspace.role : "Create or select a workspace"}</div>
            {project && <div className="muted tiny ws-project">{project.name}</div>}
          </div>
          <span className="muted" aria-hidden="true">↗</span>
        </div>
      </Link>
      <nav className="nav" aria-label="Primary navigation">
        {NAV_ITEMS.map((item, index) => {
          const showSection = index === 0 || NAV_ITEMS[index - 1]?.section !== item.section;
          const active = pathname === item.href || pathname.startsWith(item.href + "/");
          return <div key={item.href}>
            {showSection && <div className="nav-title">{item.section}</div>}
            <Link href={contextHref(item.href)} className={active ? "active" : ""} onClick={onClose} aria-current={active ? "page" : undefined}>
              <span className="icon" aria-hidden="true">{item.icon}</span><span>{item.label}</span>
            </Link>
          </div>;
        })}
      </nav>
      <div className="sidebar-foot">
        <div className="upgrade">
          <div className="strong" style={{fontSize:12}}>Usage & billing</div>
          <div className="muted tiny" style={{margin:"5px 0 9px"}}>View live plan, usage and subscription state.</div>
          <Link className="btn" href={contextHref("/usage-billing")} onClick={onClose}>Open billing</Link>
        </div>
      </div>
    </aside>
  </>;
}