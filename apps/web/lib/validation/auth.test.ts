import { describe, expect, it } from "vitest";
import { loginSchema, signupSchema } from "@/lib/validation/auth";

describe("loginSchema", () => {
  it("accepts a valid email/password", () => {
    const result = loginSchema.safeParse({
      email: "alex@lab.edu",
      password: "secret123",
    });
    expect(result.success).toBe(true);
  });

  it("rejects an invalid email", () => {
    const result = loginSchema.safeParse({
      email: "not-an-email",
      password: "Secret123456789456789",
    });
    expect(result.success).toBe(false);
  });
});

describe("signupSchema", () => {
  const valid = {
    firstName: "Alex",
    lastName: "Imani",
    email: "alex@lab.edu",
    password: "Secret123456789",
    workspaceName: "Neural Research Lab",
    agree: true,
  };

  it("accepts a fully valid submission", () => {
    expect(signupSchema.safeParse(valid).success).toBe(true);
  });

  it("requires the terms checkbox to be accepted", () => {
    const result = signupSchema.safeParse({ ...valid, agree: false });
    expect(result.success).toBe(false);
  });

  it("requires a password with an uppercase letter and a number", () => {
    const result = signupSchema.safeParse({ ...valid, password: "lowercase" });
    expect(result.success).toBe(false);
  });
});
