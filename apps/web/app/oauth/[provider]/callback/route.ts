import { NextResponse } from "next/server";
import { backendUrl } from "@/lib/api/backend";

const ACCESS_COOKIE = "research_ai_access";
const REFRESH_COOKIE = "research_ai_refresh";
const ACCESS_MAX_AGE = 30 * 60;
const REFRESH_MAX_AGE = 30 * 24 * 60 * 60;
const PROVIDERS = new Set(["google", "github"]);

function authCookieOptions(maxAge: number) {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax" as const,
    path: "/",
    maxAge,
  };
}

export async function GET(
  request: Request,
  context: { params: Promise<{ provider: string }> },
) {
  const { provider: rawProvider } = await context.params;
  const provider = rawProvider.trim().toLowerCase();
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const state = url.searchParams.get("state");
  const oauthCookie = request.headers.get("cookie")
    ?.split(";")
    .map((item) => item.trim())
    .find((item) => item.startsWith("research_ai_oauth_" + provider + "="))
    ?.split("=")[1] ?? "";

  if (!PROVIDERS.has(provider) || !code || !state || !oauthCookie) {
    return NextResponse.redirect(
      new URL("/login?oauth_error=invalid_callback", request.url),
    );
  }

  const cookieValue = decodeURIComponent(oauthCookie);
  const separator = cookieValue.indexOf(".");
  const cookieState = separator > 0 ? cookieValue.slice(0, separator) : "";
  const codeVerifier = separator > 0 ? cookieValue.slice(separator + 1) : "";

  if (cookieState !== state || codeVerifier.length < 43) {
    return NextResponse.redirect(
      new URL("/login?oauth_error=pkce_validation_failed", request.url),
    );
  }

  let upstream: Response;
  try {
    upstream = await fetch(
      backendUrl(["v1", "auth", "oauth", provider, "callback"], ""),
      {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ code, state, code_verifier: codeVerifier }),
        cache: "no-store",
        redirect: "manual",
      },
    );
  } catch {
    return NextResponse.redirect(
      new URL("/login?oauth_error=backend_unreachable", request.url),
    );
  }

  if (!upstream.ok) {
    const response = NextResponse.redirect(
      new URL("/login?oauth_error=oauth_callback_failed", request.url),
    );
    response.cookies.set("research_ai_oauth_" + provider, "", {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/oauth/" + provider + "/callback",
      maxAge: 0,
    });
    return response;
  }

  let payload: unknown = null;
  try {
    payload = await upstream.json();
  } catch {
    payload = null;
  }

  if (
    !payload ||
    typeof payload !== "object" ||
    typeof (payload as { access_token?: unknown }).access_token !== "string" ||
    typeof (payload as { refresh_token?: unknown }).refresh_token !== "string"
  ) {
    return NextResponse.redirect(
      new URL("/login?oauth_error=invalid_response", request.url),
    );
  }

  const tokens = payload as {
    access_token: string;
    refresh_token: string;
  };

  const response = NextResponse.redirect(new URL("/dashboard", request.url));
  response.cookies.set("research_ai_oauth_" + provider, "", {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/oauth/" + provider + "/callback",
    maxAge: 0,
  });
  response.cookies.set(
    ACCESS_COOKIE,
    tokens.access_token,
    authCookieOptions(ACCESS_MAX_AGE),
  );
  response.cookies.set(
    REFRESH_COOKIE,
    tokens.refresh_token,
    authCookieOptions(REFRESH_MAX_AGE),
  );
  return response;
}
