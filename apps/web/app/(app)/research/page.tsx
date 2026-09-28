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
          <div className="delta">From federated provider search</div>
        </section>
        <section className="card metric">
          <div className="label">Duplicate suppression</div>
          <div className="value">On</div>
          <div className="delta good">DOI / title-year-author merge</div>
        </section>
        <section className="card metric">
          <div className="label">Evidence-ready</div>
          <div className="value">Next</div>
          <div className="delta">Full-text extraction in the next slice</div>
        </section>
      </div>
    </>
  );
}
