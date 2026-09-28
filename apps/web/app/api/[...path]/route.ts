import { NextRequest, NextResponse } from "next/server";
import {
  backendUrl,
  forwardableRequestHeaders,
  forwardableResponseHeaders,
} from "@/lib/api/backend";

export const dynamic = "force-dynamic";

const ACCESS_COOKIE = "research_ai_access";
const REFRESH_COOKIE = "research_ai_refresh";

const ACCESS_MAX_AGE = 30 * 60;
const REFRESH_MAX_AGE = 30 * 24 * 60 * 60;

const UNSAFE_METHODS = new Set([
  "POST",
  "PUT",
  "PATCH",
  "DELETE",
]);

type AuthTokens = {
  access_token: string;
  refresh_token: string;
};

const refreshInFlight = new Map<
  string,
  Promise<AuthTokens | null>
>();

function isAuthPath(path: string[], endpoint: string): boolean {
  return path.join("/") === `v1/auth/${endpoint}`;
}

function cookieOptions(maxAge: number) {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax" as const,
    path: "/",
    maxAge,
  };
}

function clearCookieOptions() {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax" as const,
    path: "/",
    maxAge: 0,
  };
}

function clearAuthCookies(response: NextResponse) {
  response.cookies.set(
    ACCESS_COOKIE,
    "",
    clearCookieOptions(),
  );

  response.cookies.set(
    REFRESH_COOKIE,
    "",
    clearCookieOptions(),
  );
}

function setAuthCookies(
  response: NextResponse,
  tokens: AuthTokens,
) {
  response.cookies.set(
    ACCESS_COOKIE,
    tokens.access_token,
    cookieOptions(ACCESS_MAX_AGE),
  );

  response.cookies.set(
    REFRESH_COOKIE,
    tokens.refresh_token,
    cookieOptions(REFRESH_MAX_AGE),
  );
}

function responseHeadersWithoutBodyMetadata(
  headers: Headers,
): Headers {
  const result = forwardableResponseHeaders(headers);

  result.delete("content-length");
  result.delete("content-encoding");
  result.delete("transfer-encoding");

  return result;
}

function buildAuthenticatedHeaders(
  req: NextRequest,
  accessToken?: string,
): Headers {
  const headers = forwardableRequestHeaders(req.headers);

  headers.delete("cookie");
  headers.delete("authorization");

  if (accessToken) {
    headers.set("authorization", `Bearer ${accessToken}`);
  }

  return headers;
}

function buildAnonymousHeaders(
  req: NextRequest,
): Headers {
  const headers = forwardableRequestHeaders(req.headers);

  headers.delete("cookie");
  headers.delete("authorization");

  return headers;
}

function isSameOriginRequest(
  req: NextRequest,
): boolean {
  const origin = req.headers.get("origin");

  if (origin) {
    return origin === req.nextUrl.origin;
  }

  const fetchSite = req.headers.get("sec-fetch-site");

  if (fetchSite === "cross-site") {
    return false;
  }

  return true;
}

function rejectCsrf(): NextResponse {
  return NextResponse.json(
    {
      error: "CSRF validation failed",
    },
    {
      status: 403,
    },
  );
}

async function parseJson(response: Response): Promise<unknown> {
  const text = await response.text();

  if (!text) {
    return {};
  }

  try {
    return JSON.parse(text);
  } catch {
    return {};
  }
}

async function performRefresh(
  refreshToken: string,
): Promise<AuthTokens | null> {
  const existing = refreshInFlight.get(refreshToken);

  if (existing) {
    return existing;
  }

  const refreshPromise = (async () => {
    const url = backendUrl(
      ["v1", "auth", "refresh"],
      "",
    );

    const headers = new Headers();
    headers.set("content-type", "application/json");
    headers.set("accept", "application/json");

    const upstream = await fetch(url, {
      method: "POST",
      headers,
      body: JSON.stringify({
        refresh_token: refreshToken,
      }),
      redirect: "manual",
      cache: "no-store",
    });

    if (!upstream.ok) {
      return null;
    }

    const payload = await parseJson(upstream);

    if (
      !payload ||
      typeof payload !== "object" ||
      typeof (
        payload as {
          access_token?: unknown;
        }
      ).access_token !== "string" ||
      typeof (
        payload as {
          refresh_token?: unknown;
        }
      ).refresh_token !== "string"
    ) {
      return null;
    }

    return {
      access_token: (
        payload as {
          access_token: string;
        }
      ).access_token,
      refresh_token: (
        payload as {
          refresh_token: string;
        }
      ).refresh_token,
    };
  })();

  refreshInFlight.set(refreshToken, refreshPromise);

  try {
    return await refreshPromise;
  } finally {
    refreshInFlight.delete(refreshToken);
  }
}

async function proxy(
  req: NextRequest,
  {
    params,
  }: {
    params: Promise<{ path: string[] }>;
  },
) {
  const { path } = await params;

  if (
    UNSAFE_METHODS.has(req.method) &&
    !isSameOriginRequest(req)
  ) {
    return rejectCsrf();
  }

  const search = req.nextUrl.search.replace(/^\?/, "");
  const url = backendUrl(path, search);

  const accessToken =
    req.cookies.get(ACCESS_COOKIE)?.value;

  const refreshToken =
    req.cookies.get(REFRESH_COOKIE)?.value;

  let requestBody: ArrayBuffer | undefined;

  if (!["GET", "HEAD"].includes(req.method)) {
    requestBody = await req.arrayBuffer();
  }

  if (isAuthPath(path, "login")) {
    let upstream: Response;

    try {
      upstream = await fetch(url, {
        method: req.method,
        headers: buildAnonymousHeaders(req),
        body: requestBody,
        redirect: "manual",
        cache: "no-store",
      });
    } catch {
      return NextResponse.json(
        { error: "Backend unreachable" },
        { status: 502 },
      );
    }

    const payload = await parseJson(upstream);

    if (
      upstream.ok &&
      payload &&
      typeof payload === "object" &&
      typeof (
        payload as {
          access_token?: unknown;
        }
      ).access_token === "string" &&
      typeof (
        payload as {
          refresh_token?: unknown;
        }
      ).refresh_token === "string"
    ) {
      const tokenPayload = payload as {
        access_token: string;
        refresh_token: string;
        token_type?: string;
      };

      const response = NextResponse.json(
        {
          authenticated: true,
          token_type:
            tokenPayload.token_type ?? "bearer",
        },
        {
          status: upstream.status,
          headers:
            responseHeadersWithoutBodyMetadata(
              upstream.headers,
            ),
        },
      );

      setAuthCookies(response, {
        access_token:
          tokenPayload.access_token,
        refresh_token:
          tokenPayload.refresh_token,
      });

      return response;
    }

    return NextResponse.json(payload, {
      status: upstream.status,
      headers:
        responseHeadersWithoutBodyMetadata(
          upstream.headers,
        ),
    });
  }

  if (isAuthPath(path, "refresh")) {
    if (!refreshToken) {
      const response = NextResponse.json(
        { error: "Refresh session missing" },
        { status: 401 },
      );

      clearAuthCookies(response);
      return response;
    }

    let refreshed: AuthTokens | null = null;

    try {
      refreshed = await performRefresh(
        refreshToken,
      );
    } catch {
      refreshed = null;
    }

    if (!refreshed) {
      const response = NextResponse.json(
        { error: "Refresh session invalid" },
        { status: 401 },
      );

      clearAuthCookies(response);
      return response;
    }

    const response = NextResponse.json({
      authenticated: true,
      token_type: "bearer",
    });

    setAuthCookies(response, refreshed);

    return response;
  }

  if (isAuthPath(path, "logout")) {
    let upstream: Response | null = null;

    if (refreshToken) {
      try {
        const headers = new Headers();

        headers.set(
          "content-type",
          "application/json",
        );

        headers.set(
          "accept",
          "application/json",
        );

        upstream = await fetch(url, {
          method: "POST",
          headers,
          body: JSON.stringify({
            refresh_token: refreshToken,
          }),
          redirect: "manual",
          cache: "no-store",
        });
      } catch {
        upstream = null;
      }
    }

    if (upstream) {
      const payload = await parseJson(upstream);

      const response = NextResponse.json(
        payload,
        {
          status: upstream.status,
          headers:
            responseHeadersWithoutBodyMetadata(
              upstream.headers,
            ),
        },
      );

      clearAuthCookies(response);

      return response;
    }

    const response = NextResponse.json(
      { message: "Signed out." },
      { status: 200 },
    );

    clearAuthCookies(response);

    return response;
  }

  let upstream: Response;

  try {
    upstream = await fetch(url, {
      method: req.method,
      headers: buildAuthenticatedHeaders(
        req,
        accessToken,
      ),
      body: requestBody,
      redirect: "manual",
      cache: "no-store",
    });
  } catch {
    return NextResponse.json(
      { error: "Backend unreachable" },
      { status: 502 },
    );
  }

  if (
    upstream.status === 401 &&
    accessToken &&
    refreshToken
  ) {
    let refreshed: AuthTokens | null = null;

    try {
      refreshed = await performRefresh(
        refreshToken,
      );
    } catch {
      refreshed = null;
    }

    if (refreshed) {
      try {
        upstream = await fetch(url, {
          method: req.method,
          headers: buildAuthenticatedHeaders(
            req,
            refreshed.access_token,
          ),
          body: requestBody,
          redirect: "manual",
          cache: "no-store",
        });
      } catch {
        const response = NextResponse.json(
          { error: "Backend unreachable" },
          { status: 502 },
        );

        clearAuthCookies(response);
        return response;
      }

      const response = new NextResponse(
        upstream.body,
        {
          status: upstream.status,
          statusText: upstream.statusText,
          headers:
            forwardableResponseHeaders(
              upstream.headers,
            ),
        },
      );

      setAuthCookies(response, refreshed);

      return response;
    }

    const response = new NextResponse(
      upstream.body,
      {
        status: upstream.status,
        statusText: upstream.statusText,
        headers:
          forwardableResponseHeaders(
            upstream.headers,
          ),
      },
    );

    clearAuthCookies(response);

    return response;
  }

  return new NextResponse(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers:
      forwardableResponseHeaders(
        upstream.headers,
      ),
  });
}

export {
  proxy as GET,
  proxy as POST,
  proxy as PUT,
  proxy as PATCH,
  proxy as DELETE,
};