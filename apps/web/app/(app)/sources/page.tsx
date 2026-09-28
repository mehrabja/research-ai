import type { Metadata } from "next";
import SourcesLibrary from "@/components/SourcesLibrary";

export const metadata: Metadata = {
  title: "Sources · Research AI",
};

export default function SourcesPage() {
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Sources</h1>
          <p>Browse sources actually saved to a research report.</p>
        </div>
      </div>
      <SourcesLibrary />
    </>
  );
}
