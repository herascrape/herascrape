import dataclasses
import math

import pytest

from herascrape.ratelimit import DEFAULT_RATE_LIMIT, RateLimit, RateLimiter


class FakeClock:
    """Manual clock whose sleep advances time instead of waiting."""

    def __init__(self) -> None:
        self.t = 0.0
        self.slept: list[float] = []

    def now(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.t += seconds

    async def asleep(self, seconds: float) -> None:
        self.sleep(seconds)


def _limiter(clock: FakeClock, limit: RateLimit) -> RateLimiter:
    return RateLimiter(limit, now=clock.now, sleep=clock.sleep)


def _assert_slept(clock: FakeClock, expected: list[float]) -> None:
    assert len(clock.slept) == len(expected)
    for got, want in zip(clock.slept, expected, strict=True):
        assert math.isclose(got, want, rel_tol=1e-6)


def test_ratelimit_period_seconds():
    assert RateLimit(rate=50, period="s").period_seconds == 1
    assert RateLimit(rate=10, period_length=5, period="m").period_seconds == 300
    assert RateLimit(rate=1, period="h").period_seconds == 3600
    assert RateLimit(rate=1, period_length=2, period="d").period_seconds == (
        172800
    )


def test_ratelimit_is_frozen():
    limit = RateLimit(rate=5)
    with pytest.raises(dataclasses.FrozenInstanceError):
        limit.rate = 6  # pyright: ignore[reportAttributeAccessIssue]


@pytest.mark.parametrize(
    ("rate", "period_length"), [(0, 1), (-1, 1), (5, 0), (5, -2)]
)
def test_ratelimit_rejects_non_positive(rate: int, period_length: int):
    with pytest.raises(ValueError, match="positive"):
        RateLimit(rate=rate, period_length=period_length)


def test_ratelimit_rejects_unknown_period():
    with pytest.raises(ValueError, match="period"):
        RateLimit(rate=1, period="w")  # pyright: ignore[reportArgumentType]


def test_default_rate_limit():
    assert DEFAULT_RATE_LIMIT.rate == 50
    assert DEFAULT_RATE_LIMIT.period_seconds == 1


def test_disabled_never_sleeps():
    slept: list[float] = []
    RateLimiter(None, sleep=slept.append).acquire()
    RateLimiter(None, sleep=slept.append).acquire()
    assert slept == []


@pytest.mark.asyncio
async def test_disabled_never_asleeps():
    clock = FakeClock()
    limiter = RateLimiter(None, now=clock.now, sleep=clock.sleep)
    for _ in range(100):
        await limiter.aacquire(clock.asleep)
    assert clock.slept == []


def test_paces_after_burst():
    clock = FakeClock()
    limiter = _limiter(clock, RateLimit(rate=2, period="s"))
    for _ in range(4):
        limiter.acquire()
    assert sum(clock.slept) > 0


def test_burst_equals_rate_then_one_token_interval_each():
    clock = FakeClock()
    limiter = _limiter(clock, RateLimit(rate=4, period="s"))
    for _ in range(4):
        limiter.acquire()
    assert clock.slept == []
    for _ in range(3):
        limiter.acquire()
    _assert_slept(clock, [0.25] * 3)


def test_tokens_refill_with_time():
    clock = FakeClock()
    limiter = _limiter(clock, RateLimit(rate=2, period="s"))
    limiter.acquire()
    limiter.acquire()
    clock.t += 1.0
    limiter.acquire()
    limiter.acquire()
    assert clock.slept == []


def test_idle_time_does_not_bank_more_than_burst():
    clock = FakeClock()
    limiter = _limiter(clock, RateLimit(rate=2, period="s"))
    clock.t += 3600.0
    for _ in range(3):
        limiter.acquire()
    _assert_slept(clock, [0.5])


def test_slow_limit_refills_per_period():
    clock = FakeClock()
    limiter = _limiter(clock, RateLimit(rate=1, period_length=2, period="m"))
    limiter.acquire()
    limiter.acquire()
    _assert_slept(clock, [120.0])


@pytest.mark.asyncio
async def test_async_mirrors_sync_pacing():
    clock = FakeClock()
    limiter = _limiter(clock, RateLimit(rate=2, period="s"))
    for _ in range(4):
        await limiter.aacquire(clock.asleep)
    _assert_slept(clock, [0.5] * 2)


@pytest.mark.asyncio
async def test_async_and_sync_share_one_bucket():
    clock = FakeClock()
    limiter = _limiter(clock, RateLimit(rate=1, period="s"))
    limiter.acquire()
    await limiter.aacquire(clock.asleep)
    _assert_slept(clock, [1.0])
