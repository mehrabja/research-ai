export type ApiErrorPayload = {
  detail?: unknown;
  message?: unknown;
  error?: unknown;
  code?: unknown;
  request_id?: unknown;
  retry_after?: unknown;
  details?: unknown;
  extra?: unknown;
};

type StructuredApiError = {
  code?: unknown;
  message?: unknown;
  request_id?: unknown;
  retry_after?: unknown;
  details?: unknown;
  extra?: unknown;
};

export class ApiError extends Error {
  readonly status: number;
  readonly code: string | null;
  readonly requestId: string | null;
  readonly retryable: boolean;
  readonly retryAfter: number | null;
  readonly details: unknown;

  constructor(
    message: string,
    options: {
      status?: number;
      code?: string | null;
      requestId?: string | null;
      retryable?: boolean;
      retryAfter?: number | null;
      details?: unknown;
    } = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.status = options.status ?? 0;
    this.code = options.code ?? null;
    this.requestId = options.requestId ?? null;
    this.retryAfter = options.retryAfter ?? null;
    this.details = options.details;
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

  const nested =
    payload?.error &&
    typeof payload.error === "object" &&
    payload.error !== null
      ? (payload.error as StructuredApiError)
      : null;

  const codeValue = nested?.code ?? payload?.code;
  const requestIdValue = nested?.request_id ?? payload?.request_id;
  const retryAfterValue = nested?.retry_after ?? payload?.retry_after;
  const details =
    nested?.details ??
    nested?.extra ??
    payload?.details ??
    payload?.extra;

  const message =
    (typeof nested?.message === "string" && nested.message) ||
    (typeof payload?.detail === "string" && payload.detail) ||
    (typeof payload?.message === "string" && payload.message) ||
    (typeof payload?.error === "string" && payload.error) ||
    options.fallback ||
    "API request failed";

  return new ApiError(message, {
    status: options.status,
    code: typeof codeValue === "string" ? codeValue : null,
    requestId:
      typeof requestIdValue === "string"
        ? requestIdValue
        : options.requestId,
    retryAfter:
      typeof retryAfterValue === "number"
        ? retryAfterValue
        : null,
    details,
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
