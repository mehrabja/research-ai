import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const ACCESS_COOKIE = "research_ai_access";
const REFRESH_COOKIE = "research_ai_refresh";

export function proxy(request: NextRequest) {
  const accessToken = request.cookies.get(ACCESS_COOKIE)?.value;
  const refreshToken = request.cookies.get(REFRESH_COOKIE)?.value;

  if (!accessToken && !refreshToken) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/ai-studio/:path*",
    "/citations/:path*",
    "/collaboration/:path*",
    "/dashboard/:path*",
    "/evidence/:path*",
    "/final-review/:path*",
    "/files/:path*",
    "/generate/:path*",
    "/humanize/:path*",
    "/jobs/:path*",
    "/knowledge/:path*",
    "/literature/:path*",
    "/manuscript/:path*",
    "/pdf-workspace/:path*",
    "/plan/:path*",
    "/publication/:path*",
    "/research/:path*",
    "/search/:path*",
    "/research-canvas/:path*",
    "/settings/:path*",
    "/sources/:path*",
    "/team/:path*",
    "/translate/:path*",
    "/usage-billing/:path*",
    "/workspace/:path*",
  ],
};