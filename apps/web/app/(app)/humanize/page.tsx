import type { Metadata } from "next";
import HumanizeStudio from "@/components/HumanizeStudio";

export const metadata: Metadata = {
  title: "Humanize · Research AI",
};

export default function HumanizePage() {
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Language studio</div>
          <h1>Humanize manuscript</h1>
          <p>Run and validate the persisted M32 manuscript humanization pipeline.</p>
        </div>
      </div>
      <HumanizeStudio />
    </>
  );
}
