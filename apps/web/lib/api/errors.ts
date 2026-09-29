export type ApiErrorPayload = {
  detail?: unknown;
  message?: unknown;
  error?: unknown;
  code?: unknown;
};

export class ApiError extends Error {
  readonly status: number;
  readonly code: string | null;
  readonly requestId: string | null;
  readonly retryable: boolean;

  constructor(
    message: string,
    options: {
      status?: number;
      code?: string | null;
      requestId?: string | null;
      retryable?: boolean;
    } = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.status = options.status ?? 0;
    this.code = options.code ?? null;
    this.requestId = options.requestId ?? null;
    this.retryable =
      options.retryable ??
      (this.status === 408 ||
        this.status === 429 ||
        this.status >= 500);
  }
}

export function apiErrorFromUnknown(
  value: unknown,
  options: {
    status?: number;
    requestId?: string | null;
    fallback?: string;
  } = {},
): ApiError {
  const payload =
    value && typeof value === "object"
      ? (value as ApiErrorPayload)
      : null;

  const code =
    payload && typeof payload.code === "string"
      ? payload.code
      : null;

  const message =
    payload && typeof payload.detail === "string"
      ? payload.detail
      : payload && typeof payload.message === "string"
        ? payload.message
        : payload && typeof payload.error === "string"
          ? payload.error
          : options.fallback ?? "API request failed";

  return new ApiError(message, {
    status: options.status,
    code,
    requestId: options.requestId,
  });
}

export async function apiErrorFromResponse(
  response: Response,
  fallback: string,
): Promise<ApiError> {
  let payload: unknown = null;

  try {
    const text = await response.text();
    if (text) {
      try {
        payload = JSON.parse(text) as unknown;
      } catch {
        payload = null;
      }
    }
  } catch {
    payload = null;
  }

  return apiErrorFromUnknown(payload, {
    status: response.status,
    requestId: response.headers.get("x-request-id"),
    fallback,
  });
}

export function isApiError(value: unknown): value is ApiError {
  return value instanceof ApiError;
}
