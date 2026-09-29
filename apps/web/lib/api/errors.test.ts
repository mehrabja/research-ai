import { describe, expect, it } from "vitest";
import { ApiError, apiErrorFromUnknown } from "./errors";

describe("ApiError", () => {
  it("normalizes structured backend errors", () => {
    const error = apiErrorFromUnknown(
      {
        detail: "Workspace not found",
        code: "WORKSPACE_NOT_FOUND",
      },
      { status: 404 },
    );

    expect(error).toBeInstanceOf(ApiError);
    expect(error.message).toBe("Workspace not found");
    expect(error.code).toBe("WORKSPACE_NOT_FOUND");
    expect(error.status).toBe(404);
    expect(error.retryable).toBe(false);
  });

  it("marks transient responses as retryable", () => {
    const error = apiErrorFromUnknown(
      { detail: "Backend unavailable" },
      { status: 503 },
    );

    expect(error.retryable).toBe(true);
  });
});


test("unwraps the canonical nested error envelope", () => {
  const error = apiErrorFromUnknown(
    {
      error: {
        code: "RATE_LIMITED",
        message: "Too many requests",
        request_id: "rid-123",
      },
    },
    { status: 429 },
  );

  expect(error.message).toBe("Too many requests");
  expect(error.code).toBe("RATE_LIMITED");
  expect(error.requestId).toBe("rid-123");
  expect(error.retryable).toBe(true);
});
