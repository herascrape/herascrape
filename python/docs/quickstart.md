---
myst:
  html_meta:
    description: "Install the herascrape Python client, authenticate with an API key, and make sync and async calls to the Instagram API."
---

# Quickstart

## Install

```bash
pip install herascrape
```

## Authenticate

Create a key in the [dashboard](https://herascrape.com/api-keys?utm_source=readthedocs&utm_medium=docs&utm_campaign=herascrape). The client
sends it as the `x-api-key` header on every request. Pass it in:

```python
from herascrape import Client

client = Client(api_key="hs_live_xxxxxxxx")
```

Or leave it out and the client reads `HERASCRAPE_API_KEY` from the
environment:

```bash
export HERASCRAPE_API_KEY=hs_live_xxxxxxxx
```

```python
client = Client()
```

With no key in either place the constructor raises
{class}`~herascrape.AuthenticationError`, before any request is sent. Keep keys
out of source control.

Billing is per successful call. Failed calls are not billed. `balance()` and
`resolve_media()` never reach Instagram and are free.

## Call an endpoint

Path parameters are positional, query parameters are keyword-only:

```python
user = client.user_by_username(username="instagram")
profile = client.user(user["pk"])
print(profile["full_name"], profile["is_verified"])

page = client.user_followers(user["pk"])
print(len(page["items"]), page["has_more"], page["next_cursor"])

post = client.post("B4XpqViUFUI")  # shortcode, media pk, or composite pk
print(post["like_count"], post["comment_count"])
```

The user endpoints take the numeric id (`pk`), so look a username up once and
keep the `pk` rather than paying for a resolve on every call.

## Async

{class}`~herascrape.AsyncClient` mirrors {class}`~herascrape.Client` method for
method. The `iter_*` helpers become async iterators, and one client-side rate
limiter is shared by every task on the client.

```python
import asyncio

from herascrape import AsyncClient


async def main() -> None:
    async with AsyncClient() as client:
        names = ["instagram", "natgeo", "nasa"]
        profiles = await asyncio.gather(
            *(client.user_by_username(username=name) for name in names)
        )
        print([profile["follower_count"] for profile in profiles])


asyncio.run(main())
```

## Close the client

Both classes hold an `httpx` connection pool. Use them as context managers, or
close them by hand when you are done:

```python
with Client() as client:
    print(client.health())

client = Client()
try:
    print(client.balance())
finally:
    client.close()  # await client.aclose() on AsyncClient
```

Reusing one client keeps connections warm, which is most of the difference
between a cold and a warm request. Build it once and pass it around rather than
constructing one per call.

## Constructor options

| Option | Default | What it does |
| --- | --- | --- |
| `api_key` | `HERASCRAPE_API_KEY` | Sent as `x-api-key`. Required, from here or the environment. |
| `base_url` | `https://api.herascrape.com` | Override to point at a proxy or a mock. |
| `timeout` | `10.0` | Seconds per request, passed to `httpx`. |
| `max_retries` | `3` | Retries after a transient failure. See [Retries and rate limits](rate-limits.md). |
| `rate_limit` | `RateLimit(rate=50, period="s")` | Client-side token bucket. `None` disables it. |

Only `api_key` may be positional:

```python
from herascrape import Client, RateLimit

client = Client(
    api_key="hs_live_xxxxxxxx",
    timeout=30.0,
    max_retries=5,
    rate_limit=RateLimit(rate=10, period="s"),
)
```

## Next

- [Pagination](pagination.md) for the list envelope and the `iter_*` helpers.
- [Error handling](error-handling.md) for the exception hierarchy.
- [Reference](reference/index.md) for every method and option.
