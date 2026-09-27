import { Suspense } from "react";
import EmailVerifyForm from "./EmailVerifyForm";

function EmailVerifyFallback() {
  return (
    <main className="min-h-screen grid place-items-center px-6">
      <div className="card w-full max-w-md p-7 space-y-5">
        <h1 className="text-2xl font-semibold">Verify email</h1>

        <input
          className="input"
          disabled
          placeholder="Verification token"
        />

        <button
          className="btn btn-primary w-full"
          disabled
        >
          Loading…
        </button>
      </div>
    </main>
  );
}

export default function EmailVerifyPage() {
  return (
    <Suspense fallback={<EmailVerifyFallback />}>
      <EmailVerifyForm />
    </Suspense>
  );
}