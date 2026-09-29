"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

async function verifyEmail(token: string): Promise<string> {
  const response = await fetch("/api/v1/auth/verify-email", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ token }),
  });
  const payload = (await response.json().catch(() => ({}))) as {
    detail?: string;
    message?: string;
  };
  if (!response.ok) throw new Error(payload.detail || payload.message || "Verification failed.");
  return "Your email address is verified.";
}

async function resendVerification(email: string): Promise<string> {
  const response = await fetch("/api/v1/auth/verification/resend", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ email }),
  });
  const payload = (await response.json().catch(() => ({}))) as {
    detail?: string;
    message?: string;
  };
  if (!response.ok) throw new Error(payload.detail || payload.message || "Unable to send verification email.");
  return payload.message || "Verification instructions were requested.";
}

type EmailVerifyContentProps = {
  token: string;
  initialEmail: string;
};

function EmailVerifyContent({
  token,
  initialEmail,
}: EmailVerifyContentProps) {
  const [email, setEmail] = useState(initialEmail);

  const verification = useQuery({
    queryKey: ["email-verification", token],
    queryFn: () => verifyEmail(token),
    enabled: Boolean(token),
    retry: false,
  });

  const resend = useMutation({
    mutationFn: resendVerification,
  });

  const status =
    verification.isPending
      ? "working"
      : verification.isSuccess || resend.isSuccess
        ? "success"
        : verification.isError || resend.isError
          ? "error"
          : "idle";
  const message =
    verification.data ||
    (verification.error instanceof Error ? verification.error.message : "") ||
    resend.data ||
    (resend.error instanceof Error ? resend.error.message : "");

  function submitResend(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    resend.mutate(email);
  }

  return (
    <main className="auth-page">
      <section className="auth-main" style={{ width: "100%" }}>
        <div className="auth-card">
          <Link className="brand" href="/" style={{ padding: "0 0 8px" }}>
            <span className="brand-mark">R</span>
            <span>Research AI</span>
          </Link>
          <h2>Verify your email</h2>
          <p className="muted">
            Use the link sent to your email address to verify your Research-AI account.
          </p>

          {status === "working" && <p className="muted" role="status">Processing…</p>}
          {message && (
            <p
              role={status === "error" ? "alert" : "status"}
              style={{ color: status === "error" ? "var(--danger)" : undefined }}
            >
              {message}
            </p>
          )}

          {!token && (
            <form className="auth-form" onSubmit={submitResend} noValidate>
              <div className="field">
                <label htmlFor="verification-email">Email</label>
                <input
                  id="verification-email"
                  className="input"
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  autoComplete="email"
                  required
                />
              </div>
              <button className="btn primary" type="submit" disabled={!email || resend.isPending}>
                {resend.isPending ? "Sending…" : "Send verification email"}
              </button>
            </form>
          )}

          <div className="hint" style={{ marginTop: 14 }}>
            <Link href="/login">Return to login</Link>
          </div>
        </div>
      </section>
    </main>
  );
}

type EmailVerifyPageProps = {
  searchParams: Promise<{
    token?: string | string[];
    email?: string | string[];
  }>;
};

function firstParam(value: string | string[] | undefined): string {
  return Array.isArray(value) ? value[0] ?? "" : value ?? "";
}

export default async function EmailVerifyPage({
  searchParams,
}: EmailVerifyPageProps) {
  const params = await searchParams;

  return (
    <EmailVerifyContent
      token={firstParam(params.token)}
      initialEmail={firstParam(params.email)}
    />
  );
}
