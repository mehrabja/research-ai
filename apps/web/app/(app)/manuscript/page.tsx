import type { Metadata } from "next";
import ManuscriptView from "@/components/ManuscriptView";

export const metadata: Metadata = {
  title: "Manuscript · Research AI",
};

export default function ManuscriptPage() {
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Manuscript</div>
          <h1>Manuscript</h1>
          <p>Inspect the current manuscript architecture, prose and version history for a research report.</p>
        </div>
      </div>
      <ManuscriptView />
    </>
  );
}
