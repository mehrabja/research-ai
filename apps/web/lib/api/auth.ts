import type { components } from "./schema";

type UserResponse = components["schemas"]["UserResponse"];

export type AuthenticatedUser = UserResponse;

type AuthSuccess = {
  authenticated: true;
  token_type: string;
};

type AuthError = {
  error?: unknown;
  detail?: unknown;
  errors?: unknown;
};

async function parseResponse<T>(
  response: Response,
): Promise<T | AuthError> {
  const text = await response.text();

  if (!text) {
    return {} as T;
  }

  try {
    return JSON.parse(text) as T;
  } catch {
    return {};
  }
}

export async function register(
  email: string,
  password: string,
): Promise<UserResponse> {
  const response = await fetch(
    "/api/v1/auth/register",
    {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({
        email,
        password,
      }),
    },
  );

  const payload =
    await parseResponse<UserResponse>(response);

  if (!response.ok) {
    throw payload;
  }

  return payload as UserResponse;
}

export async function login(
  email: string,
  password: string,
): Promise<AuthSuccess> {
  const response = await fetch(
    "/api/v1/auth/login",
    {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({
        email,
        password,
      }),
    },
  );

  const payload =
    await parseResponse<AuthSuccess>(response);

  if (!response.ok) {
    throw payload;
  }

  return payload as AuthSuccess;
}

export async function refresh(): Promise<AuthSuccess> {
  const response = await fetch(
    "/api/v1/auth/refresh",
    {
      method: "POST",
      credentials: "include",
      headers: {
        Accept: "application/json",
      },
      body: JSON.stringify({}),
    },
  );

  const payload =
    await parseResponse<AuthSuccess>(response);

  if (!response.ok) {
    throw payload;
  }

  return payload as AuthSuccess;
}

export async function logout(): Promise<void> {
  const response = await fetch(
    "/api/v1/auth/logout",
    {
      method: "POST",
      credentials: "include",
      headers: {
        Accept: "application/json",
      },
      body: JSON.stringify({}),
    },
  );

  if (!response.ok) {
    throw await parseResponse<unknown>(response);
  }
}

export async function me(): Promise<AuthenticatedUser> {
  const response = await fetch(
    "/api/v1/auth/me",
    {
      method: "GET",
      credentials: "include",
      headers: {
        Accept: "application/json",
      },
    },
  );

  const payload =
    await parseResponse<AuthenticatedUser>(
      response,
    );

  if (!response.ok) {
    throw payload;
  }

  return payload as AuthenticatedUser;
}