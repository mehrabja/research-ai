import { headers } from "next/headers";
import { Suspense } from "react";
import { AppGroupShell } from "@/components/AppShell/AppGroupShell";
import PDFWorkspace from "@/components/PDFWorkspace";

export default async function Page() {
  await headers();
  return (
    <AppGroupShell>
      <Suspense
        fallback={
          <main className="container">
            <section className="card pad" aria-busy="true">
              Loading PDF workspace…
            </section>
          </main>
        }
      >
        <main className="container">
          <PDFWorkspace />
        </main>
      </Suspense>
    </AppGroupShell>
  );
}
