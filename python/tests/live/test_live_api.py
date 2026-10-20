from collections.abc import Iterator
from typing import Any

import pytest

from herascrape import AsyncClient, Client, NotFoundError

pytestmark = pytest.mark.live

LIVE_TIMEOUT = 30.0
INSTAGRAM_USERNAME = "instagram"
INSTAGRAM_PK = "25025320"
MISSING_USERNAME = "hs_no_such_user_7f3c9a1e2b"


@pytest.fixture
def client() -> Iterator[Client]:
    with Client(timeout=LIVE_TIMEOUT) as live_client:
        yield live_client


def test_health_reports_ok(client: Client) -> None:
    health: dict[str, Any] = client.health()
    assert health["status"] == "ok"


def test_user_by_username_has_profile_keys(client: Client) -> None:
    user: dict[str, Any] = client.user_by_username(username=INSTAGRAM_USERNAME)
    assert user["username"] == INSTAGRAM_USERNAME
    assert str(user["pk"]) == INSTAGRAM_PK


def test_iter_user_followers_stops_at_max_items(client: Client) -> None:
    followers: list[dict[str, Any]] = list(
        client.iter_user_followers(INSTAGRAM_PK, max_items=5)
    )
    assert 0 < len(followers) <= 5
    assert all("username" in follower for follower in followers)


def test_missing_username_raises_not_found(client: Client) -> None:
    with pytest.raises(NotFoundError) as excinfo:
        client.user_by_username(username=MISSING_USERNAME)
    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_async_user_by_username() -> None:
    async with AsyncClient(timeout=LIVE_TIMEOUT) as client:
        user: dict[str, Any] = await client.user_by_username(
            username=INSTAGRAM_USERNAME
        )
    assert user["username"] == INSTAGRAM_USERNAME
    assert str(user["pk"]) == INSTAGRAM_PK
