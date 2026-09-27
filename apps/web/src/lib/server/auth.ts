import { cookies } from "next/headers";
import { NextResponse } from "next/server";

const ACCESS_COOKIE = "research_ai_access_token";
const REFRESH_COOKIE = "research_ai_refresh";
const CSRF_COOKIE = "research_ai_csrf";

export type User = { id: string; email: string; full_name?: string | null };

export async function getServerUser(): Promise<User | null> {
  const token = (await cookies()).get(ACCESS_COOKIE)?.value;
  if (!token) return null;
  const base = process.env.BACKEND_API_URL ?? "http://localhost:8000";
  const res = await fetch(base + "/api/v1/auth/me", {
    headers: { authorization: "Bearer " + token },
    cache: "no-store",
  });
  if (!res.ok) return null;
  return res.json();
}

export function setAccessCookie(
  response: NextResponse,
  token: string,
): void {
  response.cookies.set({
    name: ACCESS_COOKIE,
    value: token,
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 30,
  });
}

export function clearAccessCookie(response: NextResponse): void {
  response.cookies.set({
    name: ACCESS_COOKIE,
    value: "",
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  });
}

export function copySetCookies(
  source: Headers,
  target: NextResponse,
): void {
  const headers = source as Headers & {
    getSetCookie?: () => string[];
  };
  const values = headers.getSetCookie?.() ?? [];
  for (const value of values) {
    target.headers.append("set-cookie", value);
  }
  if (!values.length) {
    const combined = source.get("set-cookie");
    if (combined) target.headers.set("set-cookie", combined);
  }
}

export function refreshCookieName(): string {
  return REFRESH_COOKIE;
}

export function csrfCookieName(): string {
  return CSRF_COOKIE;
}

export function accessCookieName(): string {
  return ACCESS_COOKIE;
}
