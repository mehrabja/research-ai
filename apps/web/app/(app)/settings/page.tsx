import type { Metadata } from "next";
import { SettingsSecurityView } from "@/components/SettingsSecurityView";
import { ProviderMatrixView } from "@/components/ProviderMatrixView";

export const metadata: Metadata = {
  title: "Settings · Research AI",
};

export default function SettingsPage() {
  return (
    <>
      <SettingsSecurityView />
      <div style={{ marginTop: 16 }}>
        <ProviderMatrixView />
      </div>
    </>
  );
}
