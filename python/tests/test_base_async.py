import math
from collections.abc import Mapping
from typing import Any

import httpx
import pytest

from herascrape._base import DEFAULT_BASE_URL, BaseAsyncClient, backoff_delay
from herascrape._errors import (
    AuthenticationError,
    HerascrapeTransportError,
    NotFoundError,
    RateLimitError,
    UpstreamError,
)
from herascrape.ratelimit import RateLimit

API_KEY = "hs_live_xxxxxxxx"


class Script:
    """MockTransport handler replaying a fixed list of replies."""

    def __init__(self, *replies: httpx.Response | Exception) -> None:
        self._replies = list(replies)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        reply = self._replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


class Client(BaseAsyncClient):
    async def get(
        self, path: str, *, params: Mapping[str, Any] | None = None
    ) -> Any:
        return await self._request(method="get", path=path, params=params)

    @property
    def closed(self) -> bool:
        return self._client.is_closed


def _make(
    *replies: httpx.Response | Exception,
    max_retries: int = 3,
    rate_limit: RateLimit | None = None,
) -> tuple[Client, Script, list[float]]:
    script = Script(*replies)
    sleeps: list[float] = []

    async def asleep(seconds: float) -> None:
        sleeps.append(seconds)

    client = Client(
        API_KEY,
        max_retries=max_retries,
        rate_limit=rate_limit,
        transport=httpx.MockTransport(script),
        asleep=asleep,
    )
    return client, script, sleeps


def _ok(data: object = None) -> httpx.Response:
    return httpx.Response(200, json={"status": "success", "data": data})


def _error(
    status_code: int,
    error_code: str,
    *,
    detail: str = "nope",
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    return httpx.Response(
        status_code,
        json={"status": "error", "error_code": error_code, "detail": detail},
        headers=headers,
    )


def _assert_backoff(delay: float, *, attempt: int) -> None:
    lowest = backoff_delay(attempt, rng=lambda: 1.0)
    highest = backoff_delay(attempt, rng=lambda: 0.0)
    assert lowest <= delay <= highest


@pytest.mark.asyncio
async def test_async_unwraps_data():
    client, _, _ = _make(_ok({"pk": "1"}))
    assert await client.get("/users/1") == {"pk": "1"}


@pytest.mark.asyncio
async def test_async_sends_api_key_and_accept_headers():
    client, script, _ = _make(_ok({}))
    await client.get("/users/1")
    request = script.requests[0]
    assert request.headers["x-api-key"] == API_KEY
    assert request.headers["accept"] == "application/json"
    assert str(request.url) == f"{DEFAULT_BASE_URL}/users/1"


@pytest.mark.asyncio
async def test_async_none_params_dropped():
    client, script, _ = _make(_ok({}))
    await client.get("/search", params={"cursor": None, "q": "x"})
    assert dict(script.requests[0].url.params) == {"q": "x"}


@pytest.mark.asyncio
async def test_async_maps_404_not_found_without_retry():
    client, script, sleeps = _make(_error(404, "not_found"))
    with pytest.raises(NotFoundError) as caught:
        await client.get("/users/1")
    assert caught.value.status_code == 404
    assert len(script.requests) == 1
    assert sleeps == []


@pytest.mark.asyncio
async def test_async_surfaces_request_id():
    client, _, _ = _make(
        _error(404, "not_found", headers={"x-request-id": "req-123"})
    )
    with pytest.raises(NotFoundError) as caught:
        await client.get("/users/1")
    assert caught.value.request_id == "req-123"


@pytest.mark.asyncio
async def test_async_retries_503():
    client, script, sleeps = _make(
        _error(503, "upstream_unavailable"), _ok({"pk": "1"})
    )
    assert await client.get("/users/1") == {"pk": "1"}
    assert len(script.requests) == 2
    assert len(sleeps) == 1
    _assert_backoff(sleeps[0], attempt=0)


@pytest.mark.asyncio
async def test_async_retries_exhausted_raise_last_error():
    client, script, sleeps = _make(
        *[httpx.Response(502) for _ in range(4)], max_retries=3
    )
    with pytest.raises(UpstreamError):
        await client.get("/users/1")
    assert len(script.requests) == 4
    assert len(sleeps) == 3


@pytest.mark.asyncio
async def test_async_429_waits_and_retries():
    client, script, sleeps = _make(
        _error(429, "too_many_requests"), _ok({"pk": "1"})
    )
    assert await client.get("/users/1") == {"pk": "1"}
    assert len(script.requests) == 2
    assert len(sleeps) == 1
    _assert_backoff(sleeps[0], attempt=0)


@pytest.mark.asyncio
async def test_async_429_honors_retry_after_header():
    client, _, sleeps = _make(
        _error(429, "too_many_requests", headers={"Retry-After": "2"}),
        _ok({"pk": "1"}),
    )
    assert await client.get("/users/1") == {"pk": "1"}
    assert sleeps == [2.0]


@pytest.mark.asyncio
async def test_async_429_exhausted_raises_rate_limit():
    client, script, sleeps = _make(
        *[_error(429, "too_many_requests") for _ in range(3)], max_retries=2
    )
    with pytest.raises(RateLimitError):
        await client.get("/users/1")
    assert len(script.requests) == 3
    assert len(sleeps) == 2


@pytest.mark.asyncio
async def test_async_transport_error_retried_then_succeeds():
    client, script, sleeps = _make(
        httpx.ConnectError("refused"), _ok({"pk": "1"})
    )
    assert await client.get("/users/1") == {"pk": "1"}
    assert len(script.requests) == 2
    assert len(sleeps) == 1


@pytest.mark.asyncio
async def test_async_timeout_wrapped_as_transport_error():
    client, script, sleeps = _make(
        *[httpx.ReadTimeout("slow") for _ in range(3)], max_retries=2
    )
    with pytest.raises(HerascrapeTransportError) as caught:
        await client.get("/users/1")
    assert isinstance(caught.value.__cause__, httpx.ReadTimeout)
    assert len(script.requests) == 3
    assert len(sleeps) == 2


@pytest.mark.asyncio
async def test_async_rate_limiter_acquired_before_every_attempt():
    client, script, sleeps = _make(
        _error(503, "upstream_unavailable"),
        _ok({}),
        _ok({}),
        rate_limit=RateLimit(rate=1, period="s"),
    )
    await client.get("/a")
    await client.get("/b")
    assert len(script.requests) == 3
    # One-token bucket and a frozen sleep: the retry backoff comes first,
    # then each later attempt queues one more second behind the last.
    assert len(sleeps) == 3
    _assert_backoff(sleeps[0], attempt=0)
    assert math.isclose(sleeps[1], 1.0, abs_tol=0.1)
    assert math.isclose(sleeps[2], 2.0, abs_tol=0.1)


@pytest.mark.asyncio
async def test_async_api_key_falls_back_to_environment(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("HERASCRAPE_API_KEY", "hs_live_fromenv")
    script = Script(_ok({}))
    client = Client(rate_limit=None, transport=httpx.MockTransport(script))
    await client.get("/users/1")
    assert script.requests[0].headers["x-api-key"] == "hs_live_fromenv"


@pytest.mark.parametrize("api_key", [None, ""])
def test_async_missing_api_key_raises_authentication_error(
    monkeypatch: pytest.MonkeyPatch, api_key: str | None
):
    monkeypatch.delenv("HERASCRAPE_API_KEY", raising=False)
    with pytest.raises(AuthenticationError, match="HERASCRAPE_API_KEY"):
        Client(api_key)


@pytest.mark.asyncio
async def test_async_context_manager_closes():
    client, _, _ = _make(_ok({}))
    async with client as entered:
        assert entered is client
        assert not client.closed
    assert client.closed


@pytest.mark.asyncio
async def test_async_aclose_is_explicit():
    client, _, _ = _make()
    await client.aclose()
    assert client.closed
