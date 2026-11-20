"use client";

import Link from "next/link";
import { Suspense } from "react";
import type { Route } from "next";
import { useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { me } from "@/lib/api/auth";
import { acceptInvitation } from "@/lib/api/team";
import { isApiError } from "@/lib/api/errors";
import { ROUTES } from "@/lib/routes";

function InvitePageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token")?.trim() ?? "";

  const session = useQuery({
    queryKey: ["invite-session"],
    queryFn: me,
    retry: false,
  });

  const accept = useMutation({
    mutationFn: () => {
      if (!token) throw new Error("Invitation token is missing.");
      return acceptInvitation(token);
    },
    onSuccess: () => {
      router.replace(ROUTES.team);
      router.refresh();
    },
  });

  const loginHref = useMemo<Route>(() => {
    if (!token) return "/login";
    const next = `/invite?token=${encodeURIComponent(token)}`;
    return `/login?next=${encodeURIComponent(next)}` as Route;
  }, [token]);

  if (!token) {
    return (
      <main className="shell-gate">
        <section className="card pad shell-gate-card" role="alert">
          <div className="eyebrow">Research AI</div>
          <h1>Invitation link is incomplete</h1>
          <p className="muted">
            The invitation token is missing from this link.
          </p>
          <Link className="btn primary" href="/login" style={{ marginTop: 14 }}>
            Go to login
          </Link>
        </section>
      </main>
    );
  }

  const needsLogin =
    session.isError &&
    isApiError(session.error) &&
    session.error.status === 401;

  if (session.isPending) {
    return (
      <main className="shell-gate">
        <section className="card pad shell-gate-card" aria-busy="true">
          <div className="eyebrow">Research AI</div>
          <h1>Checking your invitation…</h1>
        </section>
      </main>
    );
  }

  if (session.isError && !needsLogin) {
    return (
      <main className="shell-gate">
        <section className="card pad shell-gate-card" role="alert">
          <h1>Unable to verify your session</h1>
          <p className="muted" style={{ marginTop: 8 }}>
            {session.error instanceof Error
              ? session.error.message
              : "Authentication service unavailable."}
          </p>
        </section>
      </main>
    );
  }

  if (session.isError) {
    return (
      <main className="shell-gate">
        <section className="card pad shell-gate-card">
          <div className="eyebrow">Workspace invitation</div>
          <h1>Sign in to accept this invitation</h1>
          <p className="muted" style={{ marginTop: 8 }}>
            Sign in with the email address that received the invitation, then
            return to this link.
          </p>
          <Link
            className="btn primary"
            href={loginHref}
            style={{ marginTop: 14 }}
          >
            Sign in
          </Link>
        </section>
      </main>
    );
  }

  return (
    <main className="shell-gate">
      <section className="card pad shell-gate-card">
        <div className="eyebrow">Workspace invitation</div>
        <h1>Join a Research AI workspace</h1>
        <p className="muted" style={{ marginTop: 8 }}>
          Signed in as <strong>{session.data?.email}</strong>.
        </p>

        {accept.error || accept.isSuccess ? (
          <p className="muted" role={accept.error ? "alert" : "status"} style={{ marginTop: 12 }}>
            {accept.error instanceof Error
              ? accept.error.message
              : "Invitation accepted. Redirecting to your team…"}
          </p>
        ) : null}

        <button
          className="btn primary"
          type="button"
          style={{ marginTop: 14 }}
          disabled={accept.isPending}
          onClick={() => accept.mutate()}
        >
          {accept.isPending ? "Accepting…" : "Accept invitation"}
        </button>
      </section>
    </main>
  );
}


export default function InvitePage() {
  return (
    <Suspense
      fallback={
        <main className="shell-gate">
          <section className="card pad shell-gate-card" aria-busy="true">
            <div className="eyebrow">Research AI</div>
            <h1>Checking your invitation…</h1>
          </section>
        </main>
      }
    >
      <InvitePageContent />
    </Suspense>
  );
}
