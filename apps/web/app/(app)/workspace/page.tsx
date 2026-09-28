import type { Metadata } from "next";
import WorkspaceProjects from "@/components/WorkspaceProjects";

export const metadata: Metadata = {
  title: "Workspace · Research AI",
};

export default function WorkspacePage() {
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Workspace</div>
          <h1>Projects and research context</h1>
          <p>
            Work with the real workspace and project records behind your
            research.
          </p>
        </div>
      </div>
      <WorkspaceProjects />
    </>
  );
}
