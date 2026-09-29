"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";

async function requestPasswordReset(email: string): Promise<string> {
  const response = await fetch("/api/v1/auth/password-reset/request", {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({ email }),
  });
  const payload = (await response.json().catch(() => ({}))) as {
    detail?: string;
    message?: string;
  };
  if (!response.ok) {
    throw new Error(payload.detail || payload.message || "Unable to request password reset.");
  }
  return payload.message || "If the account exists, password-reset instructions will be sent.";
}

export default function PasswordResetRequestPage() {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "working" | "success" | "error">("idle");
  const [message, setMessage] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStatus("working");
    setMessage("");
    try {
      setMessage(await requestPasswordReset(email));
      setStatus("success");
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Unable to request password reset.");
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-main" style={{ width: "100%" }}>
        <div className="auth-card">
          <Link className="brand" href="/" style={{ padding: "0 0 8px" }}>
            <span className="brand-mark">R</span>
            <span>Research AI</span>
          </Link>
          <h2>Reset your password</h2>
          <p className="muted">
            Enter your account email. We will send reset instructions when the account is eligible.
          </p>

          {message && (
            <p
              role={status === "error" ? "alert" : "status"}
              style={{ color: status === "error" ? "var(--danger)" : undefined }}
            >
              {message}
            </p>
          )}

          <form className="auth-form" onSubmit={submit} noValidate>
            <div className="field">
              <label htmlFor="reset-email">Email</label>
              <input
                id="reset-email"
                className="input"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                autoComplete="email"
                required
              />
            </div>
            <button className="btn primary" type="submit" disabled={status === "working" || !email}>
              {status === "working" ? "Sending…" : "Send reset email"}
            </button>
          </form>

          <div className="hint" style={{ marginTop: 14 }}>
            <Link href="/login">Return to login</Link>
          </div>
        </div>
      </section>
    </main>
  );
}
