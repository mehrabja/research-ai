import type { components } from "./schema";
import { apiErrorFromResponse } from "./errors";

type UserResponse = components["schemas"]["UserResponse"];
export type AuthenticatedUser = UserResponse;
type AuthSuccess = { authenticated: true; token_type: string };

async function parseResponse<T>(response: Response): Promise<T> {
  const text = await response.text();
  if (!text) return {} as T;
  try { return JSON.parse(text) as T; } catch { return {} as T; }
}

async function parseSuccess<T>(response: Response, fallback: string): Promise<T> {
  if (!response.ok) throw await apiErrorFromResponse(response, fallback);
  return parseResponse<T>(response);
}

export async function register(email: string, password: string): Promise<UserResponse> {
  const response = await fetch("/api/v1/auth/register", {
    method: "POST",
    credentials: "include",
    headers: {"Content-Type":"application/json",Accept:"application/json"},
    body: JSON.stringify({email,password}),
  });
  return parseSuccess<UserResponse>(response, "Registration request failed.");
}

export async function login(email: string, password: string): Promise<AuthSuccess> {
  const response = await fetch("/api/v1/auth/login", {
    method: "POST",
    credentials: "include",
    headers: {"Content-Type":"application/json",Accept:"application/json"},
    body: JSON.stringify({email,password}),
  });
  return parseSuccess<AuthSuccess>(response, "Authentication request failed.");
}

export async function refresh(): Promise<AuthSuccess> {
  const response = await fetch("/api/v1/auth/refresh", {
    method: "POST",
    credentials: "include",
    headers: {Accept:"application/json"},
    body: JSON.stringify({}),
  });
  return parseSuccess<AuthSuccess>(response, "Session refresh failed.");
}

export async function logout(): Promise<void> {
  const response = await fetch("/api/v1/auth/logout", {
    method: "POST",
    credentials: "include",
    headers: {Accept:"application/json"},
    body: JSON.stringify({}),
  });
  await parseSuccess<unknown>(response, "Logout failed.");
}

export async function me(): Promise<AuthenticatedUser> {
  const response = await fetch("/api/v1/auth/me", {
    method: "GET",
    credentials: "include",
    headers: {Accept:"application/json"},
  });
  return parseSuccess<AuthenticatedUser>(response, "Unable to load the authenticated user.");
}
