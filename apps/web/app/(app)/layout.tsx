"use client";

import {
  Suspense,
  useState,
  type ReactNode,
} from "react";
import { Sidebar } from "@/components/AppShell/Sidebar";
import { Topbar } from "@/components/AppShell/Topbar";
import { Breadcrumbs } from "@/components/AppShell/Breadcrumbs";
import { ResearchContextProvider } from "@/lib/research-context";

export default function AppGroupLayout({
  children,
}: {
  children: ReactNode;
}) {
  const [mobileOpen, setMobileOpen] =
    useState(false);

  return (
    <Suspense
      fallback={
        <main
          className="main shell-gate"
          aria-busy="true"
        >
          <section className="card pad shell-gate-card">
            <div className="eyebrow">
              Research AI
            </div>
            <h1>
              Loading your research workspace…
            </h1>
          </section>
        </main>
      }
    >
      <ResearchContextProvider>
        <div className="app">
          <Sidebar
            open={mobileOpen}
            onClose={() => setMobileOpen(false)}
          />
          <main className="main">
            <Topbar
              mobileMenuOpen={mobileOpen}
              onMenuClick={() =>
                setMobileOpen((value) => !value)
              }
            />
            <div className="content">
              <Breadcrumbs />
              {children}
            </div>
          </main>
        </div>
      </ResearchContextProvider>
    </Suspense>
  );
}
