import { headers } from "next/headers";
import type { ReactNode } from "react";
import { AppGroupShell } from "@/components/AppShell/AppGroupShell";

export default async function AppGroupLayout({
  children,
}: {
  children: ReactNode;
}) {
  // Nonce-based CSP is request-scoped. Reading request headers here opts the
  // entire protected route group into dynamic rendering, which allows Next.js
  // to apply the proxy-generated nonce to its SSR script tags.
  await headers();

  return <AppGroupShell>{children}</AppGroupShell>;
}
