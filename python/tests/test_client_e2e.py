import re
from typing import Any, Optional

import httpx
import pytest

from herascrape import AsyncClient, Client

API_KEY = "hs_live_x"
UPPER_UUID = re.compile(r"[0-9A-F]{8}(-[0-9A-F]{4}){3}-[0-9A-F]{12}")


class Script:
    """MockTransport handler replaying a fixed list of replies."""

    def __init__(self, *replies: httpx.Response) -> None:
        self._replies = list(replies)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self._replies.pop(0)


class ClosingTransport(httpx.MockTransport):
    """MockTransport that records being closed."""

    closed = False

    def close(self) -> None:
        self.closed = True

    async def aclose(self) -> None:
        self.closed = True


def _ok(data: object) -> httpx.Response:
    return httpx.Response(200, json={"status": "success", "data": data})


def _page(
    items: list[Any],
    *,
    next_cursor: Optional[str] = None,
    key: str = "items",
) -> httpx.Response:
    return _ok(
        {
            key: items,
            "next_cursor": next_cursor,
            "has_more": next_cursor is not None,
        }
    )


def _client(script: Script) -> Client:
    return Client(api_key=API_KEY, transport=httpx.MockTransport(script))


def _async_client(script: Script) -> AsyncClient:
    return AsyncClient(api_key=API_KEY, transport=httpx.MockTransport(script))


def test_object_endpoint_returns_unwrapped_dict():
    script = Script(_ok({"pk": "123", "username": "nike"}))
    assert _client(script).user("123") == {"pk": "123", "username": "nike"}
    request = script.requests[0]
    assert request.method == "GET"
    assert request.url.path == "/users/123"
    assert request.headers["x-api-key"] == API_KEY


def test_search_users_autogenerates_session_ids():
    script = Script(_page([]))
    _client(script).search_users(query="nike")
    params = script.requests[0].url.params
    assert params["query"] == "nike"
    assert UPPER_UUID.fullmatch(params["search_session_id"])
    assert UPPER_UUID.fullmatch(params["serp_session_id"])
    assert params["search_session_id"] != params["serp_session_id"]
    assert "cursor" not in params


def test_iter_user_posts_paginates():
    script = Script(
        _page([{"pk": "1"}, {"pk": "2"}], next_cursor="c2"),
        _page([{"pk": "3"}]),
    )
    posts = list(_client(script).iter_user_posts("123"))
    assert posts == [{"pk": "1"}, {"pk": "2"}, {"pk": "3"}]
    first, second = script.requests
    assert "cursor" not in first.url.params
    assert second.url.params["cursor"] == "c2"


def test_iter_search_top_replays_query_and_session_ids():
    script = Script(
        _page([{"id": "a"}], next_cursor="c2", key="edges"),
        _page([{"id": "b"}], key="edges"),
    )
    edges = list(_client(script).iter_search_top(query="nike"))
    assert edges == [{"id": "a"}, {"id": "b"}]
    first, second = (dict(r.url.params) for r in script.requests)
    assert first["query"] == "nike"
    assert UPPER_UUID.fullmatch(first["search_session_id"])
    assert UPPER_UUID.fullmatch(first["serp_session_id"])
    assert "cursor" not in first
    assert second == {**first, "cursor": "c2"}


def test_context_manager_closes_transport():
    transport = ClosingTransport(Script(_ok({"status": "ok"})))
    with Client(api_key=API_KEY, transport=transport) as client:
        assert client.health() == {"status": "ok"}
        assert not transport.closed
    assert transport.closed


@pytest.mark.asyncio
async def test_async_user():
    script = Script(_ok({"pk": "123"}))
    async with _async_client(script) as client:
        assert await client.user("123") == {"pk": "123"}
    assert script.requests[0].url.path == "/users/123"


@pytest.mark.asyncio
async def test_async_iter_user_posts_paginates():
    script = Script(
        _page([{"pk": "1"}], next_cursor="c2"),
        _page([{"pk": "2"}]),
    )
    async with _async_client(script) as client:
        posts = [post async for post in client.iter_user_posts("123")]
    assert posts == [{"pk": "1"}, {"pk": "2"}]
    assert script.requests[1].url.params["cursor"] == "c2"


@pytest.mark.asyncio
async def test_async_context_manager_closes_transport():
    transport = ClosingTransport(Script())
    async with AsyncClient(api_key=API_KEY, transport=transport):
        assert not transport.closed
    assert transport.closed
