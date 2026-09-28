import type { Metadata } from "next";
import FinalReviewStudio from "@/components/FinalReviewStudio";

export const metadata: Metadata = {
  title: "Final review · Research AI",
};

export default function FinalReviewPage() {
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Review gate</div>
          <h1>Final review</h1>
          <p>
            Review the post-translation humanized output before the final
            validation gate.
          </p>
        </div>
      </div>
      <FinalReviewStudio />
    </>
  );
}
