import type { Metadata } from "next";
import GenerateStudio from "@/components/GenerateStudio";

export const metadata: Metadata = {
  title: "AI Studio · Research AI",
};

export default function GeneratePage() {
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">AI Studio</div>
          <h1>Generate with evidence</h1>
          <p>Run the real manuscript architecture and evidence-grounded prose pipelines.</p>
        </div>
      </div>
      <GenerateStudio />
    </>
  );
}
