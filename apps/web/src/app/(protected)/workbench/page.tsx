"use client";
import {Suspense} from "react";
import {ScientificWorkbench} from "@/components/scientific-workbench";

export default function WorkbenchPage() {
  return <Suspense fallback={<div className="card state"><h3>Loading scientific workbench…</h3><p>Preparing project context and research tools.</p></div>}>
    <ScientificWorkbench/>
  </Suspense>;
}
