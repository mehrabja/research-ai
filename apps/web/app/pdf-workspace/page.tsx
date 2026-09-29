import { Suspense } from "react";
import PDFWorkspace from "@/components/PDFWorkspace";
import { ResearchContextProvider } from "@/lib/research-context";

export default function Page() {
  return (
    <Suspense
      fallback={
        <main className="container">
          <section className="card pad" aria-busy="true">
            Loading PDF workspace…
          </section>
        </main>
      }
    >
      <ResearchContextProvider>
        <main className="container">
          <PDFWorkspace />
        </main>
      </ResearchContextProvider>
    </Suspense>
  );
}
