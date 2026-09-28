import type { Metadata } from "next";
import FilesWorkspace from "@/components/FilesWorkspace";

export const metadata: Metadata = {
  title: "Files & intelligence · Research AI",
};

export default function FilesPage() {
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Files & intelligence</h1>
          <p>
            Upload and manage files in a real project workspace.
          </p>
        </div>
      </div>
      <FilesWorkspace />
    </>
  );
}
