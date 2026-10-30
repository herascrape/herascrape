export const VERSION = "0.1.7";

export { Client } from "./client";
export type { ClientOptions } from "./base";
export { DEFAULT_RATE_LIMIT, type Period, type RateLimit } from "./ratelimit";
export type { BalanceResponse, MediaIdResolution, Page } from "./types";
export type { Json } from "./errors";
export {
  AuthenticationError,
  BadRequestError,
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
} from "./errors";
