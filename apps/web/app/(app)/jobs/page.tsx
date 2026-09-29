import type { Metadata } from "next";
import { JobsCenter } from "@/components/JobsCenter";

export const metadata: Metadata = {
  title: "Jobs · Research AI",
};

export default function JobsPage() {
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Async work</div>
          <h1>Job center</h1>
          <p>
            Track durable discovery, parsing, indexing, generation and
            export jobs from the backend queue.
          </p>
        </div>
      </div>
      <JobsCenter />
    </>
  );
}
