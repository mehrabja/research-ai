"use client";

import Link from "next/link";
import { useEffect } from "react";
import { ROUTES } from "@/lib/routes";

export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Keep the route error boundary silent by default. The existing
    // application telemetry can observe errors without leaking stack traces
    // into the UI.
    void error;
  }, [error]);

  return (
    <main className="shell-gate">
      <section className="card pad shell-gate-card" role="alert">
        <div className="eyebrow">Research AI</div>
        <h1>Something went wrong</h1>
        <p className="muted">
          This page could not be rendered. Your saved research data was not
          discarded.
        </p>
        <div className="actions" style={{ justifyContent: "center", marginTop: 16 }}>
          <button className="btn primary" type="button" onClick={() => reset()}>
            Try again
          </button>
          <Link className="btn" href={ROUTES.dashboard}>
            Go to dashboard
          </Link>
        </div>
      </section>
    </main>
  );
}
