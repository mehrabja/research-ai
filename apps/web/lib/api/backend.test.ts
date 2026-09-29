import { afterEach, describe, expect, it } from "vitest";

import { backendUrl } from "./backend";

const originalBackendUrl = process.env.BACKEND_URL;

afterEach(() => {
  if (originalBackendUrl === undefined) {
    delete process.env.BACKEND_URL;
  } else {
    process.env.BACKEND_URL = originalBackendUrl;
  }
});

describe("backendUrl", () => {
  it("preserves the FastAPI /api prefix", () => {
    process.env.BACKEND_URL = "http://127.0.0.1:8001";

    expect(
      backendUrl(["v1", "auth", "register"], ""),
    ).toBe(
      "http://127.0.0.1:8001/api/v1/auth/register",
    );
  });

  it("reads BACKEND_URL at call time", () => {
    process.env.BACKEND_URL = "http://backend-a:8000";
    expect(
      backendUrl(["v1", "auth", "me"], ""),
    ).toBe(
      "http://backend-a:8000/api/v1/auth/me",
    );

    process.env.BACKEND_URL = "http://backend-b:8000";
    expect(
      backendUrl(["v1", "auth", "me"], "include=projects"),
    ).toBe(
      "http://backend-b:8000/api/v1/auth/me?include=projects",
    );
  });

  it("normalizes a trailing slash on BACKEND_URL", () => {
    process.env.BACKEND_URL = "http://backend:8000/";

    expect(
      backendUrl(["v1", "health", "live"], ""),
    ).toBe(
      "http://backend:8000/api/v1/health/live",
    );
  });
});
