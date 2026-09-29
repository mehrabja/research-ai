"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Sidebar } from "@/components/AppShell/Sidebar";
import { Topbar } from "@/components/AppShell/Topbar";
import {
  clearSessionUserCache,
  syncSessionUser,
} from "@/lib/session-cache";

type AuthState = "checking" | "authenticated" | "error";

function SessionGate({
  children,
}: {
  children: React.ReactNode;
}) {
  const [authState, setAuthState] = useState<AuthState>("checking");
  const router = useRouter();
  const queryClient = useQueryClient();

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    async function verifySession() {
      try {
        const response = await fetch("/api/v1/auth/me", {
          method: "GET",
          credentials: "include",
          cache: "no-store",
          headers: {
            Accept: "application/json",
          },
          signal: controller.signal,
        });

        if (!active) {
          return;
        }

        if (response.ok) {
          const payload = (await response.json()) as {
            id?: unknown;
          };

          if (typeof payload.id !== "string") {
            clearSessionUserCache(queryClient);
            setAuthState("error");
            return;
          }

          syncSessionUser(queryClient, payload.id);
          setAuthState("authenticated");
          return;
        }

        if (response.status === 401) {
          clearSessionUserCache(queryClient);
          router.replace("/login");
          return;
        }

        setAuthState("error");
      } catch (error) {
        if (!active || controller.signal.aborted) {
          return;
        }

        console.error("Session verification failed:", error);
        setAuthState("error");
      }
    }

    void verifySession();

    return () => {
      active = false;
      controller.abort();
    };
  }, [queryClient, router]);

  if (authState === "checking") {
    return (
      <main
        className="main"
        aria-busy="true"
        aria-live="polite"
      >
        <div className="content">
          <section className="card pad">
            <h2>Checking your session…</h2>
            <p className="muted">
              Please wait while we verify your workspace session.
            </p>
          </section>
        </div>
      </main>
    );
  }

  if (authState === "error") {
    return (
      <main className="main">
        <div className="content">
          <section className="card pad">
            <h2>Unable to verify your session</h2>
            <p className="muted">
              The authentication service could not be reached. Please try
              again.
            </p>

            <button
              type="button"
              className="btn primary"
              onClick={() => window.location.reload()}
            >
              Try again
            </button>
          </section>
        </div>
      </main>
    );
  }

  return children;
}

export default function AppGroupLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const pathname = usePathname();

  return (
    <SessionGate key={pathname}>
      <div className="app">
        <Sidebar
          open={mobileOpen}
          onClose={() => setMobileOpen(false)}
        />

        <main className="main">
          <Topbar
            onMenuClick={() => setMobileOpen((value) => !value)}
          />

          <div className="content">{children}</div>
        </main>
      </div>
    </SessionGate>
  );
}
