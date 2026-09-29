"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";

import { api } from "@/lib/api/client";
import { register as registerUser, login, logout } from "@/lib/api/auth";
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
      await registerUser(
        values.email,
        values.password,
      );

      await login(
        values.email,
        values.password,
      );

      const workspaceResponse = await api.POST(
        "/api/v1/workspaces",
        {
          body: {
            name: values.workspaceName,
          },
        },
      );

      if (workspaceResponse.error) {
        try {
          await logout();
        } catch {
          // Best-effort session cleanup.
        }

        throw workspaceResponse.error;
      }

      return workspaceResponse.data;
    },

    onSuccess: () => {
      router.replace("/dashboard");
    },

    onError: (error) => {
      console.error("Signup failed:", error);
    },
  });

  const onSubmit = (values: SignupInput) => {
    signupMutation.mutate(values);
  };

  return (
    <main>
      <h1>Create your research workspace</h1>

      <form
        onSubmit={handleSubmit(onSubmit)}
        noValidate
      >
        <div>
          <label htmlFor="firstName">
            First name
          </label>

          <input
            id="firstName"
            type="text"
            autoComplete="given-name"
            aria-invalid={
              errors.firstName ? "true" : "false"
            }
            {...register("firstName")}
          />

          {errors.firstName && (
            <p role="alert">
              {errors.firstName.message}
            </p>
          )}
        </div>

        <div>
          <label htmlFor="lastName">
            Last name
          </label>

          <input
            id="lastName"
            type="text"
            autoComplete="family-name"
            aria-invalid={
              errors.lastName ? "true" : "false"
            }
            {...register("lastName")}
          />

          {errors.lastName && (
            <p role="alert">
              {errors.lastName.message}
            </p>
          )}
        </div>

        <div>
          <label htmlFor="email">
            Work email
          </label>

          <input
            id="email"
            type="email"
            autoComplete="email"
            aria-invalid={
              errors.email ? "true" : "false"
            }
            {...register("email")}
          />

          {errors.email && (
            <p role="alert">
              {errors.email.message}
            </p>
          )}
        </div>

        <div>
          <label htmlFor="password">
            Password
          </label>

          <input
            id="password"
            type="password"
            autoComplete="new-password"
            aria-invalid={
              errors.password ? "true" : "false"
            }
            {...register("password")}
          />

          {errors.password && (
            <p role="alert">
              {errors.password.message}
            </p>
          )}
        </div>

        <div>
          <label htmlFor="workspaceName">
            Workspace name
          </label>

          <input
            id="workspaceName"
            type="text"
            autoComplete="organization"
            aria-invalid={
              errors.workspaceName
                ? "true"
                : "false"
            }
            {...register("workspaceName")}
          />

          {errors.workspaceName && (
            <p role="alert">
              {errors.workspaceName.message}
            </p>
          )}
        </div>

        <div>
          <label>
            <input
              type="checkbox"
              aria-invalid={
                errors.agree ? "true" : "false"
              }
              {...register("agree")}
            />
            I agree to the terms
          </label>

          {errors.agree && (
            <p role="alert">
              {errors.agree.message}
            </p>
          )}
        </div>

        {signupMutation.isError && (
          <p role="alert">
            Unable to create the workspace. Please try
            again.
          </p>
        )}

        <button
          type="button"
          disabled={signupMutation.isPending}
          onClick={() => {
            void handleSubmit(onSubmit)();
          }}
        >
          {signupMutation.isPending
            ? "Creating..."
            : "Create workspace"}
        </button>
      </form>
    </main>
  );
}