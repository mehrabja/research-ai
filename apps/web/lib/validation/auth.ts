import { z } from "zod";

export const loginSchema = z.object({
  email: z.string().min(1, "Email is required").email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});
export type LoginInput = z.infer<typeof loginSchema>;

export const signupSchema = z.object({
  firstName: z.string().min(1, "First name is required"),
  lastName: z.string().min(1, "Last name is required"),
  email: z.string().min(1, "Work email is required").email("Enter a valid email address"),
  password: z
    .string()
    .min(15, "Use at least 15 characters")
    .regex(/[A-Z]/, "Include an uppercase letter")
    .regex(/[0-9]/, "Include a number"),
  workspaceName: z.string().min(1, "Workspace name is required"),
  agree: z.boolean().refine((v) => v === true, {
    message: "You must accept the workspace terms",
  }),
});
export type SignupInput = z.infer<typeof signupSchema>;
