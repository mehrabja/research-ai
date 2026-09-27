import { NextResponse } from "next/server";
import { clearAccessCookie, copySetCookies, csrfCookieName, refreshCookieName } from "@/lib/server/auth";
import { cookies } from "next/headers";

export async function POST(req: Request) {
  const jar = await cookies();
  const refreshToken = jar.get(refreshCookieName())?.value;
  const csrf = jar.get(csrfCookieName())?.value;
  const headerCsrf = req.headers.get("x-csrf-token") ?? csrf;
  const base = process.env.BACKEND_API_URL ?? "http://localhost:8000";

  if (refreshToken && csrf && headerCsrf === csrf) {
    const backend = await fetch(base + "/api/v1/auth/logout", {
      method: "POST",
      headers: {
        cookie: refreshCookieName() + "=" + refreshToken + "; " + csrfCookieName() + "=" + csrf,
        "x-csrf-token": headerCsrf,
      },
      cache: "no-store",
    });
    const out = NextResponse.json({ ok: true }, { status: backend.ok ? 200 : 502 });
    copySetCookies(backend.headers, out);
    clearAccessCookie(out);
    return out;
  }

  const out = NextResponse.json({ ok: true });
  clearAccessCookie(out);
  return out;
}
