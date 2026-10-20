import { describe, expect, it } from "vitest";
import {
  DEFAULT_RATE_LIMIT,
  periodSeconds,
  RateLimiter,
  type RateLimit,
} from "../src/ratelimit";

class FakeClock {
  t = 0;
  readonly slept: number[] = [];
  now = (): number => this.t;
  sleep = async (seconds: number): Promise<void> => {
    this.slept.push(seconds);
    this.t += seconds;
  };
}

function limiter(clock: FakeClock, limit: RateLimit): RateLimiter {
  return new RateLimiter(limit, { now: clock.now, sleep: clock.sleep });
}

function assertSlept(clock: FakeClock, expected: number[]): void {
  expect(clock.slept).toHaveLength(expected.length);
  clock.slept.forEach((got, i) => expect(got).toBeCloseTo(expected[i]!, 6));
}

describe("RateLimit config", () => {
  it("computes period seconds", () => {
    expect(periodSeconds({ rate: 50, period: "s" })).toBe(1);
    expect(periodSeconds({ rate: 10, periodLength: 5, period: "m" })).toBe(300);
    expect(periodSeconds({ rate: 1, period: "h" })).toBe(3600);
    expect(periodSeconds({ rate: 1, periodLength: 2, period: "d" })).toBe(
      172800,
    );
  });

  it("has a 50/s default", () => {
    expect(DEFAULT_RATE_LIMIT.rate).toBe(50);
    expect(periodSeconds(DEFAULT_RATE_LIMIT)).toBe(1);
  });

  it.each([
    [0, 1],
    [-1, 1],
    [5, 0],
    [5, -2],
  ])(
    "rejects non-positive rate/periodLength (%i, %i)",
    (rate, periodLength) => {
      expect(() => new RateLimiter({ rate, periodLength })).toThrow(/positive/);
    },
  );

  it("rejects an unknown period", () => {
    expect(
      () => new RateLimiter({ rate: 1, period: "w" as RateLimit["period"] }),
    ).toThrow(/period/);
  });
});

describe("token bucket", () => {
  it("never sleeps when disabled", async () => {
    const clock = new FakeClock();
    const disabled = new RateLimiter(null, {
      now: clock.now,
      sleep: clock.sleep,
    });
    for (let i = 0; i < 100; i++) await disabled.acquire();
    expect(clock.slept).toEqual([]);
  });

  it("spends the burst free then paces one token-interval each", async () => {
    const clock = new FakeClock();
    const lim = limiter(clock, { rate: 4, period: "s" });
    for (let i = 0; i < 4; i++) await lim.acquire();
    expect(clock.slept).toEqual([]);
    for (let i = 0; i < 3; i++) await lim.acquire();
    assertSlept(clock, [0.25, 0.25, 0.25]);
  });

  it("refills tokens as time passes", async () => {
    const clock = new FakeClock();
    const lim = limiter(clock, { rate: 2, period: "s" });
    await lim.acquire();
    await lim.acquire();
    clock.t += 1.0;
    await lim.acquire();
    await lim.acquire();
    expect(clock.slept).toEqual([]);
  });

  it("does not bank more than the burst while idle", async () => {
    const clock = new FakeClock();
    const lim = limiter(clock, { rate: 2, period: "s" });
    clock.t += 3600.0;
    for (let i = 0; i < 3; i++) await lim.acquire();
    assertSlept(clock, [0.5]);
  });

  it("refills across a multi-minute period", async () => {
    const clock = new FakeClock();
    const lim = limiter(clock, { rate: 1, periodLength: 2, period: "m" });
    await lim.acquire();
    await lim.acquire();
    assertSlept(clock, [120.0]);
  });
});
