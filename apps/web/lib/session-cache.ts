import type { QueryClient } from "@tanstack/react-query";

export const SESSION_EVENT_KEY = "research-ai:session-event";
export type SessionEventType = "authenticated" | "logout";

let knownSessionUserId: string | null = null;

export function broadcastSessionEvent(type: SessionEventType): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(
      SESSION_EVENT_KEY,
      JSON.stringify({ type, nonce: Date.now() }),
    );
  } catch {
    // Storage may be disabled; session correctness does not depend on this signal.
  }
}

export function syncSessionUser(
  queryClient: QueryClient,
  userId: string,
): boolean {
  if (knownSessionUserId === userId) {
    return false;
  }

  queryClient.removeQueries({
    predicate: (query) => query.queryKey[0] !== "session",
  });
  knownSessionUserId = userId;
  return true;
}

export function clearSessionUserCache(
  queryClient: QueryClient,
  broadcast = true,
): void {
  queryClient.clear();
  knownSessionUserId = null;
  if (broadcast) broadcastSessionEvent("logout");
}

export function getKnownSessionUserId(): string | null {
  return knownSessionUserId;
}
