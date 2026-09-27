import { NextResponse } from "next/server";
import { z } from "zod";
import { copySetCookies, setAccessCookie } from "@/lib/server/auth";

const schema = z.object({
  email: z.string().email(),
  password: z.string().min(15),
  full_name: z.string().max(255).optional(),
});

export async function POST(req: Request) {
  const parsed = schema.safeParse(await req.json().catch(() => null));
  if (!parsed.success) {
    return NextResponse.json(
      { detail: "Email/password validation failed." },
      { status: 422 },
    );
  }
  const base = process.env.BACKEND_API_URL ?? "http://localhost:8000";
  const backend = await fetch(base + "/api/v1/auth/register", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(parsed.data),
    cache: "no-store",
  });
  const body = await backend.json().catch(() => ({}));
  if (!backend.ok) {
    return NextResponse.json(body, { status: backend.status });
  }

  // Registration never manufactures a session. A production account must
  // complete the configured verification policy before signing in.
  const out = NextResponse.json({ ok: true, user: body });
  if (body.access_token) setAccessCookie(out, body.access_token);
  copySetCookies(backend.headers, out);
  return out;
}
