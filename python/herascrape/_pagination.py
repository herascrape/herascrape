from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from typing import Any, Optional

Page = dict[str, Any]
Item = dict[str, Any]


def _next_cursor(page: Page) -> Optional[str]:
    """Cursor for the following page, or None when the walk is over."""
    next_cursor = page["next_cursor"]
    has_more = page.get("has_more", next_cursor is not None)
    return next_cursor if has_more else None


def paginate(
    fetch_page: Callable[[Optional[str]], Page],
    *,
    item_key: str = "items",
    max_items: Optional[int] = None,
) -> Iterator[Item]:
    """Lazily yield `page[item_key]` across pages, up to `max_items`."""
    yielded = 0
    cursor: Optional[str] = None
    while max_items is None or yielded < max_items:
        page = fetch_page(cursor)
        for item in page[item_key]:
            yield item
            yielded += 1
            if max_items is not None and yielded >= max_items:
                return
        cursor = _next_cursor(page)
        if cursor is None:
            return


async def apaginate(
    fetch_page: Callable[[Optional[str]], Awaitable[Page]],
    *,
    item_key: str = "items",
    max_items: Optional[int] = None,
) -> AsyncIterator[Item]:
    """Async twin of `paginate`."""
    yielded = 0
    cursor: Optional[str] = None
    while max_items is None or yielded < max_items:
        page = await fetch_page(cursor)
        for item in page[item_key]:
            yield item
            yielded += 1
            if max_items is not None and yielded >= max_items:
                return
        cursor = _next_cursor(page)
        if cursor is None:
            return
