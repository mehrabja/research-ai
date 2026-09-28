import type { Metadata } from "next";
import TranslationStudio from "@/components/TranslationStudio";
import PostTranslationHumanizationPanel from "@/components/PostTranslationHumanizationPanel";

export const metadata: Metadata = {
  title: "Translate · Research AI",
};

export default function TranslatePage() {
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Translation</div>
          <h1>Translate research content</h1>
          <p>Approve the backend-controlled pre-translation review and hand off the approved version to translation.</p>
        </div>
      </div>
      <TranslationStudio />
      <PostTranslationHumanizationPanel />
    </>
  );
}
