export type Json =
  | string
  | number
  | boolean
  | null
  | Json[]
  | { [key: string]: Json };

export function isRecord(value: unknown): value is Record<string, Json> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export interface ApiErrorOptions {
  statusCode: number;
  errorCode?: string | null;
  detail?: Json;
  requestId?: string | null;
  retryAfter?: number | null;
}

function summary(opts: {
  statusCode: number;
  errorCode?: string | null;
  detail?: Json;
}): string {
  const message = isRecord(opts.detail) ? opts.detail["message"] : opts.detail;
  const head = opts.errorCode
    ? `${opts.statusCode} ${opts.errorCode}`
    : String(opts.statusCode);
  return typeof message === "string" && message ? `${head}: ${message}` : head;
}

export class HerascrapeError extends Error {
  constructor(message?: string, options?: { cause?: unknown }) {
    super(message, options);
    this.name = new.target.name;
  }
}

export class HerascrapeTransportError extends HerascrapeError {}

export class HerascrapeApiError extends HerascrapeError {
  readonly statusCode: number;
  readonly errorCode: string | null;
  readonly detail: Json;
  readonly requestId: string | null;

  constructor(opts: ApiErrorOptions) {
    super(summary(opts));
    this.statusCode = opts.statusCode;
    this.errorCode = opts.errorCode ?? null;
    this.detail = opts.detail ?? null;
    this.requestId = opts.requestId ?? null;
  }
}

export class BadRequestError extends HerascrapeApiError {}

export class InvalidCursorError extends BadRequestError {}

export class InvalidParameterError extends BadRequestError {}

export class AuthenticationError extends HerascrapeApiError {}

export class ForbiddenError extends HerascrapeApiError {}

export class PrivateAccountError extends ForbiddenError {}

export class NotFoundError extends HerascrapeApiError {}

export class ProfileNotFoundError extends NotFoundError {}

export class ValidationError extends HerascrapeApiError {
  get fieldErrors(): Record<string, string> | null {
    if (!isRecord(this.detail)) return null;
    const errors = this.detail["errors"];
    if (!isRecord(errors)) return null;
    const out: Record<string, string> = {};
    for (const [field, message] of Object.entries(errors)) {
      out[field] = String(message);
    }
    return out;
  }
}

export class RateLimitError extends HerascrapeApiError {
  readonly retryAfter: number | null;

  constructor(opts: ApiErrorOptions) {
    super(opts);
    this.retryAfter = opts.retryAfter ?? null;
  }
}

export class ServerError extends HerascrapeApiError {}

export class InternalError extends ServerError {}

export class UpstreamError extends ServerError {}

export class ServiceUnavailableError extends ServerError {}

type ApiErrorCtor = new (opts: ApiErrorOptions) => HerascrapeApiError;

const BY_CODE: Record<string, ApiErrorCtor> = {
  "400:bad_request": BadRequestError,
  "400:invalid_cursor": InvalidCursorError,
  "400:invalid_parameter": InvalidParameterError,
  "401:unauthorized": AuthenticationError,
  "403:forbidden": ForbiddenError,
  "403:private_account": PrivateAccountError,
  "404:not_found": NotFoundError,
  "404:profile_not_found": ProfileNotFoundError,
  "422:unprocessable_entity": ValidationError,
  "429:too_many_requests": RateLimitError,
  "500:internal_error": InternalError,
  "502:upstream_error": UpstreamError,
  "503:upstream_unavailable": ServiceUnavailableError,
};

const BY_STATUS: Record<number, ApiErrorCtor> = {
  400: BadRequestError,
  401: AuthenticationError,
  403: ForbiddenError,
  404: NotFoundError,
  422: ValidationError,
  429: RateLimitError,
  500: InternalError,
  502: UpstreamError,
  503: ServiceUnavailableError,
};

function errorClassFor(
  statusCode: number,
  errorCode: string | null,
): ApiErrorCtor {
  if (errorCode !== null) {
    const byCode = BY_CODE[`${statusCode}:${errorCode}`];
    if (byCode) return byCode;
  }
  const byStatus = BY_STATUS[statusCode];
  if (byStatus) return byStatus;
  return statusCode >= 500 ? ServerError : HerascrapeApiError;
}

export function errorFromResponse(opts: {
  statusCode: number;
  errorCode: string | null;
  detail: Json;
  requestId: string | null;
  retryAfter: number | null;
}): HerascrapeApiError {
  const Ctor = errorClassFor(opts.statusCode, opts.errorCode);
  return new Ctor({
    statusCode: opts.statusCode,
    errorCode: opts.errorCode,
    detail: opts.detail,
    requestId: opts.requestId,
    retryAfter: opts.retryAfter,
  });
}
