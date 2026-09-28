import type { Metadata } from "next";
import CitationsView from "@/components/CitationsView";

export const metadata: Metadata = {
  title: "Citations · Research AI",
};

export default function CitationsPage() {
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Citation engine</div>
          <h1>Citations & bibliography</h1>
          <p>Inspect persisted claims, citation links, validation and bibliography for a research report.</p>
        </div>
      </div>
      <CitationsView />
    </>
  );
}
