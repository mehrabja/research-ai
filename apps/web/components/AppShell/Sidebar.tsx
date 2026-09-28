"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAV_ITEMS } from "./nav-items";

export function Sidebar({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const pathname = usePathname();

  return (
    <>
      {open && (
        <div
          onClick={onClose}
          aria-hidden="true"
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(16,24,40,.35)",
            zIndex: 20,
          }}
          className="mobile-menu-backdrop"
        />
      )}
      <aside
        className="sidebar"
        data-open={open ? "true" : "false"}
      >
        <Link className="brand" href="/">
          <span className="brand-mark">R</span>
          <span>Research AI</span>
        </Link>
        <div className="workspace-switch">
          <div className="ws-row">
            <div className="avatar">NI</div>
            <div className="ws-info">
              <div className="strong" style={{ fontSize: 12 }}>
                Neural Research Lab
              </div>
              <div className="muted tiny">Role: Owner</div>
            </div>
            <span className="muted">⌄</span>
          </div>
        </div>
        <div className="nav-title">Workspace</div>
        <nav className="nav">
          {NAV_ITEMS.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={active ? "active" : ""}
                onClick={onClose}
              >
                <span className="icon">{item.icon}</span>
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
        <div className="sidebar-foot">
          <div className="upgrade">
            <div className="strong" style={{ fontSize: 12 }}>
              Pro plan
            </div>
            <div className="muted tiny" style={{ margin: "5px 0 9px" }}>
              74% of monthly credits used
            </div>
            <div className="progress">
              <span style={{ width: "74%" }} />
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}
