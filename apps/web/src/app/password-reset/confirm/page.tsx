import { Suspense } from "react";
import PasswordResetConfirmForm from "./PasswordResetConfirmForm";

function PasswordResetConfirmFallback() {
  return (
    <main className="min-h-screen grid place-items-center px-6">
      <div className="card w-full max-w-md p-7 space-y-5">
        <h1 className="text-2xl font-semibold">Set new password</h1>

        <input
          className="input"
          disabled
          placeholder="Reset token"
        />

        <input
          className="input"
          type="password"
          disabled
          placeholder="New password"
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

export default function PasswordResetConfirmPage() {
  return (
    <Suspense fallback={<PasswordResetConfirmFallback />}>
      <PasswordResetConfirmForm />
    </Suspense>
  );
}