import { headers } from "next/headers";
import { Suspense } from "react";
import ResearchCanvas from "@/components/ResearchCanvas";
import { ResearchContextProvider } from "@/lib/research-context";

export default async function Page() {
  await headers();
  return (
    <Suspense fallback={<main className="container"><section className="card pad" aria-busy="true">Loading research canvas…</section></main>}>
      <ResearchContextProvider>
        <main className="container">
          <ResearchCanvas />
        </main>
      </ResearchContextProvider>
    </Suspense>
  );
}
