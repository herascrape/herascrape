export type Period = "s" | "m" | "h" | "d";

const PERIOD_SECONDS: Record<Period, number> = {
  s: 1,
  m: 60,
  h: 3600,
  d: 86400,
};

export interface RateLimit {
  readonly rate: number;
  readonly periodLength?: number;
  readonly period?: Period;
}

export const DEFAULT_RATE_LIMIT: RateLimit = { rate: 50, period: "s" };

export function periodSeconds(limit: RateLimit): number {
  return (limit.periodLength ?? 1) * PERIOD_SECONDS[limit.period ?? "s"];
}

function validate(limit: RateLimit): void {
  if (limit.rate < 1 || (limit.periodLength ?? 1) < 1) {
    throw new Error("rate and periodLength must be positive");
  }
  if (!((limit.period ?? "s") in PERIOD_SECONDS)) {
    throw new Error('period must be one of ["s", "m", "h", "d"]');
  }
}

function monotonicSeconds(): number {
  return performance.now() / 1000;
}

async function realSleep(seconds: number): Promise<void> {
  await new Promise<void>((resolve) => setTimeout(resolve, seconds * 1000));
}

/**
 * Client-side token bucket, mirroring the API's own bucket so steady use
 * never trips a server-side 429. A `null` limit disables limiting.
 */
export class RateLimiter {
  private readonly limit: RateLimit | null;
  private readonly now: () => number;
  private readonly sleep: (seconds: number) => Promise<void>;
  private readonly capacity: number;
  private readonly refillPerSecond: number;
  private tokens: number;
  private updated: number;

  constructor(
    limit: RateLimit | null,
    opts: {
      now?: () => number;
      sleep?: (seconds: number) => Promise<void>;
    } = {},
  ) {
    if (limit) validate(limit);
    this.limit = limit;
    this.now = opts.now ?? monotonicSeconds;
    this.sleep = opts.sleep ?? realSleep;
    this.capacity = limit ? limit.rate : 0;
    this.refillPerSecond = limit ? limit.rate / periodSeconds(limit) : 0;
    this.tokens = this.capacity;
    this.updated = this.now();
  }

  async acquire(): Promise<void> {
    const wait = this.reserve();
    if (wait > 0) await this.sleep(wait);
  }

  private reserve(): number {
    if (this.limit === null) return 0;
    const current = this.now();
    const elapsed = current - this.updated;
    this.updated = current;
    this.tokens = Math.min(
      this.capacity,
      this.tokens + elapsed * this.refillPerSecond,
    );
    this.tokens -= 1;
    if (this.tokens >= 0) return 0;
    return -this.tokens / this.refillPerSecond;
  }
}
