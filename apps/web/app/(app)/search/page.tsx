import type { Metadata } from "next";
import GlobalSearchView from "@/components/GlobalSearchView";

export const metadata: Metadata = {
  title: "Search · Research AI",
};

export default function SearchPage() {
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Workspace</div>
          <h1>Global search</h1>
          <p>Search real persisted research data in the active workspace.</p>
        </div>
      </div>
      <GlobalSearchView />
    </>
  );
}
