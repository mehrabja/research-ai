"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

import { register as registerUser, login } from "@/lib/api/auth";
import {
  signupSchema,
  type SignupInput,
} from "@/lib/validation/auth";

export default function SignupPage() {
  const router = useRouter();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<SignupInput>({
    resolver: zodResolver(signupSchema),
    mode: "onBlur",
  });

  const signupMutation = useMutation({
    mutationFn: async (values: SignupInput) => {
      const fullName = [values.firstName, values.lastName]
        .map((value) => value.trim())
        .filter(Boolean)
        .join(" ");

      const user = await registerUser(
        values.email,
        values.password,
        fullName,
        values.workspaceName,
      );
      await login(values.email, values.password);
      return user;
    },

    onSuccess: () => {
      router.replace("/dashboard");
    },
  });

  const onSubmit = (values: SignupInput) => {
    signupMutation.mutate(values);
  };

  const errorMessage =
    signupMutation.error instanceof Error
      ? signupMutation.error.message
      : "Unable to create your account. Please try again.";

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
          Start with a workspace built for evidence.
        </h1>

        <p>
          Organize papers, source notes, project files,
          research plans and manuscript versions in one
          controlled research environment.
        </p>

        <div className="quote">
          <div className="tag primary">
            Research workflow
          </div>

          <p
            style={{
              margin: "12px 0 0",
              color: "var(--ink-soft)",
            }}
          >
            Keep the work, evidence and provenance
            connected from the first question to the
            final manuscript.
          </p>

          <div
            className="muted small"
            style={{ marginTop: 10 }}
          >
            Evidence-grounded by design
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

          <h2>Create your account</h2>

          <div className="muted">
            Set up your research workspace to get started.
          </div>

          <form
            className="auth-form"
            onSubmit={handleSubmit(onSubmit)}
            noValidate
          >
            <div className="grid grid-2">
              <div className="field">
                <label htmlFor="firstName">
                  First name
                </label>

                <input
                  id="firstName"
                  className="input"
                  type="text"
                  autoComplete="given-name"
                  {...register("firstName")}
                  aria-invalid={
                    errors.firstName ? "true" : "false"
                  }
                />

                {errors.firstName && (
                  <div
                    className="hint"
                    style={{ color: "var(--danger)" }}
                  >
                    {errors.firstName.message}
                  </div>
                )}
              </div>

              <div className="field">
                <label htmlFor="lastName">
                  Last name
                </label>

                <input
                  id="lastName"
                  className="input"
                  type="text"
                  autoComplete="family-name"
                  {...register("lastName")}
                  aria-invalid={
                    errors.lastName ? "true" : "false"
                  }
                />

                {errors.lastName && (
                  <div
                    className="hint"
                    style={{ color: "var(--danger)" }}
                  >
                    {errors.lastName.message}
                  </div>
                )}
              </div>
            </div>

            <div className="field">
              <label htmlFor="email">
                Work email
              </label>

              <input
                id="email"
                className="input"
                type="email"
                placeholder="you@lab.edu"
                autoComplete="email"
                {...register("email")}
                aria-invalid={
                  errors.email ? "true" : "false"
                }
              />

              {errors.email && (
                <div
                  className="hint"
                  style={{ color: "var(--danger)" }}
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
                autoComplete="new-password"
                {...register("password")}
                aria-invalid={
                  errors.password ? "true" : "false"
                }
              />

              {errors.password && (
                <div
                  className="hint"
                  style={{ color: "var(--danger)" }}
                >
                  {errors.password.message}
                </div>
              )}
            </div>

            <div className="field">
              <label htmlFor="workspaceName">
                Workspace name
              </label>

              <input
                id="workspaceName"
                className="input"
                type="text"
                placeholder="My Research Lab"
                autoComplete="organization"
                {...register("workspaceName")}
                aria-invalid={
                  errors.workspaceName
                    ? "true"
                    : "false"
                }
              />

              {errors.workspaceName && (
                <div
                  className="hint"
                  style={{ color: "var(--danger)" }}
                >
                  {errors.workspaceName.message}
                </div>
              )}
            </div>

            <label className="checkbox">
              <input
                type="checkbox"
                aria-invalid={
                  errors.agree ? "true" : "false"
                }
                {...register("agree")}
              />
              <span>
                I agree to the terms
              </span>
            </label>

            {errors.agree && (
              <div
                className="hint"
                style={{ color: "var(--danger)" }}
              >
                {errors.agree.message}
              </div>
            )}

            {signupMutation.isError && (
              <div
                className="hint"
                role="alert"
                style={{ color: "var(--danger)" }}
              >
                {errorMessage}
              </div>
            )}

            <button
              className="btn primary"
              type="submit"
              disabled={signupMutation.isPending}
            >
              {signupMutation.isPending
                ? "Creating..."
                : "Create workspace"}
            </button>

            <div className="hint">
              Already have an account?{" "}
              <Link
                href="/login"
                style={{ color: "var(--primary)" }}
              >
                Log in
              </Link>
            </div>
          </form>
        </div>
      </section>
    </div>
  );
}
