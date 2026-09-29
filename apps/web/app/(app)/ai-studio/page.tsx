import type { Metadata } from "next";
import { redirect } from "next/navigation";

export const metadata: Metadata = { title: "AI Studio · Research AI" };

export default function AIStudioPage() {
  redirect("/generate");
}
