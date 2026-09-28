import type { Metadata } from "next";
import LiteratureMap from "@/components/LiteratureMap";

export const metadata: Metadata = {
  title: "Literature · Research AI",
};

export default function LiteraturePage() {
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Literature map</h1>
          <p>
            Review the selected project&apos;s literature corpus, screening
            state, clusters and evidence gaps.
          </p>
        </div>
      </div>
      <LiteratureMap />
    </>
  );
}
