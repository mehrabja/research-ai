import Link from "next/link";

export default function CitationManager() {
  return (
    <section className="card pad">
      <div className="row">
        <div>
          <h2>Citation Manager</h2>
          <p className="muted small">
            Review persisted citation runs, claim support, validation and bibliography.
          </p>
        </div>
        <Link className="btn primary" href="/citations">Open citations</Link>
      </div>
    </section>
  );
}
