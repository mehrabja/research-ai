"use client";

import { useState } from "react";
import Link from "next/link";
import type { Route } from "next";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";

import {
  loginSchema,
  type LoginInput,
} from "@/lib/validation/auth";
import { login } from "@/lib/api/auth";

export default function LoginPage() {
  const router = useRouter();

  const {
    register,
    handleSubmit,
    watch,
    formState: {
      errors,
      isSubmitting,
    },
    setError,
  } = useForm<LoginInput>({
    resolver: zodResolver(loginSchema),
    mode: "onSubmit",
    defaultValues: {
      email: "",
      password: "",
    },
  });

  const loginMutation = useMutation({
    mutationFn: async (values: LoginInput) =>
      login(values.email, values.password),

    onSuccess: () => {
      router.replace("/dashboard");
    },

    onError: () => {
      setError("root", {
        message:
          "We couldn't sign you in. Check your email and password.",
      });
    },
  });

  const submitForm = handleSubmit((values) => {
    loginMutation.mutate(values);
  });

  const [submitted, setSubmitted] = useState(false);
  const emailValue = watch("email");
  const passwordValue = watch("password");

  const emailInvalid =
    Boolean(errors.email) || (submitted && !emailValue);
  const passwordInvalid =
    Boolean(errors.password) || (submitted && !passwordValue);

  const busy =
    isSubmitting || loginMutation.isPending;

  return (
    <div className="auth-page">
      <section className="auth-side">
        <Link className="brand" href="/">
          <span className="brand-mark">R</span>
          <span>Research AI</span>
        </Link>

        <div
          className="eyebrow"
          style={{ marginTop: 70 }}
        >
          Your research workspace
        </div>

        <h1>
          Continue where your evidence left off.
        </h1>

        <p>
          Keep papers, source notes, uploaded files,
          experiments and manuscript versions in one
          controlled workspace.
        </p>

        <div className="quote">
          <div className="tag success">
            Live workspace
          </div>

          <p
            style={{
              margin: "12px 0 0",
              color: "#c6d4e3",
            }}
          >
            &ldquo;The UI should make evidence
            traceability visible at every step.&rdquo;
          </p>

          <div
            className="muted small"
            style={{ marginTop: 10 }}
          >
            Research workflow principle
          </div>
        </div>
      </section>

      <section className="auth-main">
        <div className="auth-card">
          <Link
            className="brand"
            href="/"
            style={{ padding: "0 0 8px" }}
          >
            <span className="brand-mark">R</span>
            <span>Research AI</span>
          </Link>

          <h2>Welcome back</h2>

          <div className="muted">
            Sign in to your research workspace.
          </div>

          <form
            className="auth-form"
            onSubmit={submitForm}
            noValidate
          >
            <div className="field">
              <label htmlFor="email">
                Email
              </label>

              <input
                id="email"
                className="input"
                type="email"
                placeholder="you@lab.edu"
                autoComplete="email"
                aria-invalid={emailInvalid ? "true" : "false"}
                {...register("email")}
              />

              {errors.email && (
                <div
                  className="hint"
                  style={{
                    color: "var(--danger)",
                  }}
                >
                  {errors.email.message}
                </div>
              )}
            </div>

            <div className="field">
              <label htmlFor="password">
                Password
              </label>

              <input
                id="password"
                className="input"
                type="password"
                placeholder="••••••••"
                autoComplete="current-password"
                aria-invalid={passwordInvalid ? "true" : "false"}
                {...register("password")}
              />

              {errors.password && (
                <div
                  className="hint"
                  style={{
                    color: "var(--danger)",
                  }}
                >
                  {errors.password.message}
                </div>
              )}
            </div>

            <div className="row">
              <span aria-hidden="true" />
              <Link
                href={"/password-reset" as Route}
                className="muted small"
                style={{
                  background: "none",
                  border: 0,
                  padding: 0,
                  cursor: "pointer",
                }}
              >
                Forgot password?
              </Link>
            </div>

            {errors.root && (
              <div
                className="hint"
                style={{
                  color: "var(--danger)",
                }}
              >
                {errors.root.message}
              </div>
            )}

            <button
              className="btn primary"
              type="button"
              disabled={busy}
              onClick={() => {
                setSubmitted(true);
                void submitForm();
              }}
            >
              {busy ? "Logging in…" : "Log in"}
            </button>

            <div className="divider">
              or
            </div>

            <div className="socials">
              <button
                className="btn"
                type="button"
                onClick={() => router.push("/oauth/google/start")}
              >
                Continue with Google
              </button>

              <button
                className="btn"
                type="button"
                onClick={() => router.push("/oauth/github/start")}
              >
                Continue with GitHub
              </button>
            </div>

            <div className="hint">
              No account?{" "}
              <Link
                href="/signup"
                style={{ color: "#9fa9ff" }}
              >
                Create one
              </Link>
            </div>
          </form>
        </div>
      </section>
    </div>
  );
}
