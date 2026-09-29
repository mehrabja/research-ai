"use client";

import { useState } from "react";
import { Sidebar } from "@/components/AppShell/Sidebar";
import { Topbar } from "@/components/AppShell/Topbar";
import { Breadcrumbs } from "@/components/AppShell/Breadcrumbs";
import { ResearchContextProvider } from "@/lib/research-context";

export default function AppGroupLayout({ children }: { children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  return <ResearchContextProvider>
    <div className="app">
      <Sidebar open={mobileOpen} onClose={() => setMobileOpen(false)} />
      <main className="main">
        <Topbar onMenuClick={() => setMobileOpen((value) => !value)} />
        <div className="content">
          <Breadcrumbs />
          {children}
        </div>
      </main>
    </div>
  </ResearchContextProvider>;
}
