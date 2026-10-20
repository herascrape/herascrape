from typing import Any

import pytest

from herascrape._pagination import apaginate, paginate

Page = dict[str, Any]


def _page(
    items: list[int],
    *,
    cursor: str | None,
    more: bool,
    key: str = "items",
) -> Page:
    return {
        key: [{"id": n} for n in items],
        "next_cursor": cursor,
        "has_more": more,
    }


def _search_page(
    items: list[int],
    *,
    cursor: str | None,
    key: str = "edges",
) -> Page:
    """A search/top page: ``edges`` + ``next_cursor``, NO ``has_more``."""
    return {key: [{"id": n} for n in items], "next_cursor": cursor}


def _ids(items: list[Page]) -> list[int]:
    return [item["id"] for item in items]


class Script:
    """Fetcher that replays `pages` and records every cursor it receives."""

    def __init__(self, *pages: Page) -> None:
        self._pages = pages
        self.cursors: list[str | None] = []

    def _next(self, cursor: str | None) -> Page:
        self.cursors.append(cursor)
        return self._pages[len(self.cursors) - 1]

    def __call__(self, cursor: str | None) -> Page:
        return self._next(cursor)

    async def afetch(self, cursor: str | None) -> Page:
        return self._next(cursor)


async def _acollect(
    script: Script,
    *,
    item_key: str = "items",
    max_items: int | None = None,
) -> list[Page]:
    items = apaginate(script.afetch, item_key=item_key, max_items=max_items)
    return [item async for item in items]


def test_walks_two_pages():
    fetch = Script(
        _page([1, 2], cursor="c1", more=True),
        _page([3], cursor=None, more=False),
    )
    assert _ids(list(paginate(fetch))) == [1, 2, 3]
    assert fetch.cursors == [None, "c1"]


def test_empty_page_with_has_more_advances():
    fetch = Script(
        _page([], cursor="c1", more=True),
        _page([9], cursor=None, more=False),
    )
    assert _ids(list(paginate(fetch))) == [9]
    assert fetch.cursors == [None, "c1"]


def test_stops_on_null_cursor_even_if_has_more():
    fetch = Script(_page([1], cursor=None, more=True))
    assert _ids(list(paginate(fetch))) == [1]
    assert fetch.cursors == [None]


def test_stops_when_has_more_false_even_if_cursor_set():
    fetch = Script(_page([1], cursor="c1", more=False))
    assert _ids(list(paginate(fetch))) == [1]
    assert fetch.cursors == [None]


def test_search_top_shape_without_has_more():
    fetch = Script(
        _search_page([1, 2], cursor="c1"),
        _search_page([3], cursor=None),
    )
    items = list(paginate(fetch, item_key="edges"))
    assert _ids(items) == [1, 2, 3]
    assert fetch.cursors == [None, "c1"]


def test_max_items_truncates_mid_page():
    fetch = Script(_page([1, 2, 3], cursor="c1", more=True))
    assert _ids(list(paginate(fetch, max_items=2))) == [1, 2]
    assert fetch.cursors == [None]


def test_max_items_across_pages():
    fetch = Script(
        _page([1, 2], cursor="c1", more=True),
        _page([3, 4], cursor="c2", more=True),
    )
    assert _ids(list(paginate(fetch, max_items=3))) == [1, 2, 3]
    assert fetch.cursors == [None, "c1"]


def test_max_items_on_page_boundary_skips_next_fetch():
    fetch = Script(_page([1, 2], cursor="c1", more=True))
    assert _ids(list(paginate(fetch, max_items=2))) == [1, 2]
    assert fetch.cursors == [None]


def test_max_items_zero_fetches_nothing():
    fetch = Script()
    assert list(paginate(fetch, max_items=0)) == []
    assert fetch.cursors == []


def test_custom_item_key():
    fetch = Script(_page([7], cursor=None, more=False, key="edges"))
    assert _ids(list(paginate(fetch, item_key="edges"))) == [7]


def test_is_lazy():
    fetch = Script(
        _page([1, 2], cursor="c1", more=True),
        _page([3], cursor=None, more=False),
    )
    items = paginate(fetch)
    assert fetch.cursors == []
    assert next(items) == {"id": 1}
    assert next(items) == {"id": 2}
    assert fetch.cursors == [None]
    assert next(items) == {"id": 3}
    assert fetch.cursors == [None, "c1"]


@pytest.mark.asyncio
async def test_async_walks_two_pages():
    fetch = Script(
        _page([1, 2], cursor="c1", more=True),
        _page([3], cursor=None, more=False),
    )
    assert _ids(await _acollect(fetch)) == [1, 2, 3]
    assert fetch.cursors == [None, "c1"]


@pytest.mark.asyncio
async def test_async_empty_page_with_has_more_advances():
    fetch = Script(
        _page([], cursor="c1", more=True),
        _page([9], cursor=None, more=False),
    )
    assert _ids(await _acollect(fetch)) == [9]
    assert fetch.cursors == [None, "c1"]


@pytest.mark.asyncio
async def test_async_stops_on_null_cursor_even_if_has_more():
    fetch = Script(_page([1], cursor=None, more=True))
    assert _ids(await _acollect(fetch)) == [1]
    assert fetch.cursors == [None]


@pytest.mark.asyncio
async def test_async_max_items_on_page_boundary_skips_next_fetch():
    fetch = Script(_page([1, 2], cursor="c1", more=True))
    assert _ids(await _acollect(fetch, max_items=2)) == [1, 2]
    assert fetch.cursors == [None]


@pytest.mark.asyncio
async def test_async_custom_item_key():
    fetch = Script(_page([7], cursor=None, more=False, key="edges"))
    assert _ids(await _acollect(fetch, item_key="edges")) == [7]


@pytest.mark.asyncio
async def test_async_search_top_shape_without_has_more():
    fetch = Script(
        _search_page([1, 2], cursor="c1"),
        _search_page([3], cursor=None),
    )
    items = await _acollect(fetch, item_key="edges")
    assert _ids(items) == [1, 2, 3]
    assert fetch.cursors == [None, "c1"]


@pytest.mark.asyncio
async def test_async_is_lazy():
    fetch = Script(
        _page([1], cursor="c1", more=True),
        _page([2], cursor=None, more=False),
    )
    items = apaginate(fetch.afetch)
    assert fetch.cursors == []
    assert await anext(items) == {"id": 1}
    assert fetch.cursors == [None]
