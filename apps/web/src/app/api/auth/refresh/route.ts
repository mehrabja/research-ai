import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { copySetCookies, csrfCookieName, refreshCookieName, setAccessCookie } from "@/lib/server/auth";

export async function POST(req: Request) {
  const jar = await cookies();
  const refreshToken = jar.get(refreshCookieName())?.value;
  const csrf = jar.get(csrfCookieName())?.value;
  const headerCsrf = req.headers.get("x-csrf-token") ?? csrf;
  if (!refreshToken || !csrf || !headerCsrf || csrf !== headerCsrf) {
    return NextResponse.json({ detail: "CSRF validation failed." }, { status: 403 });
  }
  const base = process.env.BACKEND_API_URL ?? "http://localhost:8000";
  const backend = await fetch(base + "/api/v1/auth/refresh", {
    method: "POST",
    headers: { "cookie": refreshCookieName() + "=" + refreshToken, "x-csrf-token": headerCsrf },
    cache: "no-store",
  });
  const body = await backend.json().catch(() => ({}));
  if (!backend.ok) return NextResponse.json(body, { status: backend.status });
  const out = NextResponse.json({ ok: true });
  if (body.access_token) setAccessCookie(out, body.access_token);
  copySetCookies(backend.headers, out);
  return out;
}
