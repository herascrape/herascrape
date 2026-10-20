import asyncio
import json
import math
import os
import random
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, Optional, TypeVar, Union, cast

import httpx

from ._errors import (
    AuthenticationError,
    HerascrapeAPIError,
    HerascrapeTransportError,
    InvalidCursorError,
    RateLimitError,
    ServiceUnavailableError,
    UpstreamError,
    error_from_response,
)
from .ratelimit import DEFAULT_RATE_LIMIT, RateLimit, RateLimiter

DEFAULT_BASE_URL = "https://api.herascrape.com"
API_KEY_ENV_VAR = "HERASCRAPE_API_KEY"

Param = Union[str, int, float, bool]
ClientError = Union[HerascrapeAPIError, HerascrapeTransportError]

_BACKOFF_BASE = 0.5
_BACKOFF_CAP = 8.0
_BACKOFF_JITTER = 0.5
_MAX_RETRY_AFTER = 300.0

_RETRYABLE = (
    HerascrapeTransportError,
    UpstreamError,
    ServiceUnavailableError,
    InvalidCursorError,
)


def unwrap(payload: Any) -> Any:
    """Return the `data` member of a success envelope."""
    return payload["data"]


def drop_none(
    params: Optional[Mapping[str, Optional[Param]]],
) -> dict[str, Param]:
    """Query parameters without the unset (`None`) ones."""
    if params is None:
        return {}
    return {name: value for name, value in params.items() if value is not None}


def _parse_retry_after(value: Optional[str]) -> Optional[float]:
    """Seconds from a numeric `Retry-After`; `None` if absent or not usable."""
    if value is None:
        return None
    try:
        seconds = float(value)
    except ValueError:
        return None
    return max(seconds, 0.0) if math.isfinite(seconds) else None


def _json_object(body: bytes) -> dict[str, Any]:
    """The body as a JSON object; empty if it is anything else."""
    try:
        payload: Any = json.loads(body)
    except ValueError:
        return {}
    return cast(dict[str, Any], payload) if isinstance(payload, dict) else {}


def parse_error(
    *, status_code: int, headers: Mapping[str, str], body: bytes
) -> HerascrapeAPIError:
    """Build the exception for an error response, whatever its body."""
    payload = _json_object(body)
    error_code = payload.get("error_code")
    return error_from_response(
        status_code=status_code,
        error_code=error_code if isinstance(error_code, str) else None,
        detail=payload.get("detail"),
        request_id=headers.get("x-request-id"),
        retry_after=_parse_retry_after(headers.get("retry-after")),
    )


def is_retryable(exc: ClientError) -> bool:
    """Transient failures worth another attempt (429 is handled apart)."""
    return isinstance(exc, _RETRYABLE)


def backoff_delay(
    attempt: int, *, rng: Callable[[], float] = random.random
) -> float:
    """Seconds to wait before retry number `attempt` (0 for the first).

    Doubles from 0.5s up to an 8s cap, then drops by up to half at random.
    """
    delay = min(_BACKOFF_CAP, _BACKOFF_BASE * 2**attempt)
    return delay * (1 - _BACKOFF_JITTER * rng())


def retry_delay(exc: ClientError, *, attempt: int) -> Optional[float]:
    """Seconds to wait before retrying `exc`, or `None` if it is final."""
    if isinstance(exc, RateLimitError):
        if exc.retry_after is not None:
            return min(exc.retry_after, _MAX_RETRY_AFTER)
        return backoff_delay(attempt)
    return backoff_delay(attempt) if is_retryable(exc) else None


def transport_failure(exc: httpx.TransportError) -> HerascrapeTransportError:
    """The client-side error for a connection failure or timeout."""
    return HerascrapeTransportError(f"{type(exc).__name__}: {exc}")


def response_data(response: httpx.Response) -> Any:
    """The unwrapped `data` of a success response; raises on an error one."""
    if response.is_success:
        return unwrap(response.json())
    raise parse_error(
        status_code=response.status_code,
        headers=response.headers,
        body=response.content,
    )


_Client = TypeVar("_Client", bound="BaseSyncClient")


class BaseSyncClient:
    """Synchronous transport shared by every generated endpoint method."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 10.0,
        max_retries: int = 3,
        rate_limit: Optional[RateLimit] = DEFAULT_RATE_LIMIT,
        transport: Optional[httpx.BaseTransport] = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        key = api_key or os.environ.get(API_KEY_ENV_VAR)
        if not key:
            raise AuthenticationError(
                status_code=401,
                detail=f"No API key: pass api_key or set {API_KEY_ENV_VAR}.",
            )
        self._max_retries = max_retries
        self._sleep = sleep
        self._limiter = RateLimiter(rate_limit, sleep=sleep)
        self._client = httpx.Client(
            base_url=base_url,
            headers={"x-api-key": key, "accept": "application/json"},
            timeout=timeout,
            transport=transport,
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Mapping[str, Optional[Param]]] = None,
    ) -> Any:
        """Send a request and return the unwrapped `data`, retrying."""
        query = drop_none(params)
        attempt = 0
        while True:
            self._limiter.acquire()
            try:
                return self._send(method=method, path=path, params=query)
            except (HerascrapeAPIError, HerascrapeTransportError) as exc:
                delay = retry_delay(exc, attempt=attempt)
                if delay is None or attempt >= self._max_retries:
                    raise
                self._sleep(delay)
                attempt += 1

    def _send(self, *, method: str, path: str, params: dict[str, Param]) -> Any:
        try:
            response = self._client.request(method, path, params=params)
        except httpx.TransportError as exc:
            raise transport_failure(exc) from exc
        return response_data(response)

    def close(self) -> None:
        """Release the underlying connection pool."""
        self._client.close()

    def __enter__(self: _Client) -> _Client:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


_AsyncClient = TypeVar("_AsyncClient", bound="BaseAsyncClient")


class BaseAsyncClient:
    """Asynchronous transport shared by every generated endpoint method."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 10.0,
        max_retries: int = 3,
        rate_limit: Optional[RateLimit] = DEFAULT_RATE_LIMIT,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        asleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        key = api_key or os.environ.get(API_KEY_ENV_VAR)
        if not key:
            raise AuthenticationError(
                status_code=401,
                detail=f"No API key: pass api_key or set {API_KEY_ENV_VAR}.",
            )
        self._max_retries = max_retries
        self._asleep = asleep
        self._limiter = RateLimiter(rate_limit)
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"x-api-key": key, "accept": "application/json"},
            timeout=timeout,
            transport=transport,
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Mapping[str, Optional[Param]]] = None,
    ) -> Any:
        """Send a request and return the unwrapped `data`, retrying."""
        query = drop_none(params)
        attempt = 0
        while True:
            await self._limiter.aacquire(self._asleep)
            try:
                return await self._send(method=method, path=path, params=query)
            except (HerascrapeAPIError, HerascrapeTransportError) as exc:
                delay = retry_delay(exc, attempt=attempt)
                if delay is None or attempt >= self._max_retries:
                    raise
                await self._asleep(delay)
                attempt += 1

    async def _send(
        self, *, method: str, path: str, params: dict[str, Param]
    ) -> Any:
        try:
            response = await self._client.request(method, path, params=params)
        except httpx.TransportError as exc:
            raise transport_failure(exc) from exc
        return response_data(response)

    async def aclose(self) -> None:
        """Release the underlying connection pool."""
        await self._client.aclose()

    async def __aenter__(self: _AsyncClient) -> _AsyncClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()
