import Link from "next/link";
import { ROUTES } from "@/lib/routes";

export default function AppNotFound() {
  return (
    <main className="shell-gate">
      <section className="card pad shell-gate-card" role="status">
        <div className="eyebrow">Research workspace</div>
        <h1>Research page not found</h1>
        <p className="muted">
          This workspace route does not exist. Your active research context is
          still safe.
        </p>
        <div className="actions" style={{ justifyContent: "center", marginTop: 16 }}>
          <Link className="btn primary" href={ROUTES.dashboard}>
            Go to dashboard
          </Link>
          <Link className="btn" href={ROUTES.workspace}>
            Open workspace
          </Link>
        </div>
      </section>
    </main>
  );
}
