import Link from "next/link";
import type { Metadata } from "next";
import EvidenceMatrixView from "@/components/EvidenceMatrixView";

export const metadata: Metadata = {
  title: "Evidence · Research AI",
};

export default function EvidencePage() {
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Evidence</h1>
          <p>Inspect claims and source-linked evidence from the current citation run.</p>
        </div>
        <div className="actions">
          <Link className="btn" href="/citations">Citations</Link>
        </div>
      </div>
      <EvidenceMatrixView />
    </>
  );
}
