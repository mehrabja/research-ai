import type { Metadata } from "next";
import ResearchPlanView from "@/components/ResearchPlanView";

export const metadata: Metadata = {
  title: "Research plan · Research AI",
};

export default function PlanPage() {
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Planning</div>
          <h1>Research plan</h1>
          <p>
            Generate, validate, revise and inspect the persisted research plan
            for a project.
          </p>
        </div>
      </div>
      <ResearchPlanView />
    </>
  );
}
