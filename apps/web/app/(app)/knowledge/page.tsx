import type { Metadata } from "next";
import KnowledgeGraphView from "@/components/KnowledgeGraphView";

export const metadata: Metadata = {
  title: "Knowledge graph · Research AI",
};

export default function KnowledgePage() {
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Knowledge graph</h1>
          <p>
            Inspect the persisted project graph, aggregate topology and
            provenance.
          </p>
        </div>
      </div>
      <KnowledgeGraphView />
    </>
  );
}
