import math
from collections.abc import Mapping
from typing import Any, Optional, Union

import httpx
import pytest

from herascrape._base import (
    DEFAULT_BASE_URL,
    BaseSyncClient,
    backoff_delay,
    drop_none,
    is_retryable,
    parse_error,
    retry_delay,
    unwrap,
)
from herascrape._errors import (
    AuthenticationError,
    BadRequestError,
    HerascrapeAPIError,
    HerascrapeTransportError,
    InternalError,
    InvalidCursorError,
    InvalidParameterError,
    NotFoundError,
    RateLimitError,
    ServiceUnavailableError,
    UpstreamError,
)
from herascrape.ratelimit import RateLimit

API_KEY = "hs_live_xxxxxxxx"


class Script:
    """MockTransport handler replaying a fixed list of replies."""

    def __init__(self, *replies: Union[httpx.Response, Exception]) -> None:
        self._replies = list(replies)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        reply = self._replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


class Client(BaseSyncClient):
    def get(
        self, path: str, *, params: Optional[Mapping[str, Any]] = None
    ) -> Any:
        return self._request("GET", path, params=params)

    @property
    def closed(self) -> bool:
        return self._client.is_closed


def _make(
    *replies: Union[httpx.Response, Exception],
    max_retries: int = 3,
    rate_limit: Optional[RateLimit] = None,
) -> tuple[Client, Script, list[float]]:
    script = Script(*replies)
    sleeps: list[float] = []
    client = Client(
        API_KEY,
        max_retries=max_retries,
        rate_limit=rate_limit,
        transport=httpx.MockTransport(script),
        sleep=sleeps.append,
    )
    return client, script, sleeps


def _ok(data: object = None) -> httpx.Response:
    return httpx.Response(200, json={"status": "success", "data": data})


def _error(
    status_code: int,
    error_code: str,
    *,
    detail: str = "nope",
    headers: Optional[dict[str, str]] = None,
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


def test_unwraps_data():
    client, _, _ = _make(_ok({"pk": "1"}))
    assert client.get("/users/1") == {"pk": "1"}


def test_unwrap_returns_data_member():
    assert unwrap({"status": "success", "data": [1, 2]}) == [1, 2]


def test_sends_api_key_and_accept_headers():
    client, script, _ = _make(_ok({}))
    client.get("/users/1")
    request = script.requests[0]
    assert request.headers["x-api-key"] == API_KEY
    assert request.headers["accept"] == "application/json"
    assert str(request.url) == f"{DEFAULT_BASE_URL}/users/1"


def test_maps_404_not_found():
    client, script, sleeps = _make(_error(404, "not_found"))
    with pytest.raises(NotFoundError) as caught:
        client.get("/users/1")
    assert caught.value.status_code == 404
    assert len(script.requests) == 1
    assert sleeps == []


def test_surfaces_request_id():
    client, _, _ = _make(
        _error(404, "not_found", headers={"x-request-id": "req-123"})
    )
    with pytest.raises(NotFoundError) as caught:
        client.get("/users/1")
    assert caught.value.request_id == "req-123"


def test_retries_503_then_succeeds():
    client, script, sleeps = _make(
        _error(503, "upstream_unavailable"), _ok({"pk": "1"})
    )
    assert client.get("/users/1") == {"pk": "1"}
    assert len(script.requests) == 2
    assert len(sleeps) == 1
    _assert_backoff(sleeps[0], attempt=0)


def test_bare_gateway_503_without_body_is_retried():
    client, script, _ = _make(httpx.Response(503), _ok({"pk": "1"}))
    assert client.get("/users/1") == {"pk": "1"}
    assert len(script.requests) == 2


def test_bare_gateway_502_exhausted_raises_upstream_error():
    client, script, sleeps = _make(
        *[httpx.Response(502) for _ in range(4)], max_retries=3
    )
    with pytest.raises(UpstreamError):
        client.get("/users/1")
    assert len(script.requests) == 4
    assert len(sleeps) == 3
    for attempt, delay in enumerate(sleeps):
        _assert_backoff(delay, attempt=attempt)


def test_invalid_cursor_retried():
    client, script, sleeps = _make(
        _error(400, "invalid_cursor"), _ok({"items": []})
    )
    assert client.get("/users/1/posts") == {"items": []}
    assert len(script.requests) == 2
    assert len(sleeps) == 1


def test_429_without_retry_after_waits_and_retries():
    client, script, sleeps = _make(
        _error(429, "too_many_requests"), _ok({"pk": "1"})
    )
    assert client.get("/users/1") == {"pk": "1"}
    assert len(script.requests) == 2
    assert len(sleeps) == 1
    _assert_backoff(sleeps[0], attempt=0)


def test_429_honors_retry_after_header():
    client, _, sleeps = _make(
        _error(429, "too_many_requests", headers={"Retry-After": "2"}),
        _ok({"pk": "1"}),
    )
    assert client.get("/users/1") == {"pk": "1"}
    assert sleeps == [2.0]


def test_429_retry_after_wait_is_capped():
    client, _, sleeps = _make(
        _error(429, "too_many_requests", headers={"Retry-After": "86400"}),
        _ok({"pk": "1"}),
    )
    assert client.get("/users/1") == {"pk": "1"}
    assert sleeps == [300.0]


def test_429_exhausted_raises_rate_limit():
    client, script, sleeps = _make(
        *[_error(429, "too_many_requests") for _ in range(3)], max_retries=2
    )
    with pytest.raises(RateLimitError):
        client.get("/users/1")
    assert len(script.requests) == 3
    assert len(sleeps) == 2


def test_400_invalid_parameter_not_retried():
    client, script, sleeps = _make(_error(400, "invalid_parameter"))
    with pytest.raises(InvalidParameterError):
        client.get("/users/1")
    assert len(script.requests) == 1
    assert sleeps == []


def test_500_internal_error_not_retried():
    client, script, sleeps = _make(_error(500, "internal_error"))
    with pytest.raises(InternalError):
        client.get("/users/1")
    assert len(script.requests) == 1
    assert sleeps == []


def test_malformed_error_body_generic():
    client, script, _ = _make(httpx.Response(500, content=b"oops"))
    with pytest.raises(HerascrapeAPIError) as caught:
        client.get("/users/1")
    assert caught.value.status_code == 500
    assert caught.value.error_code is None
    assert len(script.requests) == 1


def test_none_params_dropped():
    client, script, _ = _make(_ok({}))
    client.get("/search", params={"cursor": None, "q": "x"})
    assert dict(script.requests[0].url.params) == {"q": "x"}


def test_transport_error_retried_then_succeeds():
    client, script, sleeps = _make(
        httpx.ConnectError("refused"), _ok({"pk": "1"})
    )
    assert client.get("/users/1") == {"pk": "1"}
    assert len(script.requests) == 2
    assert len(sleeps) == 1


def test_timeout_wrapped_as_transport_error():
    client, script, sleeps = _make(
        *[httpx.ReadTimeout("slow") for _ in range(3)], max_retries=2
    )
    with pytest.raises(HerascrapeTransportError) as caught:
        client.get("/users/1")
    assert isinstance(caught.value.__cause__, httpx.ReadTimeout)
    assert len(script.requests) == 3
    assert len(sleeps) == 2


def test_rate_limiter_acquired_before_every_attempt():
    client, script, sleeps = _make(
        _error(503, "upstream_unavailable"),
        _ok({}),
        _ok({}),
        rate_limit=RateLimit(rate=1, period="s"),
    )
    client.get("/a")
    client.get("/b")
    assert len(script.requests) == 3
    # One-token bucket and a frozen sleep: the retry backoff comes first,
    # then each later attempt queues one more second behind the last.
    assert len(sleeps) == 3
    _assert_backoff(sleeps[0], attempt=0)
    assert math.isclose(sleeps[1], 1.0, abs_tol=0.1)
    assert math.isclose(sleeps[2], 2.0, abs_tol=0.1)


def test_api_key_falls_back_to_environment(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("HERASCRAPE_API_KEY", "hs_live_fromenv")
    script = Script(_ok({}))
    client = Client(rate_limit=None, transport=httpx.MockTransport(script))
    client.get("/users/1")
    assert script.requests[0].headers["x-api-key"] == "hs_live_fromenv"


@pytest.mark.parametrize("api_key", [None, ""])
def test_missing_api_key_raises_authentication_error(
    monkeypatch: pytest.MonkeyPatch, api_key: Optional[str]
):
    monkeypatch.delenv("HERASCRAPE_API_KEY", raising=False)
    with pytest.raises(AuthenticationError, match="HERASCRAPE_API_KEY"):
        Client(api_key)


def test_context_manager_closes_client():
    client, _, _ = _make(_ok({}))
    with client as entered:
        assert entered is client
        assert not client.closed
    assert client.closed


def test_close_is_explicit():
    client, _, _ = _make()
    client.close()
    assert client.closed


def test_parse_error_reads_body_and_headers():
    error = parse_error(
        status_code=429,
        headers={"x-request-id": "r1", "retry-after": "3"},
        body=b'{"error_code": "too_many_requests", "detail": "slow down"}',
    )
    assert isinstance(error, RateLimitError)
    assert error.error_code == "too_many_requests"
    assert error.detail == "slow down"
    assert error.request_id == "r1"
    assert error.retry_after == 3.0


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (None, None),
        ("1.5", 1.5),
        ("0", 0.0),
        ("-5", 0.0),
        ("soon", None),
        ("Wed, 21 Oct 2026 07:28:00 GMT", None),
        ("inf", None),
        ("nan", None),
    ],
)
def test_parse_error_retry_after_values(
    header: Optional[str], expected: Optional[float]
):
    headers = {} if header is None else {"retry-after": header}
    error = parse_error(status_code=429, headers=headers, body=b"")
    assert isinstance(error, RateLimitError)
    assert error.retry_after == expected


@pytest.mark.parametrize(
    "body", [b"", b"oops", b"[1, 2]", b'"text"', b"null", b"\xff\xfe"]
)
def test_parse_error_tolerates_non_object_bodies(body: bytes):
    error = parse_error(status_code=418, headers={}, body=body)
    assert type(error) is HerascrapeAPIError
    assert error.status_code == 418
    assert error.error_code is None
    assert error.detail is None
    assert error.request_id is None


def test_parse_error_ignores_non_string_error_code():
    error = parse_error(
        status_code=404, headers={}, body=b'{"error_code": 7, "detail": "x"}'
    )
    assert type(error) is NotFoundError
    assert error.error_code is None
    assert error.detail == "x"


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (HerascrapeTransportError("down"), True),
        (UpstreamError(status_code=502), True),
        (ServiceUnavailableError(status_code=503), True),
        (InvalidCursorError(status_code=400), True),
        (InternalError(status_code=500), False),
        (BadRequestError(status_code=400), False),
        (InvalidParameterError(status_code=400), False),
        (NotFoundError(status_code=404), False),
        (RateLimitError(status_code=429), False),
    ],
)
def test_is_retryable_keys_on_exception_class(
    error: Union[HerascrapeAPIError, HerascrapeTransportError], expected: bool
):
    assert is_retryable(error) is expected


def test_retry_delay_covers_rate_limits_and_final_errors():
    assert retry_delay(RateLimitError(status_code=429), attempt=1) is not None
    assert (
        retry_delay(RateLimitError(status_code=429, retry_after=4.0), attempt=1)
        == 4.0
    )
    assert retry_delay(NotFoundError(status_code=404), attempt=0) is None


def test_backoff_delay_grows_and_is_capped():
    delays = [backoff_delay(n, rng=lambda: 0.0) for n in range(12)]
    assert delays == sorted(delays)
    assert delays[0] == 0.5
    assert delays[1] == 2 * delays[0]
    assert delays[-1] == delays[-2] == 8.0


def test_backoff_delay_jitter_stays_within_half_to_full():
    full = backoff_delay(2, rng=lambda: 0.0)
    assert backoff_delay(2, rng=lambda: 1.0) == full / 2
    assert backoff_delay(2, rng=lambda: 0.5) == full * 0.75


def test_backoff_delay_default_is_bounded():
    for attempt in range(6):
        _assert_backoff(backoff_delay(attempt), attempt=attempt)


def test_drop_none():
    assert drop_none(None) == {}
    assert drop_none({"a": None, "b": 0, "c": False, "d": ""}) == {
        "b": 0,
        "c": False,
        "d": "",
    }
