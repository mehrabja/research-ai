import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const ACCESS_COOKIE = "research_ai_access";
const REFRESH_COOKIE = "research_ai_refresh";

function securityHeaders(nonce: string): string {
  return [
    "default-src 'self'",
    "base-uri 'self'",
    "object-src 'none'",
    "frame-ancestors 'none'",
    "form-action 'self'",
    "script-src 'self' 'nonce-" + nonce + "' 'strict-dynamic'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    "connect-src 'self'",
    "media-src 'self' blob:",
    "worker-src 'self' blob:",
    "manifest-src 'self'",
  ].join("; ");
}

export function proxy(request: NextRequest) {
  const accessToken = request.cookies.get(ACCESS_COOKIE)?.value;
  const refreshToken = request.cookies.get(REFRESH_COOKIE)?.value;

  if (!accessToken && !refreshToken) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  const nonce = btoa(crypto.randomUUID());
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("Content-Security-Policy", securityHeaders(nonce));

  const response = NextResponse.next({
    request: { headers: requestHeaders },
  });
  response.headers.set("Content-Security-Policy", securityHeaders(nonce));
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("X-Frame-Options", "DENY");
  response.headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  response.headers.set("Permissions-Policy", "camera=(), microphone=(), geolocation=()");
  response.headers.set("Cross-Origin-Opener-Policy", "same-origin");
  response.headers.set("Cross-Origin-Resource-Policy", "same-origin");
  response.headers.set("X-Permitted-Cross-Domain-Policies", "none");

  return response;
}

export const config = {
  matcher: [
    "/ai-studio/:path*", "/citations/:path*", "/collaboration/:path*",
    "/dashboard/:path*", "/evidence/:path*", "/final-review/:path*",
    "/files/:path*", "/generate/:path*", "/humanize/:path*", "/jobs/:path*",
    "/knowledge/:path*", "/literature/:path*", "/manuscript/:path*",
    "/pdf-workspace/:path*", "/plan/:path*", "/publication/:path*",
    "/research/:path*", "/search/:path*", "/research-canvas/:path*",
    "/settings/:path*", "/sources/:path*", "/team/:path*",
    "/translate/:path*", "/usage-billing/:path*", "/workspace/:path*",
  ],
};