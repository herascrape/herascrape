import asyncio
import threading
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

Period = Literal["s", "m", "h", "d"]

_PERIOD_SECONDS: dict[Period, int] = {"s": 1, "m": 60, "h": 3600, "d": 86400}


@dataclass(frozen=True)
class RateLimit:
    """At most `rate` requests per `period_length` x `period`."""

    rate: int
    period_length: int = 1
    period: Period = "s"

    def __post_init__(self) -> None:
        if self.rate < 1 or self.period_length < 1:
            raise ValueError("rate and period_length must be positive")
        if self.period not in _PERIOD_SECONDS:
            raise ValueError(f"period must be one of {list(_PERIOD_SECONDS)}")

    @property
    def period_seconds(self) -> int:
        return self.period_length * _PERIOD_SECONDS[self.period]


DEFAULT_RATE_LIMIT = RateLimit(rate=50, period="s")


class RateLimiter:
    """Client-side token bucket, safe to share across threads and tasks.

    The bucket holds `rate` tokens (the burst) and starts full, mirroring
    the API's own bucket, so steady use never trips a server-side 429.
    `limit=None` disables limiting.
    """

    def __init__(
        self,
        limit: RateLimit | None,
        *,
        now: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._limit = limit
        self._now = now
        self._sleep = sleep
        self._lock = threading.Lock()
        self._capacity = float(limit.rate) if limit else 0.0
        self._refill_per_second = (
            limit.rate / limit.period_seconds if limit else 0.0
        )
        self._tokens = self._capacity
        self._updated = now()

    def acquire(self) -> None:
        """Block until a request may be sent."""
        wait = self._reserve()
        if wait > 0:
            self._sleep(wait)

    async def aacquire(
        self,
        asleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        """Wait without blocking the event loop until a request may be sent."""
        wait = self._reserve()
        if wait > 0:
            await asleep(wait)

    def _reserve(self) -> float:
        """Take one token, going into debt if empty; return seconds to wait."""
        if self._limit is None:
            return 0.0
        with self._lock:
            current = self._now()
            elapsed = current - self._updated
            self._updated = current
            self._tokens = min(
                self._capacity, self._tokens + elapsed * self._refill_per_second
            )
            self._tokens -= 1.0
            if self._tokens >= 0.0:
                return 0.0
            return -self._tokens / self._refill_per_second
