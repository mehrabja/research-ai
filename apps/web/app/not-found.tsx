import Link from "next/link";
import { ROUTES } from "@/lib/routes";

export default function RootNotFound() {
  return (
    <main className="shell-gate">
      <section className="card pad shell-gate-card" role="status">
        <div className="eyebrow">Research AI</div>
        <h1>Page not found</h1>
        <p className="muted">
          The requested page does not exist or is no longer available.
        </p>
        <div className="actions" style={{ justifyContent: "center", marginTop: 16 }}>
          <Link className="btn primary" href={ROUTES.home}>
            Back to home
          </Link>
          <Link className="btn" href={ROUTES.login}>
            Sign in
          </Link>
        </div>
      </section>
    </main>
  );
}
