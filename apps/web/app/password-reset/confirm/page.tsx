"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

async function confirmPasswordReset(token: string, newPassword: string): Promise<string> {
  const response = await fetch("/api/v1/auth/password-reset/confirm", {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({ token, new_password: newPassword }),
  });
  const payload = (await response.json().catch(() => ({}))) as {
    detail?: string;
    message?: string;
  };
  if (!response.ok) {
    throw new Error(payload.detail || payload.message || "Unable to reset password.");
  }
  return "Password changed successfully. You can now log in.";
}

export default function PasswordResetConfirmPage() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") || "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [status, setStatus] = useState<"idle" | "working" | "success" | "error">("idle");
  const [message, setMessage] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (password.length < 15) {
      setStatus("error");
      setMessage("Password must be at least 15 characters.");
      return;
    }
    if (password !== confirm) {
      setStatus("error");
      setMessage("Passwords do not match.");
      return;
    }
    if (!token) {
      setStatus("error");
      setMessage("This password-reset link is missing its token.");
      return;
    }

    setStatus("working");
    setMessage("");
    try {
      setMessage(await confirmPasswordReset(token, password));
      setStatus("success");
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Unable to reset password.");
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
          <h2>Choose a new password</h2>
          <p className="muted">Use the secure link from the password-reset email.</p>

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
              <label htmlFor="new-password">New password</label>
              <input
                id="new-password"
                className="input"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="new-password"
                minLength={15}
                required
              />
            </div>
            <div className="field">
              <label htmlFor="confirm-password">Confirm password</label>
              <input
                id="confirm-password"
                className="input"
                type="password"
                value={confirm}
                onChange={(event) => setConfirm(event.target.value)}
                autoComplete="new-password"
                minLength={15}
                required
              />
            </div>
            <button className="btn primary" type="submit" disabled={status === "working"}>
              {status === "working" ? "Updating…" : "Update password"}
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
