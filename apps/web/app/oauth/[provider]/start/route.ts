import { NextResponse } from "next/server";
import { backendUrl } from "@/lib/api/backend";

const PROVIDERS = new Set(["google", "github"]);
const OAUTH_COOKIE_PREFIX = "research_ai_oauth_";
const OAUTH_MAX_AGE = 10 * 60;

export async function GET(
  request: Request,
  context: { params: Promise<{ provider: string }> },
) {
  const { provider: rawProvider } = await context.params;
  const provider = rawProvider.trim().toLowerCase();

  if (!PROVIDERS.has(provider)) {
    return NextResponse.redirect(
      new URL("/login?oauth_error=unsupported_provider", request.url),
    );
  }

  let upstream: Response;
  try {
    upstream = await fetch(
      backendUrl(["v1", "auth", "oauth", provider, "start"], ""),
      {
        method: "GET",
        headers: { Accept: "application/json" },
        cache: "no-store",
        redirect: "manual",
      },
    );
  } catch {
    return NextResponse.redirect(
      new URL("/login?oauth_error=backend_unreachable", request.url),
    );
  }

  let payload: unknown = null;
  try {
    payload = await upstream.json();
  } catch {
    payload = null;
  }

  if (
    !upstream.ok ||
    !payload ||
    typeof payload !== "object" ||
    typeof (payload as { authorization_url?: unknown }).authorization_url !== "string" ||
    typeof (payload as { state?: unknown }).state !== "string" ||
    typeof (payload as { code_verifier?: unknown }).code_verifier !== "string"
  ) {
    return NextResponse.redirect(
      new URL("/login?oauth_error=oauth_start_failed", request.url),
    );
  }

  const typed = payload as {
    authorization_url: string;
    state: string;
    code_verifier: string;
  };

  const response = NextResponse.redirect(typed.authorization_url);
  response.cookies.set(
    OAUTH_COOKIE_PREFIX + provider,
    typed.state + "." + typed.code_verifier,
    {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/oauth/" + provider + "/callback",
      maxAge: OAUTH_MAX_AGE,
    },
  );
  return response;
}
