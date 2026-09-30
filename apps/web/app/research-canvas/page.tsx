import { headers } from "next/headers";
import { Suspense } from "react";
import { AppGroupShell } from "@/components/AppShell/AppGroupShell";
import ResearchCanvas from "@/components/ResearchCanvas";

export default async function Page() {
  await headers();
  return (
    <AppGroupShell>
      <Suspense
        fallback={
          <main className="container">
            <section className="card pad" aria-busy="true">
              Loading research canvas…
            </section>
          </main>
        }
      >
        <main className="container">
          <ResearchCanvas />
        </main>
      </Suspense>
    </AppGroupShell>
  );
}
