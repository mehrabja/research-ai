import { NextResponse } from "next/server";
import { z } from "zod";
import { copySetCookies, setAccessCookie } from "@/lib/server/auth";

const schema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
  two_factor_code: z.string().length(6).optional(),
  recovery_code: z.string().min(8).max(32).optional(),
});

export async function POST(req: Request) {
  const parsed = schema.safeParse(await req.json().catch(() => null));
  if (!parsed.success) {
    return NextResponse.json(
      { detail: "Invalid credentials payload." },
      { status: 422 },
    );
  }

  const base = process.env.BACKEND_API_URL ?? "http://localhost:8000";
  const backend = await fetch(base + "/api/v1/auth/login", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(parsed.data),
    cache: "no-store",
  });
  const body = await backend.json().catch(() => ({}));
  if (!backend.ok) {
    return NextResponse.json(body, { status: backend.status });
  }

  const out = NextResponse.json({ ok: true });
  setAccessCookie(out, body.access_token);
  copySetCookies(backend.headers, out);
  return out;
}
