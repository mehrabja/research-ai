import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { ToastProvider } from "@/components/ToastProvider";


export const metadata: Metadata = {
  title: {
    default: "Research AI — Research workspace",
    template: "%s · Research AI",
  },
  description:
    "Discover literature, collect evidence, connect your files and code, plan your study, and draft a manuscript inside one research workspace.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
        <ToastProvider />
      </body>
    </html>
  );
}
