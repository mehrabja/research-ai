import type { QueryClient } from "@tanstack/react-query";

let knownSessionUserId: string | null = null;

export function syncSessionUser(
  queryClient: QueryClient,
  userId: string,
): boolean {
  if (knownSessionUserId === userId) {
    return false;
  }

  queryClient.clear();
  knownSessionUserId = userId;
  return true;
}

export function clearSessionUserCache(
  queryClient: QueryClient,
): void {
  queryClient.clear();
  knownSessionUserId = null;
}

export function getKnownSessionUserId(): string | null {
  return knownSessionUserId;
}
