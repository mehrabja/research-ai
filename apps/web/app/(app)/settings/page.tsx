import type { Metadata } from "next";
import { SettingsSecurityView } from "@/components/SettingsSecurityView";

export const metadata: Metadata = {
  title: "Settings · Research AI",
};

export default function SettingsPage() {
  return <SettingsSecurityView />;
}
