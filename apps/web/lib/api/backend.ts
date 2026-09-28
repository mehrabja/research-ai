import "server-only";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

/**
 * Builds the upstream FastAPI URL for a given API-proxy path + querystring.
 */
export function backendUrl(path: string[], search: string) {
  const joined = path.join("/");
  return `${BACKEND_URL.replace(/\/$/, "")}/${joined}${search ? `?${search}` : ""}`;
}

const HOP_BY_HOP_REQUEST_HEADERS = new Set([
  "host",
  "connection",
  "content-length",
]);

/**
 * Copies incoming headers for the outgoing backend request, dropping the
 * ones that must not be forwarded as-is (Host, hop-by-hop headers, etc.).
 * The user's session cookie IS forwarded, so FastAPI sees the same auth
 * context as the browser would if it hit the backend directly.
 */
export function forwardableRequestHeaders(headers: Headers): Headers {
  const out = new Headers();
  headers.forEach((value, key) => {
    if (!HOP_BY_HOP_REQUEST_HEADERS.has(key.toLowerCase())) {
      out.set(key, value);
    }
  });
  return out;
}

const HOP_BY_HOP_RESPONSE_HEADERS = new Set([
  "connection",
  "transfer-encoding",
  "content-encoding",
]);

export function forwardableResponseHeaders(headers: Headers): Headers {
  const out = new Headers();
  headers.forEach((value, key) => {
    if (!HOP_BY_HOP_RESPONSE_HEADERS.has(key.toLowerCase())) {
      out.set(key, value);
    }
  });
  return out;
}
