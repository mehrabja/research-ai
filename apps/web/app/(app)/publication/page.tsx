import type { Metadata } from "next";
import PublicationStudio from "@/components/PublicationStudio";

export const metadata: Metadata = {
  title: "Publication · Research AI",
};

export default function PublicationPage() {
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Phase 10</div>
          <h1>Publication & export</h1>
          <p>
            Validate a report against a stored publication target and create a
            submission-ready artifact from persisted report content.
          </p>
        </div>
      </div>
      <PublicationStudio />
    </>
  );
}
