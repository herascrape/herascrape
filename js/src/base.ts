import { randomUUID } from "node:crypto";
import {
  errorFromResponse,
  HerascrapeApiError,
  HerascrapeTransportError,
  InvalidCursorError,
  RateLimitError,
  ServiceUnavailableError,
  UpstreamError,
  type Json,
} from "./errors";
import { isRecord } from "./errors";
import { DEFAULT_RATE_LIMIT, RateLimiter, type RateLimit } from "./ratelimit";

export const DEFAULT_BASE_URL = "https://api.herascrape.com";
export const API_KEY_ENV_VAR = "HERASCRAPE_API_KEY";

export type HttpMethod = "get";
export type QueryValue = string | number | boolean;
export type QueryParams = Record<string, QueryValue | null | undefined>;

export type FetchLike = (url: string, init: RequestInit) => Promise<Response>;

const BACKOFF_BASE = 0.5;
const BACKOFF_CAP = 8.0;
const BACKOFF_JITTER = 0.5;
const MAX_RETRY_AFTER = 300.0;

export function sessionId(): string {
  return randomUUID().toUpperCase();
}

export function unwrap(payload: unknown): Record<string, unknown> {
  return (payload as { data: Record<string, unknown> }).data;
}

function dropNone(params: QueryParams | undefined): Record<string, QueryValue> {
  const out: Record<string, QueryValue> = {};
  if (!params) return out;
  for (const [name, value] of Object.entries(params)) {
    if (value !== null && value !== undefined) out[name] = value;
  }
  return out;
}

export function parseRetryAfter(value: string | null): number | null {
  if (value === null || value.trim() === "") return null;
  const seconds = Number(value);
  if (!Number.isFinite(seconds)) return null;
  return Math.max(seconds, 0);
}

function jsonObject(body: string): Record<string, Json> {
  try {
    const payload: unknown = JSON.parse(body);
    return isRecord(payload) ? payload : {};
  } catch {
    return {};
  }
}

export function parseError(opts: {
  statusCode: number;
  headers: Headers;
  body: string;
}): HerascrapeApiError {
  const payload = jsonObject(opts.body);
  const errorCode = payload["error_code"];
  return errorFromResponse({
    statusCode: opts.statusCode,
    errorCode: typeof errorCode === "string" ? errorCode : null,
    detail: payload["detail"] ?? null,
    requestId: opts.headers.get("x-request-id"),
    retryAfter: parseRetryAfter(opts.headers.get("retry-after")),
  });
}

export function backoffDelay(
  attempt: number,
  rng: () => number = Math.random,
): number {
  const delay = Math.min(BACKOFF_CAP, BACKOFF_BASE * 2 ** attempt);
  return delay * (1 - BACKOFF_JITTER * rng());
}

export function isRetryable(exc: unknown): boolean {
  return (
    exc instanceof HerascrapeTransportError ||
    exc instanceof UpstreamError ||
    exc instanceof ServiceUnavailableError ||
    exc instanceof InvalidCursorError
  );
}

export function retryDelay(exc: unknown, attempt: number): number | null {
  if (exc instanceof RateLimitError) {
    if (exc.retryAfter !== null) {
      return Math.min(exc.retryAfter, MAX_RETRY_AFTER);
    }
    return backoffDelay(attempt);
  }
  return isRetryable(exc) ? backoffDelay(attempt) : null;
}

function transportFailure(exc: unknown): HerascrapeTransportError {
  const label =
    exc instanceof Error ? `${exc.name}: ${exc.message}` : String(exc);
  return new HerascrapeTransportError(label, { cause: exc });
}

async function responseData(
  response: Response,
): Promise<Record<string, unknown>> {
  if (response.ok) {
    return unwrap(await response.json());
  }
  throw parseError({
    statusCode: response.status,
    headers: response.headers,
    body: await response.text(),
  });
}

export interface ClientOptions {
  apiKey?: string;
  baseUrl?: string;
  timeout?: number;
  maxRetries?: number;
  rateLimit?: RateLimit | null;
  fetch?: FetchLike;
  sleep?: (seconds: number) => Promise<void>;
}

async function realSleep(seconds: number): Promise<void> {
  await new Promise<void>((resolve) => setTimeout(resolve, seconds * 1000));
}

export class BaseClient {
  private readonly apiKey: string;
  private readonly baseUrl: string;
  private readonly timeoutMs: number;
  private readonly maxRetries: number;
  private readonly limiter: RateLimiter;
  private readonly fetchImpl: FetchLike;
  private readonly sleep: (seconds: number) => Promise<void>;

  constructor(options: ClientOptions = {}) {
    const key = options.apiKey ?? process.env[API_KEY_ENV_VAR];
    if (!key) {
      throw errorFromResponse({
        statusCode: 401,
        errorCode: "unauthorized",
        detail: `No API key: pass apiKey or set ${API_KEY_ENV_VAR}.`,
        requestId: null,
        retryAfter: null,
      });
    }
    this.apiKey = key;
    this.baseUrl = (options.baseUrl ?? DEFAULT_BASE_URL).replace(/\/+$/, "");
    this.timeoutMs = (options.timeout ?? 10) * 1000;
    this.maxRetries = options.maxRetries ?? 3;
    this.fetchImpl = options.fetch ?? ((url, init) => fetch(url, init));
    this.sleep = options.sleep ?? realSleep;
    const rateLimit =
      options.rateLimit === undefined ? DEFAULT_RATE_LIMIT : options.rateLimit;
    this.limiter = new RateLimiter(rateLimit, { sleep: this.sleep });
  }

  protected async request<T = Record<string, unknown>>(opts: {
    method: HttpMethod;
    path: string;
    searchParams?: QueryParams;
  }): Promise<T> {
    const query = dropNone(opts.searchParams);
    let attempt = 0;
    for (;;) {
      await this.limiter.acquire();
      try {
        return (await this.send({
          method: opts.method,
          path: opts.path,
          searchParams: query,
        })) as T;
      } catch (exc) {
        if (
          !(
            exc instanceof HerascrapeApiError ||
            exc instanceof HerascrapeTransportError
          )
        ) {
          throw exc;
        }
        const delay = retryDelay(exc, attempt);
        if (delay === null || attempt >= this.maxRetries) throw exc;
        await this.sleep(delay);
        attempt += 1;
      }
    }
  }

  private async send(opts: {
    method: HttpMethod;
    path: string;
    searchParams: Record<string, QueryValue>;
  }): Promise<Record<string, unknown>> {
    const url = this.buildUrl(opts.path, opts.searchParams);
    let response: Response;
    try {
      response = await this.fetchImpl(url, {
        method: opts.method.toUpperCase(),
        headers: { "x-api-key": this.apiKey, accept: "application/json" },
        signal: AbortSignal.timeout(this.timeoutMs),
      });
    } catch (exc) {
      throw transportFailure(exc);
    }
    return responseData(response);
  }

  private buildUrl(path: string, params: Record<string, QueryValue>): string {
    const url = new URL(this.baseUrl + path);
    for (const [name, value] of Object.entries(params)) {
      url.searchParams.set(name, String(value));
    }
    return url.toString();
  }
}
