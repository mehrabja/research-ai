import { describe, expect, it } from "vitest";
import { isProtectedRoute, ROUTES } from "./routes";

describe("frontend route registry", () => {
  it("keeps the protected application routes explicit", () => {
    expect(isProtectedRoute(ROUTES.dashboard)).toBe(true);
    expect(isProtectedRoute(ROUTES.manuscript + "/123")).toBe(true);
    expect(isProtectedRoute(ROUTES.settings + "/profile")).toBe(true);
  });

  it("does not classify public routes as protected", () => {
    expect(isProtectedRoute(ROUTES.home)).toBe(false);
    expect(isProtectedRoute(ROUTES.login)).toBe(false);
    expect(isProtectedRoute(ROUTES.signup)).toBe(false);
  });
});
