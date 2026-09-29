"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

async function verifyEmail(token: string): Promise<string> {
  const response = await fetch("/api/v1/auth/verify-email", {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({ token }),
  });
  const payload = (await response.json().catch(() => ({}))) as {
    detail?: string;
    message?: string;
  };
  if (!response.ok) {
    throw new Error(payload.detail || payload.message || "Verification failed.");
  }
  return "Your email address is verified.";
}

async function resendVerification(email: string): Promise<string> {
  const response = await fetch("/api/v1/auth/verification/resend", {
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
    throw new Error(payload.detail || payload.message || "Unable to send verification email.");
  }
  return payload.message || "Verification instructions were requested.";
}

export default function EmailVerifyPage() {
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<"idle" | "working" | "success" | "error">("idle");
  const [message, setMessage] = useState("");
  const [email, setEmail] = useState(searchParams.get("email") || "");

  useEffect(() => {
    const token = searchParams.get("token");
    if (!token) return;

    setStatus("working");
    void verifyEmail(token)
      .then((result) => {
        setStatus("success");
        setMessage(result);
      })
      .catch((error) => {
        setStatus("error");
        setMessage(error instanceof Error ? error.message : "Verification failed.");
      });
  }, [searchParams]);

  async function submitResend(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStatus("working");
    setMessage("");
    try {
      const result = await resendVerification(email);
      setStatus("success");
      setMessage(result);
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Unable to send verification email.");
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
          <h2>Verify your email</h2>
          <p className="muted">
            Use the link sent to your email address to verify your Research-AI account.
          </p>

          {status === "working" && (
            <p className="muted" role="status">Processing…</p>
          )}
          {message && (
            <p
              role={status === "error" ? "alert" : "status"}
              style={{ color: status === "error" ? "var(--danger)" : undefined }}
            >
              {message}
            </p>
          )}

          {status !== "working" && searchParams.get("token") == null && (
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
              <button className="btn primary" type="submit" disabled={!email}>
                Send verification email
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
