"use client";

import { useState, type FormEvent } from "react";
import { useSearchParams } from "next/navigation";

export default function EmailVerifyForm() {
  const params = useSearchParams();

  const [token, setToken] = useState(params.get("token") ?? "");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);

    const response = await fetch("/api/backend/auth/verify-email", {
      method: "POST",
      headers: {
        "content-type": "application/json",
      },
      body: JSON.stringify({ token }),
    });

    const body = await response.json().catch(() => ({}));

    setBusy(false);

    setMsg(
      response.ok
        ? "Email verified. You can sign in."
        : body?.error?.message ??
            body?.detail ??
            "Verification failed.",
    );
  }

  return (
    <main className="min-h-screen grid place-items-center px-6">
      <form
        onSubmit={submit}
        className="card w-full max-w-md p-7 space-y-5"
      >
        <h1 className="text-2xl font-semibold">Verify email</h1>

        <input
          className="input"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          placeholder="Verification token"
        />

        <button
          className="btn btn-primary w-full"
          disabled={busy || !token}
        >
          {busy ? "Verifying…" : "Verify"}
        </button>

        {msg && <div className="muted text-sm">{msg}</div>}

        <a className="muted text-xs underline" href="/login">
          Back to sign in
        </a>
      </form>
    </main>
  );
}