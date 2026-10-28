import { afterEach, describe, expect, it } from "vitest";
import {
  BaseClient,
  backoffDelay,
  isRetryable,
  parseError,
  parseRetryAfter,
  retryDelay,
  unwrap,
  type ClientOptions,
  type FetchLike,
  type QueryParams,
} from "../src/base";
import {
  AuthenticationError,
  BadRequestError,
  HerascrapeTransportError,
  InternalError,
  InvalidCursorError,
  InvalidParameterError,
  NotFoundError,
  RateLimitError,
  ServiceUnavailableError,
  UpstreamError,
} from "../src/errors";
import type { RateLimit } from "../src/ratelimit";

const API_KEY = "hs_live_xxxxxxxx";

type Reply = Response | Error;

class FakeTimeout extends Error {}

class Script {
  private readonly replies: Reply[];
  readonly requests: { url: string; init: RequestInit }[] = [];

  constructor(...replies: Reply[]) {
    this.replies = replies;
  }

  fetch: FetchLike = async (url, init) => {
    this.requests.push({ url, init });
    const reply = this.replies.shift();
    if (reply === undefined) throw new Error("script exhausted");
    if (reply instanceof Error) throw reply;
    return reply;
  };
}

class TestClient extends BaseClient {
  get(path: string, params?: QueryParams): Promise<Record<string, unknown>> {
    return this.request({ method: "get", path, searchParams: params });
  }
}

function make(
  replies: Reply[],
  opts: { maxRetries?: number; rateLimit?: RateLimit | null } = {},
): { client: TestClient; script: Script; sleeps: number[] } {
  const script = new Script(...replies);
  const sleeps: number[] = [];
  const config: ClientOptions = {
    apiKey: API_KEY,
    maxRetries: opts.maxRetries ?? 3,
    rateLimit: opts.rateLimit ?? null,
    fetch: script.fetch,
    sleep: async (seconds) => {
      sleeps.push(seconds);
    },
  };
  return { client: new TestClient(config), script, sleeps };
}

function ok(data: unknown = null): Response {
  return new Response(JSON.stringify(data), {
    status: 200,
  });
}

function errorResponse(
  status: number,
  errorCode: string,
  opts: { detail?: string; headers?: Record<string, string> } = {},
): Response {
  return new Response(
    JSON.stringify({
      status: "error",
      error_code: errorCode,
      detail: opts.detail ?? "nope",
    }),
    { status, headers: opts.headers },
  );
}

function assertBackoff(delay: number, attempt: number): void {
  const lowest = backoffDelay(attempt, () => 1.0);
  const highest = backoffDelay(attempt, () => 0.0);
  expect(delay).toBeGreaterThanOrEqual(lowest);
  expect(delay).toBeLessThanOrEqual(highest);
}

afterEach(() => {
  delete process.env.HERASCRAPE_API_KEY;
});

describe("transport", () => {
  it("returns the response body", async () => {
    const { client } = make([ok({ pk: "1" })]);
    expect(await client.get("/users/1")).toEqual({ pk: "1" });
  });

  it("unwrap returns the body unchanged", () => {
    expect(unwrap({ items: [1], data: 5 })).toEqual({ items: [1], data: 5 });
  });

  it("sends the api key and accept headers to the right url", async () => {
    const { client, script } = make([ok({})]);
    await client.get("/users/1");
    const { url, init } = script.requests[0]!;
    const headers = init.headers as Record<string, string>;
    expect(headers["x-api-key"]).toBe(API_KEY);
    expect(headers["accept"]).toBe("application/json");
    expect(url).toBe("https://api.herascrape.com/users/1");
  });

  it("drops null and undefined query params", async () => {
    const { client, script } = make([ok({})]);
    await client.get("/search", { cursor: null, q: "x", page: undefined });
    const url = new URL(script.requests[0]!.url);
    expect(Object.fromEntries(url.searchParams)).toEqual({ q: "x" });
  });
});

describe("error mapping", () => {
  it("maps 404 not_found without retry", async () => {
    const { client, script, sleeps } = make([errorResponse(404, "not_found")]);
    await expect(client.get("/users/1")).rejects.toBeInstanceOf(NotFoundError);
    expect(script.requests).toHaveLength(1);
    expect(sleeps).toEqual([]);
  });

  it("surfaces the request id from the header", async () => {
    const { client } = make([
      errorResponse(404, "not_found", { headers: { "x-request-id": "req-1" } }),
    ]);
    await expect(client.get("/users/1")).rejects.toMatchObject({
      requestId: "req-1",
    });
  });

  it("maps a malformed error body to a generic api error", async () => {
    const { client } = make([new Response("oops", { status: 500 })]);
    await expect(client.get("/users/1")).rejects.toMatchObject({
      statusCode: 500,
      errorCode: null,
    });
  });

  it("does not retry 400 invalid_parameter", async () => {
    const { client, script } = make([errorResponse(400, "invalid_parameter")]);
    await expect(client.get("/users/1")).rejects.toBeInstanceOf(
      InvalidParameterError,
    );
    expect(script.requests).toHaveLength(1);
  });

  it("does not retry 500 internal_error", async () => {
    const { client, script } = make([errorResponse(500, "internal_error")]);
    await expect(client.get("/users/1")).rejects.toBeInstanceOf(InternalError);
    expect(script.requests).toHaveLength(1);
  });
});

describe("retries", () => {
  it("retries 503 then succeeds", async () => {
    const { client, script, sleeps } = make([
      errorResponse(503, "upstream_unavailable"),
      ok({ pk: "1" }),
    ]);
    expect(await client.get("/users/1")).toEqual({ pk: "1" });
    expect(script.requests).toHaveLength(2);
    expect(sleeps).toHaveLength(1);
    assertBackoff(sleeps[0]!, 0);
  });

  it("retries a bare 503 without a body", async () => {
    const { client, script } = make([
      new Response(null, { status: 503 }),
      ok({ pk: "1" }),
    ]);
    expect(await client.get("/users/1")).toEqual({ pk: "1" });
    expect(script.requests).toHaveLength(2);
  });

  it("raises UpstreamError after exhausting retries on 502", async () => {
    const { client, script, sleeps } = make(
      Array.from({ length: 4 }, () => new Response(null, { status: 502 })),
      { maxRetries: 3 },
    );
    await expect(client.get("/users/1")).rejects.toBeInstanceOf(UpstreamError);
    expect(script.requests).toHaveLength(4);
    expect(sleeps).toHaveLength(3);
    sleeps.forEach((delay, attempt) => assertBackoff(delay, attempt));
  });

  it("retries invalid_cursor", async () => {
    const { client, script, sleeps } = make([
      errorResponse(400, "invalid_cursor"),
      ok({ items: [] }),
    ]);
    expect(await client.get("/users/1/posts")).toEqual({ items: [] });
    expect(script.requests).toHaveLength(2);
    expect(sleeps).toHaveLength(1);
  });

  it("retries a transport error then succeeds", async () => {
    const { client, script, sleeps } = make([
      new Error("ECONNREFUSED"),
      ok({ pk: "1" }),
    ]);
    expect(await client.get("/users/1")).toEqual({ pk: "1" });
    expect(script.requests).toHaveLength(2);
    expect(sleeps).toHaveLength(1);
  });

  it("wraps a timeout as a transport error carrying the cause", async () => {
    const timeout = new FakeTimeout("slow");
    const { client, script, sleeps } = make(
      Array.from({ length: 3 }, () => timeout),
      { maxRetries: 2 },
    );
    const error = await client.get("/users/1").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(HerascrapeTransportError);
    expect((error as HerascrapeTransportError).cause).toBe(timeout);
    expect(script.requests).toHaveLength(3);
    expect(sleeps).toHaveLength(2);
  });
});

describe("429 handling", () => {
  it("waits and retries with no Retry-After", async () => {
    const { client, script, sleeps } = make([
      errorResponse(429, "too_many_requests"),
      ok({ pk: "1" }),
    ]);
    expect(await client.get("/users/1")).toEqual({ pk: "1" });
    expect(script.requests).toHaveLength(2);
    expect(sleeps).toHaveLength(1);
    assertBackoff(sleeps[0]!, 0);
  });

  it("honors a numeric Retry-After header", async () => {
    const { client, sleeps } = make([
      errorResponse(429, "too_many_requests", {
        headers: { "Retry-After": "2" },
      }),
      ok({ pk: "1" }),
    ]);
    await client.get("/users/1");
    expect(sleeps).toEqual([2.0]);
  });

  it("caps the Retry-After wait at 300 seconds", async () => {
    const { client, sleeps } = make([
      errorResponse(429, "too_many_requests", {
        headers: { "Retry-After": "86400" },
      }),
      ok({ pk: "1" }),
    ]);
    await client.get("/users/1");
    expect(sleeps).toEqual([300.0]);
  });

  it("raises RateLimitError once retries are exhausted", async () => {
    const { client, script, sleeps } = make(
      Array.from({ length: 3 }, () => errorResponse(429, "too_many_requests")),
      { maxRetries: 2 },
    );
    await expect(client.get("/users/1")).rejects.toBeInstanceOf(RateLimitError);
    expect(script.requests).toHaveLength(3);
    expect(sleeps).toHaveLength(2);
  });
});

describe("rate limiter", () => {
  it("is acquired before every attempt", async () => {
    const { client, script, sleeps } = make(
      [errorResponse(503, "upstream_unavailable"), ok({}), ok({})],
      { rateLimit: { rate: 1, period: "s" } },
    );
    await client.get("/a");
    await client.get("/b");
    expect(script.requests).toHaveLength(3);
    expect(sleeps).toHaveLength(3);
    assertBackoff(sleeps[0]!, 0);
    expect(Math.abs(sleeps[1]! - 1.0)).toBeLessThan(0.15);
    expect(Math.abs(sleeps[2]! - 2.0)).toBeLessThan(0.15);
  });
});

describe("api key", () => {
  it("falls back to the environment variable", async () => {
    process.env.HERASCRAPE_API_KEY = "hs_live_fromenv";
    const script = new Script(ok({}));
    const client = new TestClient({ rateLimit: null, fetch: script.fetch });
    await client.get("/users/1");
    const headers = script.requests[0]!.init.headers as Record<string, string>;
    expect(headers["x-api-key"]).toBe("hs_live_fromenv");
  });

  it("throws AuthenticationError when missing", () => {
    expect(() => new TestClient({ rateLimit: null })).toThrow(
      AuthenticationError,
    );
    expect(() => new TestClient({ apiKey: "", rateLimit: null })).toThrow(
      /HERASCRAPE_API_KEY/,
    );
  });
});

describe("pure helpers", () => {
  it("parseError reads the body and headers", () => {
    const error = parseError({
      statusCode: 429,
      headers: new Headers({ "x-request-id": "r1", "retry-after": "3" }),
      body: '{"error_code": "too_many_requests", "detail": "slow down"}',
    });
    expect(error).toBeInstanceOf(RateLimitError);
    expect(error.errorCode).toBe("too_many_requests");
    expect(error.detail).toBe("slow down");
    expect(error.requestId).toBe("r1");
    expect((error as RateLimitError).retryAfter).toBe(3.0);
  });

  it.each([
    [null, null],
    ["1.5", 1.5],
    ["0", 0.0],
    ["-5", 0.0],
    ["soon", null],
    ["Wed, 21 Oct 2026 07:28:00 GMT", null],
    ["inf", null],
    ["nan", null],
    ["", null],
  ])("parseRetryAfter(%o) is %o", (header, expected) => {
    expect(parseRetryAfter(header)).toBe(expected);
  });

  it("isRetryable keys on the exception class", () => {
    expect(isRetryable(new HerascrapeTransportError("down"))).toBe(true);
    expect(isRetryable(new UpstreamError({ statusCode: 502 }))).toBe(true);
    expect(isRetryable(new ServiceUnavailableError({ statusCode: 503 }))).toBe(
      true,
    );
    expect(isRetryable(new InvalidCursorError({ statusCode: 400 }))).toBe(true);
    expect(isRetryable(new InternalError({ statusCode: 500 }))).toBe(false);
    expect(isRetryable(new BadRequestError({ statusCode: 400 }))).toBe(false);
    expect(isRetryable(new NotFoundError({ statusCode: 404 }))).toBe(false);
    expect(isRetryable(new RateLimitError({ statusCode: 429 }))).toBe(false);
  });

  it("retryDelay covers rate limits and final errors", () => {
    expect(
      retryDelay(new RateLimitError({ statusCode: 429 }), 1),
    ).not.toBeNull();
    expect(
      retryDelay(new RateLimitError({ statusCode: 429, retryAfter: 4.0 }), 1),
    ).toBe(4.0);
    expect(retryDelay(new NotFoundError({ statusCode: 404 }), 0)).toBeNull();
  });

  it("backoffDelay grows, is capped, and jitters within half-to-full", () => {
    const delays = Array.from({ length: 12 }, (_, n) =>
      backoffDelay(n, () => 0),
    );
    expect(delays).toEqual([...delays].sort((a, b) => a - b));
    expect(delays[0]).toBe(0.5);
    expect(delays[1]).toBe(2 * delays[0]!);
    expect(delays[11]).toBe(8.0);
    expect(delays[10]).toBe(8.0);
    const full = backoffDelay(2, () => 0);
    expect(backoffDelay(2, () => 1)).toBe(full / 2);
    expect(backoffDelay(2, () => 0.5)).toBe(full * 0.75);
  });
});
