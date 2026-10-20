import { describe, expect, it } from "vitest";
import {
  AuthenticationError,
  BadRequestError,
  errorFromResponse,
  ForbiddenError,
  HerascrapeApiError,
  HerascrapeError,
  HerascrapeTransportError,
  InternalError,
  InvalidCursorError,
  InvalidParameterError,
  NotFoundError,
  PrivateAccountError,
  ProfileNotFoundError,
  RateLimitError,
  ServerError,
  ServiceUnavailableError,
  UpstreamError,
  ValidationError,
  type Json,
} from "../src/errors";

function map(opts: {
  statusCode: number;
  errorCode?: string | null;
  detail?: Json;
  requestId?: string | null;
  retryAfter?: number | null;
}): HerascrapeApiError {
  return errorFromResponse({
    statusCode: opts.statusCode,
    errorCode: opts.errorCode ?? null,
    detail: opts.detail ?? "",
    requestId: opts.requestId ?? null,
    retryAfter: opts.retryAfter ?? null,
  });
}

const CATALOG: [
  number,
  string,
  new (...args: never[]) => HerascrapeApiError,
][] = [
  [400, "bad_request", BadRequestError],
  [400, "invalid_cursor", InvalidCursorError],
  [400, "invalid_parameter", InvalidParameterError],
  [401, "unauthorized", AuthenticationError],
  [403, "forbidden", ForbiddenError],
  [403, "private_account", PrivateAccountError],
  [404, "not_found", NotFoundError],
  [404, "profile_not_found", ProfileNotFoundError],
  [422, "unprocessable_entity", ValidationError],
  [429, "too_many_requests", RateLimitError],
  [500, "internal_error", InternalError],
  [502, "upstream_error", UpstreamError],
  [503, "upstream_unavailable", ServiceUnavailableError],
];

describe("error code mapping", () => {
  it.each(CATALOG)(
    "%i %s maps to its exact class",
    (statusCode, errorCode, cls) => {
      const error = map({ statusCode, errorCode });
      expect(error.constructor).toBe(cls);
    },
  );

  it.each([
    [400, BadRequestError],
    [401, AuthenticationError],
    [403, ForbiddenError],
    [404, NotFoundError],
    [422, ValidationError],
    [429, RateLimitError],
    [500, InternalError],
    [502, UpstreamError],
    [503, ServiceUnavailableError],
    [504, ServerError],
  ])("unknown code at %i falls back by status", (statusCode, cls) => {
    expect(map({ statusCode, errorCode: "something_new" }).constructor).toBe(
      cls,
    );
  });

  it("an unknown status with no code is a bare HerascrapeApiError", () => {
    const error = map({ statusCode: 418, detail: null });
    expect(error.constructor).toBe(HerascrapeApiError);
    expect(error.statusCode).toBe(418);
  });

  it("a known code under the wrong status falls back by status", () => {
    expect(
      map({ statusCode: 404, errorCode: "private_account" }).constructor,
    ).toBe(NotFoundError);
  });
});

describe("error hierarchy", () => {
  it("roots at HerascrapeError", () => {
    expect(new HerascrapeApiError({ statusCode: 400 })).toBeInstanceOf(
      HerascrapeError,
    );
    expect(new HerascrapeTransportError("x")).toBeInstanceOf(HerascrapeError);
    expect(new HerascrapeTransportError("x")).not.toBeInstanceOf(
      HerascrapeApiError,
    );
  });

  it("groups the bad-request and server families", () => {
    expect(new InvalidCursorError({ statusCode: 400 })).toBeInstanceOf(
      BadRequestError,
    );
    expect(new InvalidParameterError({ statusCode: 400 })).toBeInstanceOf(
      BadRequestError,
    );
    expect(new InternalError({ statusCode: 500 })).toBeInstanceOf(ServerError);
    expect(new UpstreamError({ statusCode: 502 })).toBeInstanceOf(ServerError);
    expect(new ServiceUnavailableError({ statusCode: 503 })).toBeInstanceOf(
      ServerError,
    );
    expect(new ProfileNotFoundError({ statusCode: 404 })).toBeInstanceOf(
      NotFoundError,
    );
    expect(new PrivateAccountError({ statusCode: 403 })).toBeInstanceOf(
      ForbiddenError,
    );
  });
});

describe("error attributes", () => {
  it("carries status, code, detail and request id with a summary message", () => {
    const error = map({
      statusCode: 404,
      errorCode: "profile_not_found",
      detail: { message: "No such user" },
      requestId: "r2",
    });
    expect([error.statusCode, error.errorCode, error.requestId]).toEqual([
      404,
      "profile_not_found",
      "r2",
    ]);
    expect(error.message).toBe("404 profile_not_found: No such user");
    expect(error.name).toBe("ProfileNotFoundError");
  });

  it("renders a code-less, detail-less message as the status alone", () => {
    expect(map({ statusCode: 418, detail: null }).message).toBe("418");
  });

  it("rate limit carries retryAfter", () => {
    const error = map({
      statusCode: 429,
      errorCode: "too_many_requests",
      retryAfter: 4.0,
    });
    expect(error).toBeInstanceOf(RateLimitError);
    expect((error as RateLimitError).retryAfter).toBe(4.0);
  });

  it("429 with an unknown code is still a rate limit with retryAfter", () => {
    const error = map({
      statusCode: 429,
      errorCode: "something_new",
      retryAfter: 7.5,
    });
    expect(error.constructor).toBe(RateLimitError);
    expect((error as RateLimitError).retryAfter).toBe(7.5);
  });
});

describe("validation field errors", () => {
  it("exposes per-field messages from a dict detail", () => {
    const error = map({
      statusCode: 422,
      errorCode: "unprocessable_entity",
      detail: { message: "bad", errors: { query: "required" } },
    });
    expect(error).toBeInstanceOf(ValidationError);
    expect((error as ValidationError).fieldErrors).toEqual({
      query: "required",
    });
  });

  it.each([
    ["a string detail", "Invalid request data" as Json],
    ["a dict without errors", { message: "bad" } as Json],
    ["a non-dict errors value", { errors: ["query"] } as Json],
  ])("returns null for %s", (_label, detail) => {
    const error = map({
      statusCode: 422,
      errorCode: "unprocessable_entity",
      detail,
    });
    expect((error as ValidationError).fieldErrors).toBeNull();
  });
});
