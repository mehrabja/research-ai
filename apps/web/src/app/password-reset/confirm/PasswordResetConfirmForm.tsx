"use client";

import { useState, type FormEvent } from "react";
import { useSearchParams } from "next/navigation";

export default function PasswordResetConfirmForm() {
  const params = useSearchParams();

  const [token, setToken] = useState(params.get("token") ?? "");
  const [password, setPassword] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();

    if (password.length < 15) {
      setMsg("Password must be at least 15 characters.");
      return;
    }

    setBusy(true);

    const response = await fetch(
      "/api/backend/auth/password-reset/confirm",
      {
        method: "POST",
        headers: {
          "content-type": "application/json",
        },
        body: JSON.stringify({
          token,
          new_password: password,
        }),
      },
    );

    const body = await response.json().catch(() => ({}));

    setBusy(false);

    setMsg(
      response.ok
        ? "Password updated. You can sign in."
        : body?.error?.message ??
            body?.detail ??
            "Reset failed.",
    );
  }

  return (
    <main className="min-h-screen grid place-items-center px-6">
      <form
        onSubmit={submit}
        className="card w-full max-w-md p-7 space-y-5"
      >
        <h1 className="text-2xl font-semibold">Set new password</h1>

        <input
          className="input"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          placeholder="Reset token"
        />

        <input
          className="input"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="New password"
          autoComplete="new-password"
        />

        <button
          className="btn btn-primary w-full"
          disabled={busy || !token || !password}
        >
          {busy ? "Updating…" : "Update password"}
        </button>

        {msg && <div className="muted text-sm">{msg}</div>}

        <a className="muted text-xs underline" href="/login">
          Back to sign in
        </a>
      </form>
    </main>
  );
}