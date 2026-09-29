import type { Metadata } from "next";
import { UsageBillingView } from "@/components/UsageBillingView";

export const metadata: Metadata = {
  title: "Usage & billing · Research AI",
};

export default function UsageBillingPage() {
  return <UsageBillingView />;
}
