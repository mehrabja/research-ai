"use client";

export type APIError = { detail?: string; code?: string; message?: string };

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("content-type")) headers.set("content-type", "application/json");
  const response = await fetch("/api/backend/" + path.replace(/^\/+/, ""), { ...init, headers, credentials: "same-origin", cache: "no-store" });
  const text = await response.text();
  let payload: unknown = null;
  try { payload = text ? JSON.parse(text) : null; } catch { payload = text; }
  if (!response.ok) {
    const error = payload as APIError | null;
    const fallback = "Request failed with HTTP " + response.status;
    throw new Error(error?.detail ?? error?.message ?? (typeof payload === "string" ? payload : "") ?? fallback);
  }
  return payload as T;
}