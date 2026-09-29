import type { Metadata } from "next";
import Link from "next/link";
import ResearchDiscovery from "@/components/ResearchDiscovery";

export const metadata: Metadata = {
  title: "Research discovery · Research AI",
};

export default function ResearchPage() {
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Discovery</div>
          <h1>Research discovery</h1>
          <p>Search and triage relevant literature with source-aware filters.</p>
        </div>
        <div className="actions">
          <Link className="btn" href="/sources">
            Saved sources
          </Link>
          <Link className="btn primary" href="/jobs">
            New discovery job
          </Link>
        </div>
      </div>

      <ResearchDiscovery />

      <div className="grid grid-3" style={{ marginTop: 16 }}>
        <section className="card metric">
          <div className="label">Candidate papers</div>
          <div className="value">Live</div>
          <div className="delta">From the federated discovery API</div>
        </section>
        <section className="card metric">
          <div className="label">Advanced filters</div>
          <div className="value">On</div>
          <div className="delta">Year, citations, author, venue, type, language</div>
        </section>
        <section className="card metric">
          <div className="label">Evidence pipeline</div>
          <div className="value">Ready</div>
          <div className="delta">Extraction and file-to-evidence linkage are available</div>
        </section>
      </div>
    </>
  );
}
