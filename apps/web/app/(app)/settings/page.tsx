import type { Metadata } from "next";
import { NotificationPreferencesView } from "@/components/NotificationPreferencesView";
import { SettingsSecurityView } from "@/components/SettingsSecurityView";
import { ProviderMatrixView } from "@/components/ProviderMatrixView";

export const metadata: Metadata = {
  title: "Settings · Research AI",
};

export default function SettingsPage() {
  return (
    <>
      <SettingsSecurityView />
      <NotificationPreferencesView />
      <div style={{ marginTop: 16 }}>
        <ProviderMatrixView />
      </div>
    </>
  );
}
